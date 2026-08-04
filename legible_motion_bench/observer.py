"""The observer model: what a person watching believes the robot is doing.

This is the Boltzmann-rational model of Dragan, Lee and Srinivasa. A person
who assumes the robot is efficient scores each candidate goal by how much
the motion so far has cost relative to the best it could have done, and
normalises those scores into a belief:

    score(G) = exp( beta * ( C*(S -> G) - C(path so far) - C*(x_t -> G) ) )

C is path length and C* is the optimal cost-to-go, computed exactly in
costs.py. The bracket is at most zero and reaches zero only when the motion
so far is on an optimal path to G, so a goal loses belief in proportion to
the detour the robot has taken away from it.

There are two observer conditions and they are both first class.

    geodesic       the cost-to-go is the true shortest path around the
                   obstacles, modelling someone who can see the room
    straight_line  the cost-to-go is the straight line distance, modelling
                   someone who can see the robot and knows the candidate
                   goals but has no view of what stands between them

The second is not an ablation. Whether the ranking of planners survives the
change of observer is one of the questions the benchmark asks, and a robot
that reads as legible only to an observer with a floor plan has not
communicated anything to the person in the doorway.

Nothing here learns. Given a world and a path, the belief is a deterministic
function of the two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp

from .costs import CostToGoIndex, geodesic_cost, straight_line_cost
from .geometry import polyline_length
from .world import Scenario

CONDITIONS = ("geodesic", "straight_line")

# The rationality coefficient. One recovers the formulation as Dragan et al.
# state it, where the coefficient is absorbed into the cost. It is exposed
# because it sets how sharply the observer discriminates, and a result that
# holds only at one value of it is a result about that value.
DEFAULT_BETA = 1.0


class ObserverError(ValueError):
    """Raised when a belief cannot be computed for the inputs given."""


@dataclass(frozen=True)
class Observer:
    condition: str = "geodesic"
    beta: float = DEFAULT_BETA
    prior: dict | None = field(default=None)

    def __post_init__(self):
        if self.condition not in CONDITIONS:
            raise ObserverError(
                f"unknown observer condition {self.condition!r}, "
                f"expected one of {list(CONDITIONS)}"
            )
        if not self.beta > 0:
            raise ObserverError(f"beta must be positive, found {self.beta!r}")

    @property
    def name(self) -> str:
        """Identifier for records and table columns, beta included.

        The condition and the coefficient travel together because a belief
        computed at one coefficient is not comparable with a belief
        computed at another, and a column heading that hid the difference
        would invite exactly that comparison.
        """
        return f"{self.condition}_beta{self.beta:g}"

    def cost_to_go(self, position, goal_position, obstacles) -> float:
        """Cost-to-go under this observer's condition, computed from scratch.

        The reference implementation, kept simple and slow. Belief over a
        whole trajectory goes through the index instead, which returns the
        same numbers; `tests/test_costs.py` holds the differential test
        that says so.
        """
        if self.condition == "geodesic":
            return geodesic_cost(position, goal_position, obstacles)
        return straight_line_cost(position, goal_position)

    def index_for(self, scenario: Scenario) -> CostToGoIndex | None:
        """A reusable cost-to-go structure for this scenario, if one helps.

        None for the straight line observer, whose cost-to-go is a
        distance and needs no structure, and None for a world with no
        obstacles, where the geodesic is that same distance.
        """
        if self.condition != "geodesic" or not scenario.obstacles:
            return None
        return CostToGoIndex(
            scenario.obstacles, [g.position for g in scenario.goals]
        )

    def _cost_to_go(self, position, goal_position, obstacles, index) -> float:
        if self.condition != "geodesic":
            return straight_line_cost(position, goal_position)
        if index is None:
            return geodesic_cost(position, goal_position, obstacles)
        return index.cost_to(position, goal_position)

    def _prior_for(self, scenario: Scenario) -> dict:
        if self.prior is None:
            share = 1.0 / len(scenario.goals)
            return {g.id: share for g in scenario.goals}
        missing = set(scenario.goal_ids) - set(self.prior)
        extra = set(self.prior) - set(scenario.goal_ids)
        if missing or extra:
            raise ObserverError(
                f"prior does not match the goals of scenario {scenario.id!r}: "
                f"missing {sorted(missing)}, unexpected {sorted(extra)}"
            )
        if any(p < 0 for p in self.prior.values()):
            raise ObserverError(f"prior has a negative entry: {self.prior}")
        total = sum(self.prior.values())
        if total <= 0:
            raise ObserverError(f"prior sums to {total}, which cannot be normalised")
        return {k: v / total for k, v in self.prior.items()}

    def baseline(self, scenario: Scenario, index=None) -> dict:
        """Optimal cost from the start to each goal, C*(S -> G).

        Constant for a scenario and an observer condition, so it is
        computed once and handed to each belief rather than recomputed at
        every point of a trajectory.
        """
        return {
            g.id: self._cost_to_go(
                scenario.start, g.position, scenario.obstacles, index
            )
            for g in scenario.goals
        }

    def posterior(self, scenario: Scenario, prefix) -> dict:
        """Belief over the goals after the robot has travelled `prefix`.

        `prefix` is the path travelled so far, starting at the scenario's
        start position. A single point is a valid prefix and returns the
        prior, since no motion has yet distinguished anything.
        """
        index = self.index_for(scenario)
        return self._posterior(
            scenario,
            prefix,
            self._prior_for(scenario),
            self.baseline(scenario, index),
            index,
        )

    def _posterior(
        self, scenario: Scenario, prefix, prior: dict, baseline: dict, index
    ) -> dict:
        points = [tuple(map(float, p)) for p in prefix]
        if not points:
            raise ObserverError("a prefix must contain at least one point")
        if points[0] != scenario.start:
            raise ObserverError(
                f"prefix starts at {points[0]}, but scenario {scenario.id!r} "
                f"starts at {scenario.start}"
            )

        travelled = polyline_length(points)
        current = points[-1]

        exponents = {}
        for goal in scenario.goals:
            remaining = self._cost_to_go(
                current, goal.position, scenario.obstacles, index
            )
            exponents[goal.id] = self.beta * (
                baseline[goal.id] - travelled - remaining
            )

        # Subtract the largest exponent before exponentiating. A path that
        # wanders far from every goal drives all of these strongly negative,
        # and without the shift every weight would underflow to zero and the
        # normalisation would divide by it.
        shift = max(exponents.values())
        weights = {
            goal_id: prior[goal_id] * exp(value - shift)
            for goal_id, value in exponents.items()
        }
        total = sum(weights.values())
        if total <= 0:
            raise ObserverError(
                f"belief could not be normalised for scenario {scenario.id!r}; "
                f"every goal has zero weight under prior {prior}"
            )
        return {goal_id: w / total for goal_id, w in weights.items()}

    def posterior_sequence(self, scenario: Scenario, points) -> tuple[dict, ...]:
        """Belief after each successive point of a path.

        The first entry is the belief before the robot has moved, which is
        the prior, and the last is the belief on arrival.
        """
        path = [tuple(map(float, p)) for p in points]
        prior = self._prior_for(scenario)
        index = self.index_for(scenario)
        baseline = self.baseline(scenario, index)
        return tuple(
            self._posterior(scenario, path[: i + 1], prior, baseline, index)
            for i in range(len(path))
        )

    def belief_in_true_goal(self, scenario: Scenario, points) -> tuple[float, ...]:
        """Belief in the true goal after each successive point of a path."""
        return tuple(
            p[scenario.true_goal]
            for p in self.posterior_sequence(scenario, points)
        )


def default_observers(beta: float = DEFAULT_BETA) -> tuple[Observer, ...]:
    """The two conditions every result is reported under."""
    return tuple(Observer(condition=c, beta=beta) for c in CONDITIONS)

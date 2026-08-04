"""Legibility-optimised trajectories, with and without a safety constraint.

The trajectory is a polyline: the start, K free interior waypoints, and the
true goal. The endpoints are pinned rather than optimised, so the arrival
tolerance is never the thing under test.

The search is a compass search over the 2K waypoint coordinates, run from
several seeded starting points and given a fixed evaluation budget. It is
derivative free on purpose. The optimal cost-to-go has kinks wherever the
shortest path switches which obstacle corner it rounds, so the objective is
piecewise smooth with ridges running exactly through the configurations
that matter, and a gradient method would be working against the shape of
the problem rather than with it.

The safety-constrained planner is this same search with one clause added:
a candidate that enters a keep-out zone is rejected. Nothing else differs,
so the gap between the two planners measures the constraint and not two
different optimisers.

Both optimise against the informed observer, the one that can see the room,
because that is the model an engineer building a legible planner would
have. Results are reported under both observers. Tuning against the naive
observer would optimise away the very degradation the benchmark exists to
measure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .. import metrics
from ..observer import Observer
from ..world import Scenario
from .base import Plan, PlannerError, pinned_endpoints

DEFAULT_WAYPOINTS = 3
DEFAULT_BUDGET = 2000
DEFAULT_RESTARTS = 3
DEFAULT_SEED = 20260804
# The compass search stops when its step falls below this fraction of the
# world's size, or when the budget runs out, whichever comes first.
STEP_FLOOR_FRACTION = 1e-3
INITIAL_STEP_FRACTION = 0.12
IMPROVEMENT = 1e-12


class _Budget:
    """Counts objective evaluations and stops the search when they run out.

    Only a candidate that actually reaches the legibility computation
    spends budget. Candidates thrown out for leaving the world, for being
    infeasible, or for entering a keep-out zone are counted separately, so
    a run that spent most of its effort being refused says so instead of
    reporting a small number of evaluations and looking efficient.
    """

    def __init__(self, limit: int):
        self.limit = limit
        self.used = 0
        self.rejected = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def spend(self) -> None:
        self.used += 1

    def refuse(self) -> None:
        self.rejected += 1


@dataclass(frozen=True)
class LegiblePlanner:
    waypoints: int = DEFAULT_WAYPOINTS
    budget: int = DEFAULT_BUDGET
    restarts: int = DEFAULT_RESTARTS
    seed: int = DEFAULT_SEED
    spacing: float = metrics.DEFAULT_SAMPLE_SPACING
    respect_keep_out: bool = False
    observer: Observer = field(default_factory=lambda: Observer(condition="geodesic"))

    def __post_init__(self):
        if self.waypoints < 1:
            raise PlannerError(
                f"a legible planner needs at least one free waypoint, "
                f"found {self.waypoints}"
            )
        if self.budget < 1:
            raise PlannerError(f"budget must be positive, found {self.budget}")
        if self.restarts < 0:
            raise PlannerError(f"restarts cannot be negative, found {self.restarts}")

    @property
    def name(self) -> str:
        kind = "legible_safe" if self.respect_keep_out else "legible"
        return f"{kind}_k{self.waypoints}_b{self.budget}"

    def _path(self, scenario: Scenario, params) -> tuple:
        interior = [
            (params[2 * i], params[2 * i + 1]) for i in range(self.waypoints)
        ]
        return pinned_endpoints(
            scenario,
            [scenario.start, *interior, scenario.true_goal_position],
        )

    def _score(self, scenario: Scenario, params, budget: _Budget):
        """Legibility of these waypoints, or None if they are not allowed.

        None covers three separate refusals and the caller does not need to
        tell them apart: a waypoint outside the world, a trajectory that is
        infeasible, and, for the constrained planner, one that enters a
        keep-out zone.
        """
        if budget.exhausted:
            return None
        bounds = scenario.bounds
        for i in range(self.waypoints):
            if not bounds.contains((params[2 * i], params[2 * i + 1])):
                budget.refuse()
                return None

        points = self._path(scenario, params)
        if metrics.feasibility(scenario, points):
            budget.refuse()
            return None
        if self.respect_keep_out and metrics.safety(scenario, points).keep_out_entries:
            budget.refuse()
            return None

        budget.spend()
        samples = metrics.resample(points, self.spacing)
        legibility, _, _ = metrics.legibility_and_time_to_confidence(
            scenario,
            self.observer,
            samples,
            metrics.DEFAULT_SPEED,
            metrics.DEFAULT_CONFIDENCE_THRESHOLD,
        )
        return legibility

    def _seed_along_the_optimal_path(self, scenario: Scenario) -> list:
        """Waypoints spread evenly along the shortest path.

        A starting point that is feasible by construction, and whose score
        is the baseline's legibility, so the search can only report an
        improvement on doing nothing.
        """
        from ..costs import geodesic

        route = geodesic(
            scenario.start, scenario.true_goal_position, scenario.obstacles
        )
        samples = metrics.resample(
            route.path, max(route.cost / (self.waypoints + 1), 1e-9)
        )
        params = []
        for i in range(1, self.waypoints + 1):
            index = round(i * (len(samples) - 1) / (self.waypoints + 1))
            params.extend(samples[index])
        return params

    def _starting_points(self, scenario: Scenario, budget: _Budget) -> list:
        """Admissible waypoint sets to search from.

        The optimal path is the natural first seed, but the constrained
        planner cannot always use it: in a world where the cheapest route
        already crosses a keep-out zone, that seed is inadmissible and
        perturbing around it wastes the whole restart allowance on
        candidates that are refused for the same reason. So the seed is
        only kept if it is admissible, and the search for further starts
        recentres on the first admissible point it finds.
        """
        base = self._seed_along_the_optimal_path(scenario)
        starts = []
        if self._score(scenario, base, budget) is not None:
            starts.append(base)

        rng = random.Random(self.seed)
        span = min(
            scenario.bounds.xmax - scenario.bounds.xmin,
            scenario.bounds.ymax - scenario.bounds.ymin,
        )
        wanted = self.restarts if starts else max(self.restarts, 1)
        attempts = 20 if starts else 200
        while len(starts) < wanted + (1 if starts else 0):
            centre = starts[0] if starts else base
            found = False
            for attempt in range(attempts):
                # Widen the search the longer it goes without an
                # admissible point, so a tightly constrained world is not
                # explored at the same radius as an open one.
                scale = 0.25 * span * (1.0 + 3.0 * attempt / attempts)
                candidate = [p + rng.gauss(0.0, scale) for p in centre]
                if self._score(scenario, candidate, budget) is not None:
                    starts.append(candidate)
                    found = True
                    break
            if not found:
                break
        return starts

    def _compass_search(self, scenario: Scenario, start, budget: _Budget):
        best = list(start)
        best_score = self._score(scenario, best, budget)
        if best_score is None:
            return None, None

        span = max(
            scenario.bounds.xmax - scenario.bounds.xmin,
            scenario.bounds.ymax - scenario.bounds.ymin,
        )
        step = INITIAL_STEP_FRACTION * span
        floor = STEP_FLOOR_FRACTION * span

        while step > floor and not budget.exhausted:
            improved = False
            for axis in range(len(best)):
                for delta in (step, -step):
                    if budget.exhausted:
                        break
                    candidate = list(best)
                    candidate[axis] += delta
                    score = self._score(scenario, candidate, budget)
                    if score is not None and score > best_score + IMPROVEMENT:
                        best, best_score = candidate, score
                        improved = True
            if not improved:
                step /= 2.0
        return best, best_score

    def plan(self, scenario: Scenario) -> Plan:
        budget = _Budget(self.budget)
        baseline = self._score(
            scenario, self._seed_along_the_optimal_path(scenario), budget
        )

        best = None
        best_score = None
        for start in self._starting_points(scenario, budget):
            params, score = self._compass_search(scenario, start, budget)
            if score is not None and (best_score is None or score > best_score):
                best, best_score = params, score

        if best is None:
            raise PlannerError(
                f"{self.name} found no admissible trajectory for scenario "
                f"{scenario.id!r} within a budget of {self.budget} evaluations"
            )

        return Plan(
            planner=self.name,
            scenario_id=scenario.id,
            points=self._path(scenario, best),
            settings={
                "waypoints": self.waypoints,
                "budget": self.budget,
                "evaluations": budget.used,
                "refusals": budget.rejected,
                "restarts": self.restarts,
                "seed": self.seed,
                "spacing": self.spacing,
                "respect_keep_out": self.respect_keep_out,
                "observer": self.observer.name,
                "seed_legibility": baseline,
                "best_legibility": best_score,
            },
        )

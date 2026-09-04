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
from dataclasses import dataclass, field, replace
from math import hypot, sqrt

from .. import metrics
from ..costs import geodesic
from ..geometry import GeometryError, polyline_length
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

# The ceilings the frontier is traced at. A ceiling bounds the cost ratio,
# so 1.1 means the planner may spend a tenth more path than the optimum to
# buy clarity.
#
# There is no unbounded ceiling here, and its absence is a finding rather
# than an oversight. Dragan and Srinivasa bound their own optimisation with
# a trust region on cost, and they are explicit that their legibility model
# can only be trusted inside it: their user studies found observers who
# stopped reasoning about the declared goals once motion became strange
# enough, and began to believe in a goal that was not in the scene. Our
# observer cannot represent that belief, because its posterior sums to one
# over the goals the scenario declares however odd the trajectory is. An
# unbounded search reached a cost ratio near 3.6 on the fixtures, which is
# a legibility number computed outside the region where the formalism has
# ever been shown to correspond to what people perceive. Passing
# cost_budget=None is still supported, because seeing what the metric asks
# for when nothing stops it is the argument for stopping it, but such a
# point is a diagnostic and never a reported result.
DEFAULT_COST_CEILINGS = (1.05, 1.1, 1.25, 1.5, 2.0)


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
    cost_budget: float | None = None
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
        if self.cost_budget is not None and self.cost_budget < 1.0:
            raise PlannerError(
                f"cost budget is a ratio against the optimal path and cannot "
                f"be below one, found {self.cost_budget}"
            )

    @property
    def name(self) -> str:
        kind = "legible_safe" if self.respect_keep_out else "legible"
        ceiling = "inf" if self.cost_budget is None else f"{self.cost_budget:g}"
        return f"{kind}_k{self.waypoints}_c{ceiling}_e{self.budget}"

    def _path(self, scenario: Scenario, params) -> tuple:
        interior = [
            (params[2 * i], params[2 * i + 1]) for i in range(self.waypoints)
        ]
        return pinned_endpoints(
            scenario,
            [scenario.start, *interior, scenario.true_goal_position],
        )

    def _score(self, scenario: Scenario, params, budget: _Budget, optimal_cost: float):
        """Legibility of these waypoints, or None if they are not allowed.

        None covers four separate refusals and the caller does not need to
        tell them apart: a waypoint outside the world, a trajectory that is
        infeasible, one that spends more path than the cost budget allows,
        and, for the constrained planner, one that enters a keep-out zone.
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
        if (
            self.cost_budget is not None
            and polyline_length(points) > self.cost_budget * optimal_cost
        ):
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
        """Waypoints spread evenly along the shortest admissible path.

        For the unconstrained planner that is the shortest path, whose cost
        ratio is one so no cost budget can refuse it, and whose score is
        the baseline's legibility, so the search can only report an
        improvement on doing nothing.

        For the constrained planner the shortest path may be exactly what
        the constraint forbids, and it is precisely in those worlds that
        the comparison is interesting. So its seed is the shortest path
        that treats keep-out zones as blocking. That route has no zone
        entries by construction and is the cheapest such route, which
        matters because random restarts almost never satisfy a tight cost
        budget: perturbing three waypoints independently produces long
        paths, and a ceiling near one refuses nearly all of them.
        """
        blocking = tuple(scenario.obstacles)
        if self.respect_keep_out:
            blocking += tuple(scenario.keep_out_zones)
        try:
            route = geodesic(scenario.start, scenario.true_goal_position, blocking)
        except GeometryError:
            # A start or goal sitting inside a keep-out zone, or a zone
            # that seals the goal off. Fall back to the unconstrained
            # route; it will be refused, and the random restarts take over.
            route = geodesic(
                scenario.start, scenario.true_goal_position, scenario.obstacles
            )

        corners = route.path[1:-1]
        if len(corners) <= self.waypoints:
            # Keep every corner the optimal path turns at, then pad by
            # halving the longest leg. Spacing the waypoints evenly
            # instead would cut those corners, and a seed that cuts a
            # corner runs through the obstacle the corner was going
            # round: refused, leaving the search to start somewhere
            # arbitrary and able to finish below the baseline it was
            # supposed to begin from.
            points = list(route.path)
            while len(points) - 2 < self.waypoints:
                legs = [
                    hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(points, points[1:])
                ]
                longest = legs.index(max(legs))
                a, b = points[longest], points[longest + 1]
                points.insert(longest + 1, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            interior = points[1:-1]
        else:
            # More corners than free waypoints, so no setting of them
            # reproduces the optimal path. The seed is the best even
            # spacing available and may well be refused; the structured
            # starts are what the search then relies on.
            samples = metrics.resample(
                route.path, max(route.cost / (self.waypoints + 1), 1e-9)
            )
            interior = [
                samples[round(i * (len(samples) - 1) / (self.waypoints + 1))]
                for i in range(1, self.waypoints + 1)
            ]

        params = []
        for point in interior:
            params.extend(point)
        return params

    def _unconstrained_answer(self, scenario: Scenario):
        """What the same search finds when keep-out zones are only scored.

        Returns the waypoints and what they cost to find, or None and zero
        for the unconstrained planner, which has no twin to consult.

        Refusing a candidate does not only shrink the feasible set, it
        changes the path the compass search takes through it, because the
        route to a good safe region can run through candidates that are
        refused for entering a zone on the way. Measured on 4 September
        2026: in every world and ceiling where the unconstrained answer
        was itself safe, and so lay inside the constrained planner's own
        feasible set, the constrained search came back below it. Five
        cases out of five, by between 0.0010 and 0.0806 legibility, and
        unchanged by quadrupling the budget. A search that returns less
        than a trajectory it is obliged to accept is not measuring its
        constraint, it is reporting its own seeding.

        So the constrained planner starts from that answer whenever the
        constraint admits it. Nothing is smuggled: it comes from the same
        ceiling on the same scenario, and it is scored under the
        constrained rules like any other candidate, so an unsafe one is
        refused rather than adopted. It is not free either. The twin
        search spends its own budget, recorded separately as
        seed_search_evaluations, so a constrained run costs about twice
        what an unconstrained one costs.
        """
        if not self.respect_keep_out:
            return None, 0
        try:
            plan = replace(self, respect_keep_out=False).plan(scenario)
        except PlannerError:
            # The unconstrained search found nothing either, so there is
            # nothing to seed from and the constrained search proceeds as
            # it did before.
            return None, 0
        interior = plan.points[1:-1]
        if len(interior) != self.waypoints:
            return None, plan.settings["evaluations"]
        params = []
        for point in interior:
            params.extend(point)
        return params, plan.settings["evaluations"]

    def _starting_points(
        self,
        scenario: Scenario,
        budget: _Budget,
        optimal_cost: float,
        unconstrained=None,
    ) -> list:
        """Admissible waypoint sets to search from.

        The optimal path is the natural first seed, but the constrained
        planner cannot always use it: in a world where the cheapest route
        already crosses a keep-out zone, that seed is inadmissible and
        perturbing around it wastes the whole restart allowance on
        candidates that are refused for the same reason. So the seed is
        only kept if it is admissible, and the search for further starts
        recentres on the first admissible point it finds.

        The unconstrained answer, where there is one, is scored before
        anything else and kept ahead of everything else. Both orderings
        matter. Scored first, because a start scored after the budget has
        run out is refused for that alone. Kept first, because the list
        is truncated to the restart allowance, and this is the one start
        whose presence the guarantee rests on: the compass search only
        ever accepts an improvement, so beginning here is what stops the
        constrained result falling below it.
        """
        base = self._seed_along_the_optimal_path(scenario)
        scored = []
        pinned = []
        if unconstrained is not None:
            score = self._score(scenario, unconstrained, budget, optimal_cost)
            if score is not None:
                pinned.append(unconstrained)
        for candidate in self._structured_starts(scenario, base, optimal_cost):
            score = self._score(scenario, candidate, budget, optimal_cost)
            if score is not None:
                scored.append((score, candidate))

        rng = random.Random(self.seed)
        deviation = self._characteristic_deviation(scenario, optimal_cost)
        centre = scored[0][1] if scored else base
        for _ in range(self.restarts):
            for attempt in range(60):
                # Widen the search the longer it goes without an
                # admissible point, so a tightly constrained world is not
                # explored at the same radius as an open one.
                scale = deviation * (1.0 + 3.0 * attempt / 60)
                candidate = [p + rng.gauss(0.0, scale) for p in centre]
                score = self._score(scenario, candidate, budget, optimal_cost)
                if score is not None:
                    scored.append((score, candidate))
                    break

        # Refine the most promising starts rather than all of them, so a
        # small budget is spent going deep in a few basins instead of
        # shallow in many.
        scored.sort(key=lambda pair: -pair[0])
        return pinned + [
            candidate
            for _score, candidate in scored[: self.restarts + 1 - len(pinned)]
        ]

    def _structured_starts(self, scenario: Scenario, base, optimal_cost: float) -> list:
        """Seeds that differ in which way they go round, not only by how far.

        The objective is multimodal across homotopy classes: going above an
        obstacle and going below it are separate basins, and a compass
        search started in one will not cross to the other however long it
        runs. Random perturbation does not reliably cross either, because
        under a tight cost budget nearly every random displacement is
        refused for being too long.

        So the seed is also offset bodily to each side of the line from the
        start to the goal, at several magnitudes. That samples both
        families deliberately instead of hoping to stumble into them.
        """
        deviation = self._characteristic_deviation(scenario, optimal_cost)
        sx, sy = scenario.start
        gx, gy = scenario.true_goal_position
        length = hypot(gx - sx, gy - sy)
        if length <= 0:
            return [base]
        across = (-(gy - sy) / length, (gx - sx) / length)

        starts = [base]
        for magnitude in (0.5, 1.0, 2.0):
            for sign in (1.0, -1.0):
                offset = sign * magnitude * deviation
                starts.append(
                    [
                        value + across[index % 2] * offset
                        for index, value in enumerate(base)
                    ]
                )
        return starts

    def _characteristic_deviation(
        self, scenario: Scenario, optimal_cost: float
    ) -> float:
        """How far a waypoint can move before the cost budget refuses it.

        A detour that leaves a straight path of length L, reaches a
        perpendicular distance d and returns costs about 2d^2/L more than
        going straight, so a cost ratio ceiling of c allows a deviation of
        roughly L*sqrt((c-1)/2). Sizing the search around that keeps a
        tight ceiling from spending its whole restart allowance proposing
        detours it will refuse, and keeps a loose one from creeping.

        With no ceiling there is nothing to derive it from, so the search
        falls back to a fraction of the world.
        """
        span = max(
            scenario.bounds.xmax - scenario.bounds.xmin,
            scenario.bounds.ymax - scenario.bounds.ymin,
        )
        if self.cost_budget is None:
            return INITIAL_STEP_FRACTION * span
        allowed = optimal_cost * sqrt(max(self.cost_budget - 1.0, 0.0) / 2.0)
        return min(max(allowed, STEP_FLOOR_FRACTION * span), INITIAL_STEP_FRACTION * span)

    def _compass_search(
        self, scenario: Scenario, start, budget: _Budget, optimal_cost: float
    ):
        best = list(start)
        best_score = self._score(scenario, best, budget, optimal_cost)
        if best_score is None:
            return None, None

        span = max(
            scenario.bounds.xmax - scenario.bounds.xmin,
            scenario.bounds.ymax - scenario.bounds.ymin,
        )
        step = self._characteristic_deviation(scenario, optimal_cost)
        floor = STEP_FLOOR_FRACTION * span

        while step > floor and not budget.exhausted:
            improved = False
            for axis in range(len(best)):
                for delta in (step, -step):
                    if budget.exhausted:
                        break
                    candidate = list(best)
                    candidate[axis] += delta
                    score = self._score(scenario, candidate, budget, optimal_cost)
                    if score is not None and score > best_score + IMPROVEMENT:
                        best, best_score = candidate, score
                        improved = True
            if not improved:
                step /= 2.0
        return best, best_score

    def plan(self, scenario: Scenario) -> Plan:
        # Before this planner's own budget is touched, so that the seed is
        # scored against a full budget rather than the remains of one.
        unconstrained, seed_search_evaluations = self._unconstrained_answer(scenario)

        budget = _Budget(self.budget)
        optimal_cost = geodesic(
            scenario.start, scenario.true_goal_position, scenario.obstacles
        ).cost
        baseline = self._score(
            scenario,
            self._seed_along_the_optimal_path(scenario),
            budget,
            optimal_cost,
        )

        best = None
        best_score = None
        for start in self._starting_points(
            scenario, budget, optimal_cost, unconstrained
        ):
            params, score = self._compass_search(
                scenario, start, budget, optimal_cost
            )
            if score is not None and (best_score is None or score > best_score):
                best, best_score = params, score

        if best is None:
            # The wording matters and is not defensive. A compass search
            # that comes back empty has failed to find something; it has
            # not shown there is nothing to find. Any claim of the form
            # "no trajectory within this cost budget achieves that" is a
            # statement about this search at this budget, and must be
            # written that way wherever it is reported.
            raise PlannerError(
                f"{self.name} did not find an admissible trajectory for "
                f"scenario {scenario.id!r} within {self.budget} evaluations "
                f"after {budget.rejected} refusals; this is a failure to "
                f"find one, not a proof that none exists",
                evaluations=budget.used,
                refusals=budget.rejected,
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
                "cost_budget": self.cost_budget,
                "observer": self.observer.name,
                "seed_search_evaluations": seed_search_evaluations,
                "seed_legibility": baseline,
                "best_legibility": best_score,
            },
        )


@dataclass(frozen=True)
class SweepPoint:
    """One cost ceiling and what the search found under it.

    `plan` is None when the search came back empty. That is recorded as a
    search outcome and never as a proof: `not_found` says the committed
    search at this budget did not find an admissible trajectory, which is
    a weaker statement than saying none exists, and the difference has to
    survive into anything written from these records.
    """

    ceiling: float | None
    plan: Plan | None
    not_found: str | None
    evaluations: int
    refusals: int

    def as_record(self) -> dict:
        return {
            "ceiling": self.ceiling,
            "plan": None if self.plan is None else self.plan.as_record(),
            "not_found": self.not_found,
            "evaluations": self.evaluations,
            "refusals": self.refusals,
        }


def sweep(scenario: Scenario, ceilings=DEFAULT_COST_CEILINGS, **planner_settings):
    """One point per cost ceiling, which is what traces the frontier.

    A single legibility-optimised trajectory is a point. The question the
    benchmark asks is what clarity costs, and that is only answerable by
    asking the same planner the same question under a series of budgets.
    Ceilings are searched in the order given and each is planned
    independently, so no ceiling inherits another's answer and the sweep
    cannot smuggle a result from a looser budget into a tighter one.

    A ceiling under which nothing admissible is found does not stop the
    sweep. Tight ceilings combined with a safety constraint are exactly
    where that happens, and it is the interesting part of the frontier
    rather than an error.
    """
    points = []
    for ceiling in ceilings:
        planner = LegiblePlanner(cost_budget=ceiling, **planner_settings)
        try:
            plan = planner.plan(scenario)
        except PlannerError as exc:
            points.append(
                SweepPoint(
                    ceiling=ceiling,
                    plan=None,
                    not_found=str(exc),
                    evaluations=getattr(exc, "evaluations", 0),
                    refusals=getattr(exc, "refusals", 0),
                )
            )
            continue
        points.append(
            SweepPoint(
                ceiling=ceiling,
                plan=plan,
                not_found=None,
                evaluations=plan.settings["evaluations"],
                refusals=plan.settings["refusals"],
            )
        )
    return tuple(points)

"""What a trajectory is worth: clarity, cost, and constraint satisfaction.

Four quantities, computed exactly from the trajectory and the world. No
human raters and no model judges anywhere in this file.

    legibility          belief mass on the true goal, weighted towards
                        early motion, normalised to [0, 1]
    cost ratio          path length over the optimal path length
    time to confidence  when the observer's belief in the true goal rises
                        above a threshold and stays there
    safety              keep-out zone entries and minimum clearance

They are returned together in one record and there is no way to ask this
module for one without the others. Legibility bought by cutting a corner is
not legibility, and a column that reported it alone would say so anyway.

Obstacles and keep-out zones are treated differently on purpose. Passing
through an obstacle is infeasible: the observer's cost-to-go is undefined
inside one, so the trajectory scores as a constraint violation and carries
no legibility number. Crossing a keep-out zone is feasible and scored. If
keep-out zones were hard too there would be no frontier to measure, because
no planner could ever trade safety for clarity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot, inf, isfinite

from .costs import geodesic_cost
from .geometry import (
    polyline_enters_interior,
    polyline_length,
    polyline_min_clearance,
)
from .observer import Observer
from .world import Scenario

# How close a trajectory must come to the true goal to count as having
# arrived. Our own planners land on it exactly, so this only ever binds on
# a trajectory proposed by a language model.
#
# It is deliberately far tighter than any physically meaningful margin. A
# trajectory that stops a centimetre short of the goal has not reached the
# goal, and scoring it as an arrival would let a model post a legibility
# number for motion that never completed the task. The tolerance absorbs
# floating point, nothing else.
ARRIVAL_TOLERANCE = 1e-6

# Spacing between samples along the path, in world units. The robot moves
# at constant speed, so this is also the time step once divided by speed,
# and a longer trajectory is measured at more samples rather than at the
# same number spread thinner. That is what makes a slower route arrive
# later in time to confidence instead of merely looking different.
DEFAULT_SAMPLE_SPACING = 0.05
DEFAULT_SPEED = 1.0
DEFAULT_CONFIDENCE_THRESHOLD = 0.8


class MetricError(ValueError):
    """Raised when metrics are asked for something they cannot mean."""


@dataclass(frozen=True)
class Safety:
    keep_out_entries: int
    keep_out_zone_ids: tuple[str, ...]
    min_clearance: float

    @property
    def enters_keep_out(self) -> bool:
        return self.keep_out_entries > 0


@dataclass(frozen=True)
class TrajectoryMetrics:
    scenario_id: str
    observer: str
    feasible: bool
    infeasibility: tuple[str, ...]
    path_cost: float
    optimal_cost: float
    cost_ratio: float | None
    legibility: float | None
    time_to_confidence: float | None
    duration: float
    confidence_threshold: float
    sample_spacing: float
    speed: float
    samples: int
    safety: Safety

    def as_record(self) -> dict:
        record = asdict(self)
        record["safety"] = asdict(self.safety)
        record["safety"]["enters_keep_out"] = self.safety.enters_keep_out
        return record


def resample(points, spacing: float) -> tuple[tuple[float, float], ...]:
    """Points at equal arc length along a polyline, both ends included.

    The number of samples follows from the length rather than being fixed,
    so two trajectories are compared at the same resolution rather than at
    the same count. The spacing actually used is at most the spacing asked
    for, and both endpoints land exactly on the original ones.
    """
    if spacing <= 0:
        raise MetricError(f"sample spacing must be positive, found {spacing!r}")
    path = [(float(x), float(y)) for x, y in points]
    if len(path) < 2:
        raise MetricError("a trajectory needs at least two points to be sampled")

    lengths = [0.0]
    for a, b in zip(path, path[1:]):
        lengths.append(lengths[-1] + hypot(b[0] - a[0], b[1] - a[1]))
    total = lengths[-1]
    if total <= 0:
        raise MetricError("a trajectory of zero length cannot be sampled")

    steps = max(1, int(-(-total // spacing)))
    samples = []
    segment = 0
    for i in range(steps + 1):
        target = total * i / steps
        while segment < len(path) - 2 and lengths[segment + 1] < target:
            segment += 1
        a, b = path[segment], path[segment + 1]
        span = lengths[segment + 1] - lengths[segment]
        t = 0.0 if span <= 0 else (target - lengths[segment]) / span
        t = min(1.0, max(0.0, t))
        samples.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    samples[0] = path[0]
    samples[-1] = path[-1]
    return tuple(samples)


def feasibility(scenario: Scenario, points) -> tuple[str, ...]:
    """Why a trajectory cannot be scored for legibility, if it cannot.

    Returns an empty tuple when the trajectory is feasible. Entering a
    keep-out zone is deliberately not on this list: that is a safety
    violation the trajectory is scored for, not a reason it cannot be
    scored at all.
    """
    path = [(float(x), float(y)) for x, y in points]
    reasons: list[str] = []
    if len(path) < 2:
        return (f"has {len(path)} point(s), a trajectory needs at least two",)
    if polyline_length(path) <= 0:
        reasons.append("has zero length")

    if path[0] != scenario.start:
        reasons.append(f"starts at {path[0]} rather than at {scenario.start}")

    goal = scenario.true_goal_position
    if hypot(path[-1][0] - goal[0], path[-1][1] - goal[1]) > ARRIVAL_TOLERANCE:
        reasons.append(
            f"ends at {path[-1]} rather than at the true goal {goal}"
        )

    for obstacle in scenario.obstacles:
        if polyline_enters_interior(path, obstacle):
            reasons.append(f"passes through the interior of obstacle {obstacle.id!r}")

    return tuple(reasons)


def safety(scenario: Scenario, points) -> Safety:
    """Keep-out entries and minimum clearance, mechanically."""
    path = [(float(x), float(y)) for x, y in points]
    entered = tuple(
        zone.id
        for zone in scenario.keep_out_zones
        if polyline_enters_interior(path, zone)
    )
    return Safety(
        keep_out_entries=len(entered),
        keep_out_zone_ids=entered,
        min_clearance=polyline_min_clearance(path, scenario.obstacles),
    )


def legibility_and_time_to_confidence(
    scenario: Scenario,
    observer: Observer,
    samples,
    speed: float,
    threshold: float,
) -> tuple[float, float | None, float]:
    """Legibility, time to confidence, and duration for a sampled path.

    Legibility follows Dragan et al.: the belief in the true goal averaged
    over the trajectory with weight f(t) = T - t, so the same clarity
    counts for more the earlier it arrives. Weights are non-negative and
    the belief is a probability, so the result lies in [0, 1].

    Time to confidence is the first sample time after which the belief in
    the true goal never again falls below the threshold. It is None when
    the trajectory ends below the threshold, which is a different statement
    from arriving late and must not be recorded as a large number.
    """
    beliefs = observer.belief_in_true_goal(scenario, samples)
    steps = len(samples) - 1
    total = polyline_length(samples)
    duration = total / speed
    times = [duration * i / steps for i in range(steps + 1)]

    weights = [duration - t for t in times]
    weight_total = sum(weights)
    if weight_total <= 0:
        raise MetricError("trajectory has no duration to weight legibility over")
    legibility = sum(b * w for b, w in zip(beliefs, weights)) / weight_total

    time_to_confidence = None
    for i in range(len(beliefs) - 1, -1, -1):
        if beliefs[i] < threshold:
            break
        time_to_confidence = times[i]

    return legibility, time_to_confidence, duration


def evaluate(
    scenario: Scenario,
    observer: Observer,
    points,
    spacing: float = DEFAULT_SAMPLE_SPACING,
    speed: float = DEFAULT_SPEED,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> TrajectoryMetrics:
    """Score one trajectory in one world under one observer.

    An infeasible trajectory carries no legibility number and no cost
    ratio. The raw path length and optimal length are still recorded, so
    the numbers remain auditable, but neither is turned into a figure that
    would flatter a trajectory for stopping early or for walking through a
    wall.
    """
    if speed <= 0:
        raise MetricError(f"speed must be positive, found {speed!r}")
    if not 0.0 < threshold <= 1.0:
        raise MetricError(
            f"confidence threshold must lie in (0, 1], found {threshold!r}"
        )

    path = [(float(x), float(y)) for x, y in points]
    reasons = feasibility(scenario, path)
    feasible = not reasons

    path_cost = polyline_length(path) if len(path) >= 2 else 0.0
    optimal_cost = geodesic_cost(
        scenario.start, scenario.true_goal_position, scenario.obstacles
    )
    zone_safety = safety(scenario, path) if len(path) >= 1 else Safety(0, (), inf)

    legibility = None
    time_to_confidence = None
    cost_ratio = None
    samples: tuple = ()
    duration = path_cost / speed

    if feasible:
        samples = resample(path, spacing)
        legibility, time_to_confidence, duration = legibility_and_time_to_confidence(
            scenario, observer, samples, speed, threshold
        )
        cost_ratio = path_cost / optimal_cost

    return TrajectoryMetrics(
        scenario_id=scenario.id,
        observer=observer.name,
        feasible=feasible,
        infeasibility=reasons,
        path_cost=path_cost,
        optimal_cost=optimal_cost,
        cost_ratio=cost_ratio,
        legibility=legibility,
        time_to_confidence=time_to_confidence,
        duration=duration,
        confidence_threshold=threshold,
        sample_spacing=spacing,
        speed=speed,
        samples=len(samples),
        safety=zone_safety,
    )


def evaluate_all_observers(
    scenario: Scenario,
    observers,
    points,
    **kwargs,
) -> tuple[TrajectoryMetrics, ...]:
    """Score one trajectory under every observer condition."""
    return tuple(evaluate(scenario, o, points, **kwargs) for o in observers)


def summarise(records) -> str:
    """A fixed-width table of scored trajectories, for reading at a terminal.

    Legibility never appears without its cost and safety columns beside it,
    and an infeasible row shows why rather than showing a blank.
    """
    rows = list(records)
    if not rows:
        return "no trajectories scored\n"
    header = (
        f"{'scenario':<18} {'observer':<20} {'legib':>7} {'cost':>7} "
        f"{'ttc':>7} {'keepout':>8} {'clear':>7}"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        if not r.feasible:
            lines.append(
                f"{r.scenario_id:<18} {r.observer:<20} "
                f"{'violation':>7} {'':>7} {'':>7} "
                f"{r.safety.keep_out_entries:>8} "
                f"{_clearance(r.safety.min_clearance):>7}   {'; '.join(r.infeasibility)}"
            )
            continue
        ttc = "never" if r.time_to_confidence is None else f"{r.time_to_confidence:.2f}"
        lines.append(
            f"{r.scenario_id:<18} {r.observer:<20} "
            f"{r.legibility:>7.4f} {r.cost_ratio:>7.4f} {ttc:>7} "
            f"{r.safety.keep_out_entries:>8} "
            f"{_clearance(r.safety.min_clearance):>7}"
        )
    return "\n".join(lines) + "\n"


def _clearance(value: float) -> str:
    return "none" if not isfinite(value) else f"{value:.4f}"

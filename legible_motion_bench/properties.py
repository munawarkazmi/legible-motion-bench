"""Machine-checked facts carried inside scenario files.

Every scenario asserts what it is for. A scenario built to be ambiguous at
the start says so as a property, and committed code decides whether it is
true. Nothing here is authored by assertion: a fact is either a threshold
the author chose and the code checks, or a quantity the code computes and a
tool writes back into the file.

The registry is closed. A scenario that names a kind this build does not
implement fails loudly rather than being counted as verified, which is the
only way a proof obligation can be added before its proof exists without
anyone noticing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .costs import geodesic
from .geometry import polyline_enters_interior, polyline_min_clearance
from .metrics import DEFAULT_SAMPLE_SPACING, resample
from .observer import Observer
from .world import Property, Scenario

TOLERANCE = 1e-9

# Properties about belief are evaluated along the optimal path at this
# spacing. It is fixed rather than a property argument so that two
# scenarios cannot quietly assert their facts at different resolutions.
BELIEF_SPACING = DEFAULT_SAMPLE_SPACING


class PropertyError(ValueError):
    """Raised when a property is malformed or names an unknown kind."""


@dataclass(frozen=True)
class PropertyResult:
    kind: str
    ok: bool
    computed: object
    expected: str
    detail: str


@dataclass(frozen=True)
class Kind:
    name: str
    required_args: frozenset
    carries_value: bool
    compute: Callable[[Scenario, dict], object]
    compare: Callable[[object, Property], tuple[bool, str]]
    describes: Callable[[Property], str]


def _geodesic_for(scenario: Scenario, args: dict):
    start = scenario.point_named(args["from"])
    end = scenario.point_named(args["to"])
    return geodesic(start, end, scenario.obstacles)


def _compute_geodesic_cost(scenario: Scenario, args: dict) -> float:
    return _geodesic_for(scenario, args).cost


def _compute_keep_out_entries(scenario: Scenario, args: dict) -> int:
    path = _geodesic_for(scenario, args).path
    return sum(
        1 for zone in scenario.keep_out_zones if polyline_enters_interior(path, zone)
    )


def _compute_min_clearance(scenario: Scenario, args: dict) -> float:
    path = _geodesic_for(scenario, args).path
    return polyline_min_clearance(path, scenario.obstacles)


def _compute_goal_separation(scenario: Scenario, args: dict) -> float:
    positions = [g.position for g in scenario.goals]
    return min(
        ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        for i, a in enumerate(positions)
        for b in positions[i + 1 :]
    )


def _compute_goal_cost_spread(scenario: Scenario, args: dict) -> float:
    """Spread of optimal costs from the start across all candidate goals.

    A small spread is what makes a scenario worth including: if one goal is
    far cheaper than the rest, an observer who assumes the robot is rational
    already knows the answer before the robot moves, and there is no
    ambiguity for a legible trajectory to resolve.
    """
    costs = [
        geodesic(scenario.start, g.position, scenario.obstacles).cost
        for g in scenario.goals
    ]
    return max(costs) - min(costs)


def _optimal_beliefs(scenario: Scenario, condition: str) -> tuple[float, ...]:
    """Belief in the true goal along the optimal path, sample by sample.

    Every belief property is about the optimal path rather than about some
    planner's output, because a scenario has to state what it is for
    without depending on which planners happen to exist. What a scenario
    can honestly assert is a fact about its own geometry: how long the
    cheapest way to the goal leaves an observer guessing.
    """
    route = geodesic(
        scenario.start, scenario.true_goal_position, scenario.obstacles
    )
    samples = resample(route.path, BELIEF_SPACING)
    return Observer(condition=condition).belief_in_true_goal(scenario, samples)


def _compute_early_belief(scenario: Scenario, args: dict) -> float:
    """Highest belief in the true goal over the opening of the optimal path.

    The fact the whole benchmark rests on: that the cheapest trajectory
    leaves the question open for a while. If this is already high, there
    is no ambiguity for a legible trajectory to resolve and the scenario
    is not testing anything.
    """
    beliefs = _optimal_beliefs(scenario, args["observer"])
    fraction = float(args["until_fraction"])
    if not 0.0 < fraction <= 1.0:
        raise PropertyError(
            f"until_fraction must lie in (0, 1], found {fraction!r}"
        )
    cutoff = max(1, round(fraction * (len(beliefs) - 1)))
    return max(beliefs[: cutoff + 1])


def _compute_final_belief(scenario: Scenario, args: dict) -> float:
    return _optimal_beliefs(scenario, args["observer"])[-1]


def _compute_observer_disagreement(scenario: Scenario, args: dict) -> float:
    """Widest gap between the two observers along the optimal path.

    A scenario where this is near zero cannot say anything about whether
    the ranking of planners survives an observer who cannot see the room,
    because in that world there is nothing to see.
    """
    informed = _optimal_beliefs(scenario, "geodesic")
    naive = _optimal_beliefs(scenario, "straight_line")
    return max(abs(a - b) for a, b in zip(informed, naive))


def _compare_value(computed, prop: Property) -> tuple[bool, str]:
    if prop.value is None:
        raise PropertyError(
            f"property {prop.kind!r} carries a computed value but none is "
            f"recorded; run tools/verify_scenarios.py --write to record it"
        )
    if isinstance(computed, int) and not isinstance(computed, bool):
        ok = computed == prop.value
        return ok, f"recorded {prop.value}, computed {computed}"
    delta = abs(float(computed) - float(prop.value))
    return delta <= TOLERANCE, (
        f"recorded {prop.value!r}, computed {computed!r}, difference {delta:.3e}"
    )


def _compare_at_least(computed, prop: Property) -> tuple[bool, str]:
    threshold = float(prop.args["threshold"])
    return computed >= threshold, f"computed {computed!r}, threshold {threshold!r}"


def _compare_at_most(computed, prop: Property) -> tuple[bool, str]:
    threshold = float(prop.args["threshold"])
    return computed <= threshold, f"computed {computed!r}, threshold {threshold!r}"


def _describe_path(prop: Property) -> str:
    return f"{prop.kind} from {prop.args['from']} to {prop.args['to']}"


def _describe_threshold(prop: Property) -> str:
    return f"{prop.kind} {prop.args['threshold']}"


def _describe_belief(prop: Property) -> str:
    where = prop.args.get("until_fraction")
    span = f" over the first {where:g} of the path" if where is not None else ""
    return (
        f"{prop.kind} {prop.args['threshold']} "
        f"to the {prop.args['observer']} observer{span}"
    )


_KINDS: dict[str, Kind] = {}


def _register(kind: Kind) -> None:
    _KINDS[kind.name] = kind


_register(
    Kind(
        name="geodesic_cost",
        required_args=frozenset({"from", "to"}),
        carries_value=True,
        compute=_compute_geodesic_cost,
        compare=_compare_value,
        describes=_describe_path,
    )
)
_register(
    Kind(
        name="geodesic_keep_out_entries",
        required_args=frozenset({"from", "to"}),
        carries_value=True,
        compute=_compute_keep_out_entries,
        compare=_compare_value,
        describes=_describe_path,
    )
)
_register(
    Kind(
        name="geodesic_min_clearance",
        required_args=frozenset({"from", "to"}),
        carries_value=True,
        compute=_compute_min_clearance,
        compare=_compare_value,
        describes=_describe_path,
    )
)
_register(
    Kind(
        name="goal_separation_at_least",
        required_args=frozenset({"threshold"}),
        carries_value=False,
        compute=_compute_goal_separation,
        compare=_compare_at_least,
        describes=_describe_threshold,
    )
)
_register(
    Kind(
        name="goal_cost_spread_at_most",
        required_args=frozenset({"threshold"}),
        carries_value=False,
        compute=_compute_goal_cost_spread,
        compare=_compare_at_most,
        describes=_describe_threshold,
    )
)


_register(
    Kind(
        name="optimal_path_early_belief_at_most",
        required_args=frozenset({"observer", "until_fraction", "threshold"}),
        carries_value=False,
        compute=_compute_early_belief,
        compare=_compare_at_most,
        describes=_describe_belief,
    )
)
_register(
    Kind(
        name="optimal_path_early_belief_at_least",
        required_args=frozenset({"observer", "until_fraction", "threshold"}),
        carries_value=False,
        compute=_compute_early_belief,
        compare=_compare_at_least,
        describes=_describe_belief,
    )
)
_register(
    Kind(
        name="optimal_path_final_belief_at_least",
        required_args=frozenset({"observer", "threshold"}),
        carries_value=False,
        compute=_compute_final_belief,
        compare=_compare_at_least,
        describes=_describe_belief,
    )
)
_register(
    Kind(
        name="optimal_path_final_belief_at_most",
        required_args=frozenset({"observer", "threshold"}),
        carries_value=False,
        compute=_compute_final_belief,
        compare=_compare_at_most,
        describes=_describe_belief,
    )
)
_register(
    Kind(
        name="observer_disagreement_at_least",
        required_args=frozenset({"threshold"}),
        carries_value=False,
        compute=_compute_observer_disagreement,
        compare=_compare_at_least,
        describes=_describe_threshold,
    )
)
_register(
    Kind(
        name="observer_disagreement_at_most",
        required_args=frozenset({"threshold"}),
        carries_value=False,
        compute=_compute_observer_disagreement,
        compare=_compare_at_most,
        describes=_describe_threshold,
    )
)


def registered_kinds() -> tuple[str, ...]:
    return tuple(sorted(_KINDS))


def _kind_for(prop: Property) -> Kind:
    try:
        kind = _KINDS[prop.kind]
    except KeyError:
        raise PropertyError(
            f"unknown property kind {prop.kind!r}; this build implements "
            f"{list(registered_kinds())}"
        ) from None
    args = set(prop.args)
    missing = kind.required_args - args
    if missing:
        raise PropertyError(f"property {prop.kind!r} is missing args {sorted(missing)}")
    unknown = args - kind.required_args
    if unknown:
        raise PropertyError(f"property {prop.kind!r} has unknown args {sorted(unknown)}")
    if not kind.carries_value and prop.value is not None:
        raise PropertyError(
            f"property {prop.kind!r} is checked against a threshold and must "
            f"not record a value, found {prop.value!r}"
        )
    return kind


def kind_for(prop: Property) -> Kind:
    """Resolve and validate the registered kind a property names."""
    return _kind_for(prop)


def compute(scenario: Scenario, prop: Property):
    """Compute the quantity a property is about, without comparing it."""
    return _kind_for(prop).compute(scenario, prop.args)


def check(scenario: Scenario, prop: Property) -> PropertyResult:
    kind = _kind_for(prop)
    computed = kind.compute(scenario, prop.args)
    ok, detail = kind.compare(computed, prop)
    return PropertyResult(
        kind=prop.kind,
        ok=ok,
        computed=computed,
        expected=kind.describes(prop),
        detail=detail,
    )


def check_all(scenario: Scenario) -> tuple[PropertyResult, ...]:
    return tuple(check(scenario, prop) for prop in scenario.properties)

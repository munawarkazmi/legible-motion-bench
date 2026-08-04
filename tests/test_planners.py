import json
from pathlib import Path

import pytest

from legible_motion_bench import metrics, world
from legible_motion_bench.observer import Observer, default_observers
from legible_motion_bench.planners import Plan, PlannerError, ShortestPathPlanner
from legible_motion_bench.planners.base import pinned_endpoints

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ["open_two_goals", "pillar_two_goals", "wall_detour"]


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


@pytest.mark.parametrize("name", NAMES)
def test_shortest_path_is_feasible_and_costs_exactly_one(name):
    scenario_ = scenario(name)
    plan = ShortestPathPlanner().plan(scenario_)
    result = metrics.evaluate(scenario_, Observer(), plan.points)
    assert result.feasible
    assert result.infeasibility == ()
    assert result.cost_ratio == pytest.approx(1.0)


@pytest.mark.parametrize("name", NAMES)
def test_shortest_path_endpoints_are_exact(name):
    scenario_ = scenario(name)
    plan = ShortestPathPlanner().plan(scenario_)
    assert plan.points[0] == scenario_.start
    assert plan.points[-1] == scenario_.true_goal_position


@pytest.mark.parametrize("name", NAMES)
def test_shortest_path_is_deterministic(name):
    scenario_ = scenario(name)
    assert ShortestPathPlanner().plan(scenario_) == ShortestPathPlanner().plan(scenario_)


def test_shortest_path_ignores_keep_out_zones():
    # The baseline is not automatically the safe option, which is what
    # makes the safety columns worth reporting.
    pillar = scenario("pillar_two_goals")
    plan = ShortestPathPlanner().plan(pillar)
    result = metrics.evaluate(pillar, Observer(), plan.points)
    assert result.feasible
    assert result.safety.keep_out_entries == 1
    assert result.safety.keep_out_zone_ids == ("aisle",)


def test_the_baseline_carries_a_legibility_number_worth_beating():
    # Doing nothing about legibility is not the same as being illegible.
    # Recording where the baseline sits stops a later improvement being
    # reported against an imagined floor of zero.
    open_world = scenario("open_two_goals")
    plan = ShortestPathPlanner().plan(open_world)
    informed, naive = metrics.evaluate_all_observers(
        open_world, default_observers(), plan.points
    )
    assert informed.legibility == pytest.approx(0.7165, abs=5e-4)
    assert naive.legibility == pytest.approx(informed.legibility)


def test_plan_records_round_trip_as_json():
    plan = ShortestPathPlanner().plan(scenario("wall_detour"))
    record = plan.as_record()
    assert record["planner"] == "shortest_path"
    assert record["scenario_id"] == "wall_detour"
    assert record["settings"] == {}
    restored = json.loads(json.dumps(record))
    assert [tuple(p) for p in restored["points"]] == list(plan.points)


def test_pinned_endpoints_overrides_a_drifting_optimiser():
    # An optimiser that lands a millimetre short of the goal must not turn
    # into a failure to reach it, so the endpoints are set rather than
    # trusted. The arrival tolerance is never the thing under test.
    open_world = scenario("open_two_goals")
    drifted = [(1.0000001, 5.0), (4.0, 8.0), (8.999999, 8.0000001)]
    pinned = pinned_endpoints(open_world, drifted)
    assert pinned[0] == open_world.start
    assert pinned[-1] == open_world.true_goal_position
    assert pinned[1] == (4.0, 8.0)
    assert metrics.feasibility(open_world, pinned) == ()


def test_a_plan_needs_at_least_two_points():
    with pytest.raises(PlannerError, match="at least two points"):
        pinned_endpoints(scenario("open_two_goals"), [(1.0, 5.0)])


def test_plan_is_hashable_by_value():
    a = ShortestPathPlanner().plan(scenario("open_two_goals"))
    b = Plan(planner=a.planner, scenario_id=a.scenario_id, points=a.points)
    assert a.points == b.points

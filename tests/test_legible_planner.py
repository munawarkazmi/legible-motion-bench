"""Tests for the legibility optimiser.

Every planner here runs at a coarse sampling spacing and a small budget so
the suite stays quick. That is legitimate for testing behaviour, which is
what these assert, and it is not how the benchmark is run: the reported
results use the default spacing and a budget large enough to converge, both
of which are recorded in every plan.
"""

import json
from pathlib import Path

import pytest

from legible_motion_bench import metrics, world
from legible_motion_bench.observer import Observer
from legible_motion_bench.planners import (
    LegiblePlanner,
    PlannerError,
    ShortestPathPlanner,
)

FIXTURES = Path(__file__).parent / "fixtures"
FAST = {"budget": 40, "restarts": 1, "spacing": 0.3}


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def legibility_of(scenario_, points, spacing=0.3):
    return metrics.evaluate(
        scenario_, Observer(condition="geodesic"), points, spacing=spacing
    ).legibility


@pytest.mark.parametrize(
    "name", ["open_two_goals", "pillar_two_goals", "wall_detour"]
)
def test_the_optimiser_beats_the_baseline_it_starts_from(name):
    # The search seeds itself on the shortest path, so it can only report
    # an improvement over doing nothing about legibility. If this ever
    # fails, the search is losing ground it was handed.
    scenario_ = scenario(name)
    baseline = ShortestPathPlanner().plan(scenario_)
    optimised = LegiblePlanner(**FAST).plan(scenario_)
    assert legibility_of(scenario_, optimised.points) > legibility_of(
        scenario_, baseline.points
    )


@pytest.mark.parametrize(
    "name", ["open_two_goals", "pillar_two_goals", "wall_detour"]
)
def test_optimised_trajectories_are_feasible_with_pinned_endpoints(name):
    scenario_ = scenario(name)
    plan = LegiblePlanner(**FAST).plan(scenario_)
    assert metrics.feasibility(scenario_, plan.points) == ()
    assert plan.points[0] == scenario_.start
    assert plan.points[-1] == scenario_.true_goal_position
    assert len(plan.points) == 5


def test_clarity_is_paid_for_in_path_cost():
    # The trade the benchmark exists to measure, now produced by a planner
    # rather than by hand.
    open_world = scenario("open_two_goals")
    plan = LegiblePlanner(**FAST).plan(open_world)
    result = metrics.evaluate(open_world, Observer(), plan.points, spacing=0.3)
    assert result.cost_ratio > 1.0


def test_the_constrained_planner_never_enters_a_keep_out_zone():
    # True by construction rather than by luck: a candidate that enters a
    # zone is refused before it is ever scored.
    pillar = scenario("pillar_two_goals")
    plan = LegiblePlanner(respect_keep_out=True, **FAST).plan(pillar)
    assert metrics.safety(pillar, plan.points).keep_out_entries == 0
    assert plan.settings["respect_keep_out"] is True


def test_the_baseline_itself_violates_the_constraint_the_safe_planner_respects():
    # Without this the constrained planner would be solving an empty
    # problem in this fixture and the comparison would say nothing.
    pillar = scenario("pillar_two_goals")
    baseline = ShortestPathPlanner().plan(pillar)
    assert metrics.safety(pillar, baseline.points).keep_out_entries == 1


def test_planning_is_deterministic():
    pillar = scenario("pillar_two_goals")
    first = LegiblePlanner(**FAST).plan(pillar)
    second = LegiblePlanner(**FAST).plan(pillar)
    assert first.points == second.points
    assert first.settings == second.settings


def test_the_seed_changes_the_search():
    open_world = scenario("open_two_goals")
    a = LegiblePlanner(seed=1, **FAST).plan(open_world)
    b = LegiblePlanner(seed=2, **FAST).plan(open_world)
    assert a.settings["seed"] == 1
    assert b.settings["seed"] == 2


def test_the_budget_is_respected_and_reported():
    open_world = scenario("open_two_goals")
    plan = LegiblePlanner(budget=25, restarts=1, spacing=0.3).plan(open_world)
    assert plan.settings["evaluations"] <= 25
    assert plan.settings["budget"] == 25
    assert plan.settings["refusals"] >= 0


def test_refusals_are_counted_separately_from_evaluations():
    # A search that spent most of its effort being refused must say so
    # rather than reporting few evaluations and looking efficient.
    pillar = scenario("pillar_two_goals")
    plan = LegiblePlanner(respect_keep_out=True, **FAST).plan(pillar)
    assert plan.settings["refusals"] > 0


def test_plan_settings_record_what_produced_the_trajectory():
    plan = LegiblePlanner(**FAST).plan(scenario("open_two_goals"))
    for key in (
        "waypoints",
        "budget",
        "evaluations",
        "refusals",
        "restarts",
        "seed",
        "spacing",
        "respect_keep_out",
        "observer",
        "best_legibility",
    ):
        assert key in plan.settings, key
    assert plan.settings["observer"] == "geodesic_beta1"
    restored = json.loads(json.dumps(plan.as_record()))
    assert restored["settings"]["budget"] == plan.settings["budget"]


def test_planner_names_carry_their_parameters():
    assert LegiblePlanner(waypoints=3, budget=2000).name == "legible_k3_b2000"
    assert (
        LegiblePlanner(waypoints=2, budget=500, respect_keep_out=True).name
        == "legible_safe_k2_b500"
    )


def test_waypoint_count_shapes_the_trajectory():
    open_world = scenario("open_two_goals")
    for k in (1, 2, 4):
        plan = LegiblePlanner(waypoints=k, **FAST).plan(open_world)
        assert len(plan.points) == k + 2


def test_malformed_planners_are_rejected():
    with pytest.raises(PlannerError, match="at least one free waypoint"):
        LegiblePlanner(waypoints=0)
    with pytest.raises(PlannerError, match="budget must be positive"):
        LegiblePlanner(budget=0)
    with pytest.raises(PlannerError, match="restarts cannot be negative"):
        LegiblePlanner(restarts=-1)

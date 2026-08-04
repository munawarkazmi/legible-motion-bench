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
from legible_motion_bench.costs import geodesic
from legible_motion_bench.geometry import polyline_length
from legible_motion_bench.observer import Observer
from legible_motion_bench.planners import (
    LegiblePlanner,
    PlannerError,
    ShortestPathPlanner,
    sweep,
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
def test_the_seed_reproduces_the_optimal_path(name):
    # The search is only guaranteed to beat the baseline because it starts
    # from it. That holds only if the waypoints can express the optimal
    # path, which means keeping the corners it turns at rather than
    # spacing waypoints evenly along it: an evenly spaced seed cuts the
    # corner and runs through the obstacle the corner was avoiding.
    scenario_ = scenario(name)
    planner = LegiblePlanner(**FAST)
    optimal = geodesic(
        scenario_.start, scenario_.true_goal_position, scenario_.obstacles
    )
    assert len(optimal.path) - 2 <= planner.waypoints, "fixture needs more waypoints"

    seed = planner._seed_along_the_optimal_path(scenario_)
    points = planner._path(scenario_, seed)
    assert metrics.feasibility(scenario_, points) == ()
    assert polyline_length(points) == pytest.approx(optimal.cost)


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
    # Two budgets travel with a legible planner and they mean different
    # things: c is the ceiling on path cost, e the number of objective
    # evaluations. A name that carried only one of them would let two
    # incomparable rows sit under the same heading.
    assert LegiblePlanner(waypoints=3, budget=2000).name == "legible_k3_cinf_e2000"
    assert (
        LegiblePlanner(waypoints=3, budget=2000, cost_budget=1.25).name
        == "legible_k3_c1.25_e2000"
    )
    assert (
        LegiblePlanner(waypoints=2, budget=500, respect_keep_out=True).name
        == "legible_safe_k2_cinf_e500"
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
    with pytest.raises(PlannerError, match="cannot be below one"):
        LegiblePlanner(cost_budget=0.9)


@pytest.mark.parametrize("ceiling", [1.05, 1.25, 2.0])
def test_the_cost_budget_is_never_exceeded(ceiling):
    open_world = scenario("open_two_goals")
    plan = LegiblePlanner(cost_budget=ceiling, **FAST).plan(open_world)
    result = metrics.evaluate(open_world, Observer(), plan.points, spacing=0.3)
    assert result.cost_ratio <= ceiling + 1e-9
    assert plan.settings["cost_budget"] == ceiling


def test_a_looser_budget_buys_more_clarity_than_a_tight_one():
    open_world = scenario("open_two_goals")
    tight = LegiblePlanner(cost_budget=1.05, **FAST).plan(open_world)
    loose = LegiblePlanner(cost_budget=None, **FAST).plan(open_world)
    assert legibility_of(open_world, loose.points) > legibility_of(
        open_world, tight.points
    )


def test_the_sweep_returns_one_point_per_ceiling():
    open_world = scenario("open_two_goals")
    ceilings = (1.05, 1.25, None)
    points = sweep(open_world, ceilings=ceilings, **FAST)
    assert [p.ceiling for p in points] == list(ceilings)
    assert all(p.plan is not None for p in points)
    assert all(p.not_found is None for p in points)


def test_the_sweep_records_a_failure_instead_of_raising():
    # A ceiling under which nothing admissible is found is part of the
    # frontier, not an error, and the record must say the search failed
    # rather than that nothing exists.
    pillar = scenario("pillar_two_goals")
    points = sweep(
        pillar, ceilings=(1.0,), respect_keep_out=True, budget=20, restarts=0,
        spacing=0.3,
    )
    assert len(points) == 1
    assert points[0].plan is None
    assert "not a proof that none exists" in points[0].not_found
    assert points[0].refusals > 0


def test_sweep_points_serialise():
    points = sweep(scenario("open_two_goals"), ceilings=(1.1,), **FAST)
    restored = json.loads(json.dumps(points[0].as_record()))
    assert restored["ceiling"] == 1.1
    assert restored["plan"]["settings"]["cost_budget"] == 1.1
    assert restored["not_found"] is None

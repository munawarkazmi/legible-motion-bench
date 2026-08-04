import json
import random
from math import hypot, inf
from pathlib import Path

import pytest

from legible_motion_bench import metrics, world
from legible_motion_bench.costs import geodesic
from legible_motion_bench.geometry import polyline_length
from legible_motion_bench.observer import Observer, default_observers

FIXTURES = Path(__file__).parent / "fixtures"


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def optimal_path(scenario_):
    return list(
        geodesic(
            scenario_.start, scenario_.true_goal_position, scenario_.obstacles
        ).path
    )


# Hand-built trajectories in the obstacle-free world. All three reach the
# true goal at (9, 8); they differ only in how early they commit to it.
DIRECT = [(1.0, 5.0), (9.0, 8.0)]
LEGIBLE = [(1.0, 5.0), (4.0, 8.5), (9.0, 8.0)]
OVERSHOOT = [(1.0, 5.0), (3.0, 9.5), (9.0, 8.0)]
WRONG_WAY = [(1.0, 5.0), (4.0, 2.0), (9.0, 8.0)]


def test_resample_hits_both_ends_and_respects_the_spacing():
    path = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
    samples = metrics.resample(path, 0.5)
    assert samples[0] == (0.0, 0.0)
    assert samples[-1] == (3.0, 4.0)
    gaps = [
        hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(samples, samples[1:])
    ]
    assert max(gaps) <= 0.5 + 1e-12
    assert polyline_length(samples) == pytest.approx(7.0)


def test_resample_is_deterministic_and_sample_count_follows_length():
    short = metrics.resample([(0.0, 0.0), (1.0, 0.0)], 0.1)
    long = metrics.resample([(0.0, 0.0), (2.0, 0.0)], 0.1)
    assert len(long) > len(short)
    assert metrics.resample([(0.0, 0.0), (1.0, 0.0)], 0.1) == short


def test_resample_rejects_what_it_cannot_sample():
    with pytest.raises(metrics.MetricError, match="spacing must be positive"):
        metrics.resample([(0.0, 0.0), (1.0, 0.0)], 0.0)
    with pytest.raises(metrics.MetricError, match="at least two points"):
        metrics.resample([(0.0, 0.0)], 0.1)
    with pytest.raises(metrics.MetricError, match="zero length"):
        metrics.resample([(1.0, 1.0), (1.0, 1.0)], 0.1)


def test_the_optimal_path_is_feasible_in_every_fixture():
    for name in ("open_two_goals", "pillar_two_goals", "wall_detour"):
        scenario_ = scenario(name)
        assert metrics.feasibility(scenario_, optimal_path(scenario_)) == ()


def test_crossing_a_keep_out_zone_is_not_infeasibility():
    # The whole frontier depends on this distinction. A trajectory that
    # crosses a keep-out zone is scored for it and still receives a
    # legibility number; if it were infeasible there would be nothing to
    # trade off against.
    pillar = scenario("pillar_two_goals")
    path = optimal_path(pillar)
    assert metrics.feasibility(pillar, path) == ()
    assert metrics.safety(pillar, path).keep_out_entries == 1
    assert metrics.evaluate(pillar, Observer(), path).legibility is not None


def test_infeasibility_reasons_are_specific():
    pillar = scenario("pillar_two_goals")
    through = metrics.feasibility(pillar, [(1.0, 5.0), (11.0, 8.0), (6.0, 5.0)])
    assert any("interior of obstacle 'pillar'" in r for r in through)
    wrong_start = metrics.feasibility(pillar, [(2.0, 5.0), (11.0, 8.0)])
    assert any("starts at" in r for r in wrong_start)
    short = metrics.feasibility(pillar, [(1.0, 5.0), (9.0, 7.0)])
    assert any("rather than at the true goal" in r for r in short)
    assert metrics.feasibility(pillar, [(1.0, 5.0)])[0].startswith("has 1 point")


def test_safety_matches_the_facts_the_scenario_carries():
    pillar = scenario("pillar_two_goals")
    to_true = metrics.safety(pillar, optimal_path(pillar))
    assert to_true.keep_out_entries == 1
    assert to_true.keep_out_zone_ids == ("aisle",)
    assert to_true.enters_keep_out
    assert to_true.min_clearance == pytest.approx(0.1915652570442301)

    to_other = metrics.safety(
        pillar, list(geodesic(pillar.start, pillar.goal("B").position, pillar.obstacles).path)
    )
    assert to_other.keep_out_entries == 0
    assert not to_other.enters_keep_out


def test_clearance_is_not_a_number_where_there_are_no_obstacles():
    open_world = scenario("open_two_goals")
    assert metrics.safety(open_world, DIRECT).min_clearance == inf
    assert "none" in metrics.summarise([metrics.evaluate(open_world, Observer(), DIRECT)])


def test_an_infeasible_trajectory_carries_no_legibility_and_no_cost_ratio():
    pillar = scenario("pillar_two_goals")
    through_the_wall = [(1.0, 5.0), (11.0, 5.0)]
    result = metrics.evaluate(pillar, Observer(), through_the_wall)
    assert not result.feasible
    assert result.legibility is None
    assert result.cost_ratio is None
    assert len(result.infeasibility) == 2
    # The raw lengths survive so the row stays auditable, but neither is
    # turned into a ratio that would flatter a trajectory for stopping
    # short of the goal.
    assert result.path_cost == pytest.approx(10.0)
    assert result.optimal_cost == pytest.approx(10.44030650891055)
    assert "violation" in metrics.summarise([result])


def test_the_optimal_path_has_a_cost_ratio_of_one():
    for name in ("open_two_goals", "pillar_two_goals", "wall_detour"):
        scenario_ = scenario(name)
        result = metrics.evaluate(scenario_, Observer(), optimal_path(scenario_))
        assert result.cost_ratio == pytest.approx(1.0)


def test_legibility_lies_in_the_unit_interval():
    open_world = scenario("open_two_goals")
    rng = random.Random(20260804)
    for _ in range(30):
        waypoint = (rng.uniform(1.5, 8.5), rng.uniform(0.5, 9.5))
        result = metrics.evaluate(
            open_world, Observer(), [(1.0, 5.0), waypoint, (9.0, 8.0)]
        )
        assert 0.0 <= result.legibility <= 1.0


def test_deviating_early_towards_the_true_goal_buys_clarity_and_costs_path():
    # The trade the benchmark exists to measure, on trajectories built by
    # hand so the relationship is not an artefact of any planner.
    open_world = scenario("open_two_goals")
    direct, legible, overshoot = (
        metrics.evaluate(open_world, Observer(), p)
        for p in (DIRECT, LEGIBLE, OVERSHOOT)
    )
    assert direct.legibility < legible.legibility < overshoot.legibility
    assert direct.cost_ratio < legible.cost_ratio < overshoot.cost_ratio
    assert direct.time_to_confidence > legible.time_to_confidence
    assert legible.time_to_confidence > overshoot.time_to_confidence
    # Diminishing returns: the second deviation buys less clarity per unit
    # of path than the first.
    first = (legible.legibility - direct.legibility) / (
        legible.cost_ratio - direct.cost_ratio
    )
    second = (overshoot.legibility - legible.legibility) / (
        overshoot.cost_ratio - legible.cost_ratio
    )
    assert second < first


def test_deviating_towards_the_wrong_goal_is_punished_on_both_axes():
    open_world = scenario("open_two_goals")
    direct = metrics.evaluate(open_world, Observer(), DIRECT)
    wrong = metrics.evaluate(open_world, Observer(), WRONG_WAY)
    assert wrong.legibility < direct.legibility
    assert wrong.cost_ratio > direct.cost_ratio
    assert wrong.time_to_confidence > direct.time_to_confidence


def test_the_two_observers_agree_exactly_when_there_is_nothing_to_see():
    # No obstacles means the geodesic is the straight line, so the two
    # conditions must coincide. If they ever drift apart here, one of the
    # two cost models has stopped being what it claims to be.
    open_world = scenario("open_two_goals")
    informed, naive = metrics.evaluate_all_observers(
        open_world, default_observers(), LEGIBLE
    )
    assert informed.legibility == naive.legibility
    assert informed.time_to_confidence == naive.time_to_confidence


def test_the_two_observers_differ_once_there_is_an_obstacle():
    pillar = scenario("pillar_two_goals")
    informed, naive = metrics.evaluate_all_observers(
        pillar, default_observers(), optimal_path(pillar)
    )
    assert informed.legibility > naive.legibility
    assert informed.time_to_confidence < naive.time_to_confidence
    assert informed.cost_ratio == naive.cost_ratio
    assert informed.safety == naive.safety


def test_time_to_confidence_is_none_rather_than_late_when_it_never_arrives():
    # A threshold the belief never reaches must not be recorded as a large
    # number, because a large number reads as "arrived late" and this is
    # "did not arrive".
    open_world = scenario("open_two_goals")
    result = metrics.evaluate(open_world, Observer(), DIRECT, threshold=1.0)
    assert result.time_to_confidence is None
    assert "never" in metrics.summarise([result])


def test_a_stricter_threshold_never_brings_confidence_forward():
    open_world = scenario("open_two_goals")
    times = [
        metrics.evaluate(open_world, Observer(), LEGIBLE, threshold=t).time_to_confidence
        for t in (0.6, 0.8, 0.95)
    ]
    assert times[0] <= times[1] <= times[2]


def test_time_to_confidence_is_measured_in_time_not_in_samples():
    # Halving the speed doubles the time to confidence, because the robot
    # covers the same path more slowly. A metric that counted samples
    # would not move at all.
    open_world = scenario("open_two_goals")
    fast = metrics.evaluate(open_world, Observer(), LEGIBLE, speed=1.0)
    slow = metrics.evaluate(open_world, Observer(), LEGIBLE, speed=0.5)
    assert slow.time_to_confidence == pytest.approx(2 * fast.time_to_confidence)
    assert slow.duration == pytest.approx(2 * fast.duration)
    assert slow.legibility == pytest.approx(fast.legibility)


def test_finer_sampling_does_not_move_the_metrics_much():
    open_world = scenario("open_two_goals")
    coarse = metrics.evaluate(open_world, Observer(), LEGIBLE, spacing=0.1)
    fine = metrics.evaluate(open_world, Observer(), LEGIBLE, spacing=0.01)
    assert fine.legibility == pytest.approx(coarse.legibility, abs=5e-3)
    assert fine.samples > coarse.samples


def test_malformed_measurement_settings_are_rejected():
    open_world = scenario("open_two_goals")
    with pytest.raises(metrics.MetricError, match="speed must be positive"):
        metrics.evaluate(open_world, Observer(), DIRECT, speed=0.0)
    with pytest.raises(metrics.MetricError, match="threshold must lie"):
        metrics.evaluate(open_world, Observer(), DIRECT, threshold=0.0)
    with pytest.raises(metrics.MetricError, match="threshold must lie"):
        metrics.evaluate(open_world, Observer(), DIRECT, threshold=1.5)


def test_a_record_always_carries_cost_and_safety_beside_legibility():
    # Enforced structurally: there is no way to obtain a legibility number
    # from this module without the columns it must be read against.
    open_world = scenario("open_two_goals")
    record = metrics.evaluate(open_world, Observer(), LEGIBLE).as_record()
    for key in ("legibility", "cost_ratio", "path_cost", "optimal_cost", "safety"):
        assert key in record
    for key in ("keep_out_entries", "min_clearance", "enters_keep_out"):
        assert key in record["safety"]
    assert record["observer"] == "geodesic_beta1"
    assert json.loads(json.dumps(record))["legibility"] == record["legibility"]


def test_summarise_handles_an_empty_run():
    assert metrics.summarise([]) == "no trajectories scored\n"

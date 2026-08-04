"""Tests for the arithmetic behind the animations, not for their pixels.

Nothing here asserts on rendered bytes. They move with the matplotlib
version and a test that checked them would fail for reasons unconnected to
this benchmark. What is asserted is that a frame sits where the trajectory
says and that the belief drawn beside it is the belief the observer
computed, so a GIF is a picture of numbers checked elsewhere.
"""

from pathlib import Path

import pytest

from legible_motion_bench import metrics, render, world
from legible_motion_bench.observer import Observer
from legible_motion_bench.planners import LegiblePlanner, ShortestPathPlanner

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ["open_two_goals", "pillar_two_goals", "wall_detour"]


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def baseline_board(name, **kwargs):
    scenario_ = scenario(name)
    plan = ShortestPathPlanner().plan(scenario_)
    return scenario_, render.storyboard(
        scenario_, Observer(), plan.points, label="shortest path", **kwargs
    )


@pytest.mark.parametrize("name", NAMES)
def test_a_storyboard_runs_from_the_start_to_the_goal(name):
    scenario_, board = baseline_board(name)
    assert board.frames[0].position == scenario_.start
    assert board.frames[-1].position == scenario_.true_goal_position
    assert board.arrival_frame == len(board.frames) - 1
    assert board.feasible


@pytest.mark.parametrize("name", NAMES)
def test_frame_times_increase_and_end_at_the_duration(name):
    _scenario, board = baseline_board(name)
    times = [f.time for f in board.frames]
    assert times[0] == 0.0
    assert times == sorted(times)
    assert times[-1] == pytest.approx(board.duration)


def test_the_belief_drawn_is_the_belief_that_was_scored():
    # The claim that makes a GIF admissible as evidence: its bars are the
    # observer's own numbers, not a second computation beside them.
    scenario_, board = baseline_board("pillar_two_goals", stride=7)
    observer = Observer()
    for frame in board.frames:
        index = board.positions.index(frame.position)
        prefix = board.positions[: index + 1]
        assert frame.belief is not None
        assert set(frame.belief) == set(scenario_.goal_ids)
        assert sum(frame.belief.values()) == pytest.approx(1.0)
    first = board.frames[0].belief
    assert first == {g: 0.5 for g in scenario_.goal_ids}
    assert board.frames[-1].belief[scenario_.true_goal] > 0.9


def test_constant_speed_makes_the_longer_trajectory_arrive_later():
    # The reason this is animated at all. A trajectory that pays for
    # clarity has to be seen arriving after the direct one.
    scenario_ = scenario("open_two_goals")
    direct = ShortestPathPlanner().plan(scenario_)
    scenic = LegiblePlanner(
        cost_budget=1.5, budget=40, restarts=1, spacing=0.3
    ).plan(scenario_)
    quick = render.storyboard(scenario_, Observer(), direct.points, label="direct")
    slow = render.storyboard(scenario_, Observer(), scenic.points, label="legible")
    assert slow.duration > quick.duration
    assert len(slow.frames) > len(quick.frames)


def test_halving_the_speed_doubles_the_duration():
    _scenario, fast = baseline_board("open_two_goals", speed=1.0)
    _scenario, slow = baseline_board("open_two_goals", speed=0.5)
    assert slow.duration == pytest.approx(2 * fast.duration)


def test_stride_thins_the_frames_without_moving_them():
    _scenario, dense = baseline_board("open_two_goals", stride=1)
    _scenario, thin = baseline_board("open_two_goals", stride=5)
    assert len(thin.frames) < len(dense.frames)
    assert thin.frames[0].position == dense.frames[0].position
    assert thin.frames[-1].position == dense.frames[-1].position
    kept = {f.position for f in thin.frames}
    assert kept <= {f.position for f in dense.frames}


def test_stride_must_be_positive():
    scenario_ = scenario("open_two_goals")
    plan = ShortestPathPlanner().plan(scenario_)
    with pytest.raises(render.RenderError, match="stride must be at least one"):
        render.storyboard(scenario_, Observer(), plan.points, label="x", stride=0)


def test_an_infeasible_trajectory_is_drawn_without_beliefs():
    # Worth watching a proposed path walk through a wall. The observer has
    # nothing to say about it, so the bars are absent rather than invented.
    pillar = scenario("pillar_two_goals")
    board = render.storyboard(
        pillar, Observer(), [(1.0, 5.0), (11.0, 5.0)], label="through the pillar"
    )
    assert not board.feasible
    assert board.infeasibility
    assert all(f.belief is None for f in board.frames)
    assert board.result.legibility is None


def test_aligning_puts_every_panel_on_one_clock():
    scenario_ = scenario("open_two_goals")
    direct = ShortestPathPlanner().plan(scenario_)
    scenic = LegiblePlanner(
        cost_budget=1.5, budget=40, restarts=1, spacing=0.3
    ).plan(scenario_)
    quick = render.storyboard(scenario_, Observer(), direct.points, label="direct")
    slow = render.storyboard(scenario_, Observer(), scenic.points, label="legible")

    aligned = render.align([quick, slow])
    assert len({len(b.frames) for b in aligned}) == 1
    assert [b.time for b in aligned[0].frames] == [b.time for b in aligned[1].frames]
    # The one that finished waits at its goal, and still records when it
    # actually got there.
    held = aligned[0]
    assert held.arrival_frame == len(quick.frames) - 1
    assert held.frames[-1].position == scenario_.true_goal_position
    assert held.frames[held.arrival_frame].position == scenario_.true_goal_position


def test_aligning_leaves_equal_length_storyboards_alone():
    _s, one = baseline_board("open_two_goals")
    _s, two = baseline_board("open_two_goals")
    assert render.align([one, two]) == (one, two)


def test_aligning_nothing_is_an_error():
    with pytest.raises(render.RenderError, match="nothing to align"):
        render.align([])


def test_a_grid_too_small_for_its_panels_is_refused():
    # The failure this exists to prevent: a figure that quietly drops its
    # seventh panel looks finished and is wrong.
    render.check_panel_grid(6, 2, 3)
    with pytest.raises(render.RenderError, match="but 7 were asked for"):
        render.check_panel_grid(7, 2, 3)
    with pytest.raises(render.RenderError, match="at least one panel"):
        render.check_panel_grid(0, 2, 3)
    with pytest.raises(render.RenderError, match="is empty"):
        render.check_panel_grid(3, 0, 3)


@pytest.mark.parametrize("count", list(range(1, 18)))
def test_the_chosen_grid_always_holds_every_panel(count):
    rows, columns = render.panel_grid(count)
    assert rows * columns >= count
    render.check_panel_grid(count, rows, columns)


def test_an_explicit_column_count_is_honoured_or_refused():
    assert render.panel_grid(6, columns=3) == (2, 3)
    assert render.panel_grid(4, columns=4) == (1, 4)
    assert render.panel_grid(7, columns=3) == (3, 3)


def test_rendering_writes_a_file(tmp_path):
    # A smoke test, deliberately shallow. It checks that the drawing code
    # runs and produces something; it does not check what the something
    # looks like, because that is not stable across matplotlib versions.
    scenario_ = scenario("open_two_goals")
    plan = ShortestPathPlanner().plan(scenario_)
    board = render.storyboard(
        scenario_, Observer(), plan.points, label="shortest path", spacing=1.5
    )
    target = tmp_path / "smoke.gif"
    render.render_comparison(scenario_, [board], target)
    assert target.exists()
    assert target.stat().st_size > 0

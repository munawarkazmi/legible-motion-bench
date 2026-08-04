"""The scenario suite, and whether it covers what it says it covers.

Two kinds of check live here. The first is that every fact a scenario
carries still holds, which is also what CI runs directly. The second is
about the suite as a whole: a benchmark made only of worlds where clarity
is cheap, or only of worlds with obstacles, would produce clean numbers
that answer none of the questions it was built for. Those are cross
scenario claims and cannot be scenario properties, so they are asserted
here instead.
"""

from pathlib import Path

import pytest

from legible_motion_bench import properties, world
from legible_motion_bench.costs import geodesic
from legible_motion_bench.world import Property

SUITE = Path(__file__).resolve().parents[1] / "scenarios"

EXPECTED = (
    "door_pair",
    "fan_middle",
    "fan_outer",
    "keep_out_shortcut",
    "narrow_gap",
    "open_pair",
    "pillar_aisle",
    "wall_choice",
)


@pytest.fixture(scope="module")
def suite():
    return world.load_directory(SUITE)


def compute(scenario, kind, args):
    return properties.compute(scenario, Property(kind, args, None))


def final_belief(scenario, condition="geodesic"):
    return compute(
        scenario,
        "optimal_path_final_belief_at_least",
        {"observer": condition, "threshold": 0.0},
    )


def test_the_suite_is_the_one_that_is_documented(suite):
    assert tuple(s.id for s in suite) == EXPECTED


def test_every_scenario_carries_facts_and_they_hold(suite):
    for scenario in suite:
        results = properties.check_all(scenario)
        assert results, f"{scenario.id} asserts nothing about itself"
        failed = [r for r in results if not r.ok]
        assert not failed, (scenario.id, failed)


def test_the_suite_spans_early_ambiguity(suite):
    # A suite of uniformly ambiguous worlds cannot show whether a planner
    # wastes path where clarity is already free, and one of uniformly easy
    # worlds cannot show whether it buys clarity where it is not.
    early = {
        s.id: compute(
            s,
            "optimal_path_early_belief_at_most",
            {"observer": "geodesic", "until_fraction": 0.4, "threshold": 1.0},
        )
        for s in suite
    }
    assert min(early.values()) < 0.45, early
    assert max(early.values()) > 0.75, early


def test_the_suite_contains_both_kinds_of_keep_out_world(suite):
    # One where the cheapest route already violates, so safety costs
    # something before legibility is asked for, and one where it does not,
    # so the constraint only bites once a planner tries to be clear.
    entries = {
        s.id: compute(
            s,
            "geodesic_keep_out_entries",
            {"from": "start", "to": s.true_goal},
        )
        for s in suite
        if s.keep_out_zones
    }
    assert len(entries) >= 2, entries
    assert any(count > 0 for count in entries.values()), entries
    assert any(count == 0 for count in entries.values()), entries


def test_the_suite_separates_the_two_observers_somewhere_and_nowhere(suite):
    disagreement = {
        s.id: compute(s, "observer_disagreement_at_least", {"threshold": 0.0})
        for s in suite
    }
    # Worlds with no obstacles must give the two observers nothing to
    # disagree about, which is the control on the observer model itself.
    for scenario in suite:
        if not scenario.obstacles:
            assert disagreement[scenario.id] == pytest.approx(0.0), scenario.id
    assert max(disagreement.values()) > 0.15, disagreement


def test_the_suite_contains_a_world_where_the_optimal_path_must_turn(suite):
    corners = {
        s.id: len(
            geodesic(s.start, s.true_goal_position, s.obstacles).path
        )
        - 2
        for s in suite
    }
    assert max(corners.values()) >= 2, corners


def test_the_suite_contains_more_than_two_goals_somewhere(suite):
    assert max(len(s.goals) for s in suite) >= 3


def test_a_middle_goal_is_harder_to_convey_than_an_outer_one(suite):
    # The paired comparison the two fan scenarios exist for. They share
    # their geometry exactly and differ only in which goal is true, so the
    # difference cannot come from the scene. Dragan and Srinivasa note that
    # for a goal in the middle, exaggeration points at a different goal and
    # legibility is limited by the complexity of the scene.
    scenarios = {s.id: s for s in suite}
    middle = final_belief(scenarios["fan_middle"])
    outer = final_belief(scenarios["fan_outer"])
    assert middle < outer
    assert scenarios["fan_middle"].goals == scenarios["fan_outer"].goals
    assert scenarios["fan_middle"].start == scenarios["fan_outer"].start


def test_the_clearance_column_is_only_informative_without_corners(suite):
    # Worth asserting because it is a limitation, not a bug. A shortest
    # path that rounds an obstacle touches its corner, so its minimum
    # clearance is exactly zero, and the clearance column says nothing in
    # such a world. narrow_gap exists so the column has somewhere to speak.
    scenarios = {s.id: s for s in suite}
    turning = scenarios["wall_choice"]
    assert compute(
        turning, "geodesic_min_clearance", {"from": "start", "to": "A"}
    ) == pytest.approx(0.0)
    straight = scenarios["narrow_gap"]
    assert compute(
        straight, "geodesic_min_clearance", {"from": "start", "to": "A"}
    ) > 0.3

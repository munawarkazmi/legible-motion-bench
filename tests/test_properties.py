from math import sqrt
from pathlib import Path

import pytest

from legible_motion_bench import properties, world
from legible_motion_bench.world import Property

FIXTURES = Path(__file__).parent / "fixtures"


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def test_registry_is_closed_and_pinned():
    # Pinned so that adding a property kind is a deliberate act with a test
    # behind it, rather than something a scenario file can introduce.
    assert properties.registered_kinds() == (
        "geodesic_cost",
        "geodesic_keep_out_entries",
        "geodesic_min_clearance",
        "goal_cost_spread_at_most",
        "goal_separation_at_least",
        "observer_disagreement_at_least",
        "observer_disagreement_at_most",
        "optimal_path_early_belief_at_least",
        "optimal_path_early_belief_at_most",
        "optimal_path_final_belief_at_least",
        "optimal_path_final_belief_at_most",
    )


def test_early_belief_measures_how_long_the_question_stays_open():
    # In wall_detour the optimal paths to both goals share their first leg,
    # so the informed observer learns nothing at all over that stretch and
    # sits at the prior.
    detour = scenario("wall_detour")
    early = properties.compute(
        detour,
        Property(
            "optimal_path_early_belief_at_most",
            {"observer": "geodesic", "until_fraction": 0.3, "threshold": 0.0},
            None,
        ),
    )
    assert early == pytest.approx(0.5)
    late = properties.compute(
        detour,
        Property(
            "optimal_path_early_belief_at_most",
            {"observer": "geodesic", "until_fraction": 1.0, "threshold": 0.0},
            None,
        ),
    )
    assert late > 0.95


def test_the_naive_observer_can_be_driven_below_the_prior():
    detour = scenario("wall_detour")
    disagreement = properties.compute(
        detour, Property("observer_disagreement_at_least", {"threshold": 0.0}, None)
    )
    assert disagreement > 0.15


def test_an_open_world_gives_the_two_observers_nothing_to_disagree_about():
    open_world = scenario("open_two_goals")
    disagreement = properties.compute(
        open_world, Property("observer_disagreement_at_most", {"threshold": 1.0}, None)
    )
    assert disagreement == pytest.approx(0.0)


def test_a_malformed_fraction_is_rejected():
    with pytest.raises(properties.PropertyError, match="until_fraction"):
        properties.compute(
            scenario("open_two_goals"),
            Property(
                "optimal_path_early_belief_at_most",
                {"observer": "geodesic", "until_fraction": 0.0, "threshold": 0.5},
                None,
            ),
        )


@pytest.mark.parametrize(
    "name", ["open_two_goals", "pillar_two_goals", "wall_detour"]
)
def test_every_fixture_property_holds(name):
    results = properties.check_all(scenario(name))
    assert results, f"{name} carries no properties"
    failed = [r for r in results if not r.ok]
    assert not failed, failed


def test_recorded_costs_match_hand_computation():
    open_world = scenario("open_two_goals")
    assert properties.compute(
        open_world, Property("geodesic_cost", {"from": "start", "to": "A"}, None)
    ) == pytest.approx(sqrt(8**2 + 3**2))

    detour = scenario("wall_detour")
    assert properties.compute(
        detour, Property("geodesic_cost", {"from": "start", "to": "A"}, None)
    ) == pytest.approx(sqrt(20) + 1.0 + sqrt(29))


def test_the_optimal_path_to_the_true_goal_crosses_the_keep_out_zone():
    # This is the fact the pillar scenario exists to carry: the cheapest
    # path is already unsafe before legibility is asked for.
    pillar = scenario("pillar_two_goals")
    assert properties.compute(
        pillar,
        Property("geodesic_keep_out_entries", {"from": "start", "to": "A"}, None),
    ) == 1
    assert properties.compute(
        pillar,
        Property("geodesic_keep_out_entries", {"from": "start", "to": "B"}, None),
    ) == 0
    assert properties.compute(
        pillar,
        Property("geodesic_min_clearance", {"from": "start", "to": "A"}, None),
    ) == pytest.approx(2.0 / sqrt(109))


def test_unknown_kind_is_an_error():
    with pytest.raises(properties.PropertyError, match="unknown property kind"):
        properties.check(scenario("open_two_goals"), Property("invented", {}, None))


def test_missing_and_unknown_arguments_are_errors():
    open_world = scenario("open_two_goals")
    with pytest.raises(properties.PropertyError, match="missing args"):
        properties.check(open_world, Property("geodesic_cost", {"from": "start"}, None))
    with pytest.raises(properties.PropertyError, match="unknown args"):
        properties.check(
            open_world,
            Property("geodesic_cost", {"from": "start", "to": "A", "via": "B"}, None),
        )


def test_value_carrying_property_without_a_value_is_an_error():
    with pytest.raises(properties.PropertyError, match="none is"):
        properties.check(
            scenario("open_two_goals"),
            Property("geodesic_cost", {"from": "start", "to": "A"}, None),
        )


def test_threshold_property_carrying_a_value_is_an_error():
    with pytest.raises(properties.PropertyError, match="must not record a value"):
        properties.check(
            scenario("open_two_goals"),
            Property("goal_separation_at_least", {"threshold": 1.0}, 6.0),
        )


def test_a_wrong_recorded_value_fails_rather_than_raising():
    result = properties.check(
        scenario("open_two_goals"),
        Property("geodesic_cost", {"from": "start", "to": "A"}, 99.0),
    )
    assert not result.ok
    assert "99.0" in result.detail


def test_thresholds_are_checked_in_the_right_direction():
    open_world = scenario("open_two_goals")
    assert properties.check(
        open_world, Property("goal_separation_at_least", {"threshold": 6.0}, None)
    ).ok
    assert not properties.check(
        open_world, Property("goal_separation_at_least", {"threshold": 6.5}, None)
    ).ok
    assert properties.check(
        open_world, Property("goal_cost_spread_at_most", {"threshold": 0.0}, None)
    ).ok

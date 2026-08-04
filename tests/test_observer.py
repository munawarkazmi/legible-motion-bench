import random
from pathlib import Path

import pytest

from legible_motion_bench import world
from legible_motion_bench.costs import geodesic
from legible_motion_bench.observer import (
    CONDITIONS,
    Observer,
    ObserverError,
    default_observers,
)

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ["open_two_goals", "pillar_two_goals", "wall_detour"]


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def densify(points, per_segment=25):
    """Subdivide a polyline so properties are tested between the corners."""
    dense = [points[0]]
    for a, b in zip(points, points[1:]):
        for k in range(1, per_segment + 1):
            t = k / per_segment
            dense.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return dense


def optimal_path_to(scenario_, goal_id, per_segment=25):
    result = geodesic(
        scenario_.start, scenario_.goal(goal_id).position, scenario_.obstacles
    )
    return densify(result.path, per_segment)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_posterior_sums_to_one(name, condition):
    scenario_ = scenario(name)
    observer = Observer(condition=condition)
    rng = random.Random(20260804)
    for _ in range(50):
        # Random wandering prefixes, not just sensible ones. A planner under
        # test is not obliged to be sensible, and an observer that only
        # normalises correctly on tidy paths is not usable.
        points = [scenario_.start]
        for _ in range(rng.randint(1, 6)):
            candidate = (rng.uniform(0.5, 9.5), rng.uniform(0.5, 9.5))
            if not any(ob.contains_interior(candidate) for ob in scenario_.obstacles):
                points.append(candidate)
        belief = observer.posterior(scenario_, points)
        assert set(belief) == set(scenario_.goal_ids)
        assert sum(belief.values()) == pytest.approx(1.0)
        assert all(0.0 <= p <= 1.0 for p in belief.values())


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("condition", CONDITIONS)
def test_belief_before_moving_is_the_prior(name, condition):
    # At the start the bracket is exactly zero for every goal, whatever the
    # world looks like, so the belief must be the prior exactly rather than
    # approximately.
    scenario_ = scenario(name)
    belief = Observer(condition=condition).posterior(scenario_, [scenario_.start])
    assert belief == {g.id: 0.5 for g in scenario_.goals}


@pytest.mark.parametrize("name", NAMES)
def test_optimal_path_never_loses_belief_in_its_own_goal(name):
    # Advancing along the optimal path to G by a distance d costs d and can
    # reduce the cost-to-go of any other goal by at most d, so no other goal
    # can gain on G. The observer that can see the room must reflect that.
    scenario_ = scenario(name)
    observer = Observer(condition="geodesic")
    for goal_id in scenario_.goal_ids:
        beliefs = [
            p[goal_id]
            for p in observer.posterior_sequence(
                scenario_, optimal_path_to(scenario_, goal_id)
            )
        ]
        for earlier, later in zip(beliefs, beliefs[1:]):
            assert later >= earlier - 1e-12, (goal_id, earlier, later)
        assert beliefs[-1] > beliefs[0]


@pytest.mark.parametrize("condition", CONDITIONS)
def test_heading_straight_at_a_goal_is_read_as_heading_there(condition):
    scenario_ = scenario("open_two_goals")
    observer = Observer(condition=condition)
    beliefs = observer.belief_in_true_goal(
        scenario_, densify([scenario_.start, scenario_.true_goal_position])
    )
    assert beliefs[0] == pytest.approx(0.5)
    assert beliefs[-1] > 0.99
    for earlier, later in zip(beliefs, beliefs[1:]):
        assert later >= earlier - 1e-12


@pytest.mark.parametrize("condition", CONDITIONS)
def test_symmetric_world_gives_symmetric_belief(condition):
    # open_two_goals is a mirror image about the line through the start, so
    # a path reflected in that line must produce the reflected belief.
    scenario_ = scenario("open_two_goals")
    observer = Observer(condition=condition)
    upward = [(1.0, 5.0), (4.0, 6.5), (7.0, 7.0)]
    downward = [(1.0, 5.0), (4.0, 3.5), (7.0, 3.0)]
    up = observer.posterior(scenario_, upward)
    down = observer.posterior(scenario_, downward)
    assert up["A"] == down["B"]
    assert up["B"] == down["A"]
    assert up["A"] > up["B"]


def test_a_deviation_towards_one_goal_favours_it_over_the_direct_path():
    scenario_ = scenario("open_two_goals")
    observer = Observer(condition="geodesic")
    direct = observer.posterior(scenario_, [(1.0, 5.0), (5.0, 6.5)])
    exaggerated = observer.posterior(scenario_, [(1.0, 5.0), (4.0, 8.0)])
    assert exaggerated["A"] > direct["A"]


def test_beta_sharpens_the_belief():
    scenario_ = scenario("open_two_goals")
    path = [(1.0, 5.0), (4.0, 7.0)]
    beliefs = [
        Observer(condition="geodesic", beta=b).posterior(scenario_, path)["A"]
        for b in (0.25, 1.0, 4.0)
    ]
    assert beliefs[0] < beliefs[1] < beliefs[2]


def test_the_two_observers_disagree_when_the_room_is_not_visible():
    # The point of carrying both conditions, and it shows up before any
    # planner has tried to be legible. In wall_detour the optimal paths to
    # both goals share their first leg around the wall, so the observer who
    # can see the room learns nothing at all over that stretch and holds at
    # the prior. The observer who cannot see the wall reads the same motion
    # as the robot walking away from the goal it is actually going to, and
    # its belief in the true goal falls well below the prior before the
    # path clears the corner.
    scenario_ = scenario("wall_detour")
    path = optimal_path_to(scenario_, scenario_.true_goal, per_segment=20)
    informed = Observer(condition="geodesic").belief_in_true_goal(scenario_, path)
    naive = Observer(condition="straight_line").belief_in_true_goal(scenario_, path)

    shared_leg = informed[:21]
    assert all(p == pytest.approx(0.5) for p in shared_leg)
    assert min(informed) >= informed[0] - 1e-12

    assert min(naive) < 0.35
    assert naive.index(min(naive)) < len(naive) // 2
    assert informed[len(informed) // 4] > naive[len(naive) // 4]
    # Both recover once the goals separate; the disagreement is about when
    # the observer knows, which is the whole subject of the benchmark.
    assert informed[-1] > 0.95
    assert naive[-1] > 0.95


def test_wandering_far_from_every_goal_still_yields_a_distribution():
    # Every exponent is large and negative here. Without shifting by the
    # largest before exponentiating, all the weights underflow to zero and
    # the normalisation divides by zero.
    scenario_ = scenario("open_two_goals")
    detour = [(1.0, 5.0)] + [(1.0 + i * 0.01, 5.0 + (-1) ** i * 4.0) for i in range(60)]
    belief = Observer(condition="geodesic", beta=50.0).posterior(scenario_, detour)
    assert sum(belief.values()) == pytest.approx(1.0)
    assert all(p >= 0.0 for p in belief.values())


def test_custom_prior_is_honoured_and_validated():
    scenario_ = scenario("open_two_goals")
    biased = Observer(condition="geodesic", prior={"A": 3.0, "B": 1.0})
    assert biased.posterior(scenario_, [scenario_.start]) == pytest.approx(
        {"A": 0.75, "B": 0.25}
    )
    with pytest.raises(ObserverError, match="does not match the goals"):
        Observer(prior={"A": 1.0}).posterior(scenario_, [scenario_.start])
    with pytest.raises(ObserverError, match="negative entry"):
        Observer(prior={"A": -1.0, "B": 2.0}).posterior(scenario_, [scenario_.start])
    with pytest.raises(ObserverError, match="cannot be normalised"):
        Observer(prior={"A": 0.0, "B": 0.0}).posterior(scenario_, [scenario_.start])


def test_malformed_observers_and_prefixes_are_rejected():
    scenario_ = scenario("open_two_goals")
    with pytest.raises(ObserverError, match="unknown observer condition"):
        Observer(condition="telepathic")
    with pytest.raises(ObserverError, match="beta must be positive"):
        Observer(beta=0.0)
    with pytest.raises(ObserverError, match="at least one point"):
        Observer().posterior(scenario_, [])
    with pytest.raises(ObserverError, match="prefix starts at"):
        Observer().posterior(scenario_, [(2.0, 2.0), (3.0, 3.0)])


def test_observer_names_carry_the_coefficient():
    assert Observer(condition="geodesic").name == "geodesic_beta1"
    assert Observer(condition="straight_line", beta=2.5).name == "straight_line_beta2.5"
    assert [o.name for o in default_observers()] == [
        "geodesic_beta1",
        "straight_line_beta1",
    ]


def test_posterior_is_deterministic():
    scenario_ = scenario("pillar_two_goals")
    path = optimal_path_to(scenario_, "A", per_segment=5)
    first = Observer().posterior_sequence(scenario_, path)
    second = Observer().posterior_sequence(scenario_, path)
    assert first == second

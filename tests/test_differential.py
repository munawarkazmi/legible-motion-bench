"""The fast paths are held to the slow ones by test, not by argument.

Three optimisations sit underneath every number this benchmark reports: an
orientation predicate that trusts floating point when a forward error bound
says it may, a segment test that short circuits before reaching rational
arithmetic, and a cost-to-go index that reuses a visibility graph across
queries. Each is only admissible if it returns exactly what the obvious
implementation returns, so each is compared against it here.

The orientation corpus is deliberately built from near-collinear triples,
where a naive floating point determinant is not merely imprecise but
reports the wrong sign. The test asserts that it does, so that a corpus
which had quietly become easy could not pass as evidence.
"""

import random
from pathlib import Path

import pytest

from legible_motion_bench import world
from legible_motion_bench.costs import CostToGoIndex, geodesic_cost
from legible_motion_bench.geometry import (
    ConvexPolygon,
    _orientation_exact,
    orientation,
)

FIXTURES = Path(__file__).parent / "fixtures"
NAMES = ["open_two_goals", "pillar_two_goals", "wall_detour"]

CASES = 20000


def scenario(name):
    return world.load_scenario(FIXTURES / f"{name}.json")


def naive_orientation(o, a, b):
    """What the predicate would be without the guard. Not used in the code."""
    v = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    return (v > 0.0) - (v < 0.0)


def near_collinear_triples(count, seed=20260804):
    """Triples that lie on a line up to the rounding of their coordinates."""
    rng = random.Random(seed)
    for _ in range(count):
        ox, oy = rng.random(), rng.random()
        dx, dy = rng.uniform(-1, 1), rng.uniform(-1, 1)
        t, s = rng.uniform(-2, 2), rng.uniform(-2, 2)
        yield (
            (ox, oy),
            (ox + t * dx, oy + t * dy),
            (ox + s * dx, oy + s * dy),
        )


def test_guarded_orientation_equals_exact_orientation():
    for o, a, b in near_collinear_triples(CASES):
        assert orientation(o, a, b) == _orientation_exact(o, a, b), (o, a, b)


def test_the_corpus_is_hard_enough_to_be_evidence():
    # If a naive determinant got these right, agreeing with it would say
    # nothing about the guard. It does not: it reports collinear where the
    # rounded coordinates are genuinely not.
    wrong = sum(
        1
        for o, a, b in near_collinear_triples(CASES)
        if naive_orientation(o, a, b) != _orientation_exact(o, a, b)
    )
    assert wrong > CASES // 10, f"only {wrong} of {CASES} cases were hard"


def test_guarded_orientation_on_exactly_collinear_input():
    for o, a, b in [
        ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),
        ((0.5, 0.5), (12.0, 12.0), (24.0, 24.0)),
        ((0.0, 0.2), (0.2, 0.0), (0.1, 0.1)),
        ((-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)),
    ]:
        assert orientation(o, a, b) == 0
        assert _orientation_exact(o, a, b) == 0


def test_short_circuited_segment_test_equals_the_exact_clip():
    polygons = [
        ConvexPolygon.from_vertices("square", [(2, 2), (4, 2), (4, 4), (2, 4)]),
        ConvexPolygon.from_vertices("triangle", [(0.1, 0.1), (0.9, 0.2), (0.3, 0.7)]),
        ConvexPolygon.from_vertices(
            "pentagon", [(5, 0), (7, 1), (7.5, 3), (6, 4), (4.5, 2)]
        ),
    ]
    rng = random.Random(20260805)
    for polygon in polygons:
        for _ in range(3000):
            # Draw endpoints from the polygon's own vertices half the time,
            # so grazing and vertex-touching cases are common rather than
            # vanishingly unlikely.
            if rng.random() < 0.5:
                a = rng.choice(polygon.vertices)
            else:
                a = (rng.uniform(-1, 9), rng.uniform(-1, 6))
            if rng.random() < 0.5:
                b = rng.choice(polygon.vertices)
            else:
                b = (rng.uniform(-1, 9), rng.uniform(-1, 6))
            assert polygon.segment_enters_interior(
                a, b
            ) == polygon.segment_enters_interior_exact(a, b), (polygon.id, a, b)


@pytest.mark.parametrize("name", NAMES)
def test_cost_to_go_index_equals_the_full_search(name):
    scenario_ = scenario(name)
    index = CostToGoIndex(scenario_.obstacles, [g.position for g in scenario_.goals])
    rng = random.Random(20260806)
    bounds = scenario_.bounds
    checked = 0
    while checked < 800:
        point = (
            rng.uniform(bounds.xmin, bounds.xmax),
            rng.uniform(bounds.ymin, bounds.ymax),
        )
        if any(ob.contains_interior(point) for ob in scenario_.obstacles):
            continue
        checked += 1
        for goal in scenario_.goals:
            reference = geodesic_cost(point, goal.position, scenario_.obstacles)
            # Both sum the lengths of the same polyline, but they
            # accumulate from opposite ends, so the last bit may differ.
            # The tolerance is for the summation order and nothing else.
            assert index.cost_to(point, goal.position) == pytest.approx(
                reference, rel=1e-12, abs=1e-12
            )


def test_the_index_agrees_with_the_scenario_facts():
    pillar = scenario("pillar_two_goals")
    index = CostToGoIndex(pillar.obstacles, [g.position for g in pillar.goals])
    assert index.cost_to(pillar.start, pillar.goal("A").position) == pytest.approx(
        10.44030650891055
    )
    assert index.cost_to(pillar.start, pillar.goal("B").position) == pytest.approx(
        10.44030650891055
    )


def test_the_index_rejects_what_the_full_search_rejects():
    pillar = scenario("pillar_two_goals")
    index = CostToGoIndex(pillar.obstacles, [g.position for g in pillar.goals])
    with pytest.raises(Exception, match="lies inside obstacle"):
        index.cost_to((6.0, 5.0), pillar.goal("A").position)
    with pytest.raises(Exception, match="was not built for target"):
        index.cost_to(pillar.start, (0.5, 0.5))

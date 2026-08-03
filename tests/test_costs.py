import random
from math import hypot, sqrt

import pytest

from legible_motion_bench.costs import (
    UnreachableGoal,
    geodesic,
    geodesic_cost,
    straight_line_cost,
)
from legible_motion_bench.geometry import ConvexPolygon, GeometryError

WALL = ConvexPolygon.from_vertices(
    "wall", [(5, 0.5), (6, 0.5), (6, 7), (5, 7)]
)
PILLAR = ConvexPolygon.from_vertices(
    "pillar", [(5, 4), (7, 4), (7, 6), (5, 6)]
)
# Four overlapping rectangles that seal a hole around (5, 5). Convex
# obstacles cannot enclose a point on their own, so the sealed case is built
# from an overlapping union.
BOX = [
    ConvexPolygon.from_vertices("left", [(3, 3), (4, 3), (4, 7), (3, 7)]),
    ConvexPolygon.from_vertices("right", [(6, 3), (7, 3), (7, 7), (6, 7)]),
    ConvexPolygon.from_vertices("bottom", [(3, 3), (7, 3), (7, 4), (3, 4)]),
    ConvexPolygon.from_vertices("top", [(3, 6), (7, 6), (7, 7), (3, 7)]),
]


def test_open_world_geodesic_is_the_straight_line():
    result = geodesic((1, 5), (9, 8), [])
    assert result.path == ((1, 5), (9, 8))
    assert result.cost == pytest.approx(hypot(8, 3))


def test_geodesic_around_a_wall_turns_at_obstacle_corners():
    result = geodesic((1, 5), (11, 5), [WALL])
    assert result.path == ((1, 5), (5, 7), (6, 7), (11, 5))
    assert result.cost == pytest.approx(sqrt(20) + 1.0 + sqrt(29))


def test_geodesic_takes_the_cheaper_side():
    # The wall reaches almost to the floor, so going over the top is
    # shorter. Mirroring the wall must mirror the choice.
    low = ConvexPolygon.from_vertices("low", [(5, 3), (6, 3), (6, 9.5), (5, 9.5)])
    result = geodesic((1, 5), (11, 5), [low])
    assert result.path == ((1, 5), (5, 3), (6, 3), (11, 5))


def test_geodesic_is_symmetric_under_reflection():
    upper = geodesic((1, 5), (11, 8), [PILLAR])
    mirrored = geodesic((1, 5), (11, 2), [PILLAR])
    assert upper.cost == pytest.approx(mirrored.cost)


def test_geodesic_is_reversible():
    forward = geodesic((1, 5), (11, 5), [WALL])
    backward = geodesic((11, 5), (1, 5), [WALL])
    assert forward.cost == pytest.approx(backward.cost)
    assert backward.path == tuple(reversed(forward.path))


def test_geodesic_is_deterministic():
    first = geodesic((1, 5), (11, 5), [WALL])
    second = geodesic((1, 5), (11, 5), [WALL])
    assert first == second


def test_geodesic_is_never_shorter_than_the_straight_line():
    # The straight line observer is the second condition in the benchmark,
    # so the relationship between the two cost models is asserted rather
    # than assumed: an observer who cannot see the obstacles always
    # underestimates the cost-to-go, never the reverse.
    rng = random.Random(20260804)
    obstacles = [WALL, PILLAR]
    for _ in range(200):
        a = (rng.uniform(0, 12), rng.uniform(0, 10))
        b = (rng.uniform(0, 12), rng.uniform(0, 10))
        if any(ob.contains_interior(a) or ob.contains_interior(b) for ob in obstacles):
            continue
        assert geodesic_cost(a, b, obstacles) >= straight_line_cost(a, b) - 1e-12


def test_query_point_inside_an_obstacle_is_rejected():
    with pytest.raises(GeometryError, match="start point"):
        geodesic((5.5, 5), (11, 5), [WALL])
    with pytest.raises(GeometryError, match="end point"):
        geodesic((1, 5), (5.5, 5), [WALL])


def test_query_point_on_an_obstacle_boundary_is_allowed():
    result = geodesic((5, 7), (11, 5), [WALL])
    assert result.cost == pytest.approx(1.0 + sqrt(29))


def test_sealed_goal_is_unreachable():
    with pytest.raises(UnreachableGoal):
        geodesic((0, 0), (5, 5), BOX)

import random

import pytest

from legible_motion_bench.geometry import (
    ConvexPolygon,
    GeometryError,
    orientation,
    point_segment_distance,
    polyline_enters_interior,
    polyline_length,
    polyline_min_clearance,
    segment_segment_distance,
    segments_intersect,
)

UNIT = ConvexPolygon.from_vertices("unit", [(0, 0), (1, 0), (1, 1), (0, 1)])
# Coordinates that are not exactly representable in binary floating point.
# Every predicate below must still be decided exactly, because the
# visibility graph is built from these answers.
TENTHS = ConvexPolygon.from_vertices(
    "tenths", [(0.1, 0.1), (0.3, 0.1), (0.3, 0.3), (0.1, 0.3)]
)


def test_orientation_signs():
    assert orientation((0, 0), (1, 0), (0, 1)) == 1
    assert orientation((0, 0), (0, 1), (1, 0)) == -1
    assert orientation((0, 0), (1, 1), (2, 2)) == 0


def test_orientation_is_exact_on_inexact_coordinates():
    # 0.1 + 0.1 == 0.2 holds exactly for doubles, so this point lies exactly
    # on the segment and the predicate must report collinear rather than
    # something within a tolerance of it.
    assert orientation((0.0, 0.2), (0.2, 0.0), (0.1, 0.1)) == 0


def test_polygon_representation_is_canonical():
    # Same square, written clockwise and starting from three different
    # corners. All four must reduce to one representation, otherwise the
    # visibility graph would depend on how the file was typed.
    clockwise = ConvexPolygon.from_vertices("cw", [(0, 0), (0, 1), (1, 1), (1, 0)])
    rotated = ConvexPolygon.from_vertices("rot", [(1, 1), (0, 1), (0, 0), (1, 0)])
    counter = ConvexPolygon.from_vertices("ccw", [(1, 0), (1, 1), (0, 1), (0, 0)])
    assert clockwise.vertices == UNIT.vertices
    assert rotated.vertices == UNIT.vertices
    assert counter.vertices == UNIT.vertices
    assert UNIT.vertices == ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def test_polygon_rejects_degenerate_input():
    with pytest.raises(GeometryError, match="at least 3"):
        ConvexPolygon.from_vertices("two", [(0, 0), (1, 1)])
    with pytest.raises(GeometryError, match="repeats a vertex"):
        ConvexPolygon.from_vertices("dup", [(0, 0), (1, 0), (0, 0)])
    with pytest.raises(GeometryError, match="zero area"):
        ConvexPolygon.from_vertices("flat", [(0, 0), (1, 1), (2, 2)])


def test_polygon_rejects_non_convex_and_collinear_vertices():
    with pytest.raises(GeometryError, match="not strictly convex"):
        ConvexPolygon.from_vertices(
            "dart", [(0, 0), (2, 0), (1, 1), (2, 2), (0, 2)]
        )
    with pytest.raises(GeometryError, match="not strictly convex"):
        ConvexPolygon.from_vertices(
            "collinear", [(0, 0), (1, 0), (2, 0), (2, 2), (0, 2)]
        )


def test_containment_distinguishes_boundary_from_interior():
    assert UNIT.contains_interior((0.5, 0.5))
    assert not UNIT.contains_interior((0.0, 0.5))
    assert not UNIT.contains_interior((0.0, 0.0))
    assert UNIT.contains_closed((0.0, 0.5))
    assert UNIT.contains_closed((0.0, 0.0))
    assert not UNIT.contains_closed((-1e-9, 0.5))


def test_segment_crossing_the_interior():
    assert UNIT.segment_enters_interior((-1, 0.5), (2, 0.5))
    assert UNIT.segment_enters_interior((0.25, 0.25), (0.75, 0.75))
    assert UNIT.segment_enters_interior((-1, -1), (2, 2))


def test_segment_grazing_an_edge_does_not_enter():
    # A shortest path is allowed to run flush along an obstacle edge, so
    # grazing must not block visibility.
    assert not UNIT.segment_enters_interior((-1, 0), (2, 0))
    assert not TENTHS.segment_enters_interior((0.0, 0.1), (0.4, 0.1))


def test_segment_touching_a_single_vertex_does_not_enter():
    assert not TENTHS.segment_enters_interior((0.0, 0.2), (0.2, 0.0))
    assert not UNIT.segment_enters_interior((-1, 1), (1, -1))


def test_segment_entirely_outside_or_degenerate():
    assert not UNIT.segment_enters_interior((2, 2), (3, 3))
    assert not UNIT.segment_enters_interior((2, 2), (2, 2))
    assert UNIT.segment_enters_interior((0.5, 0.5), (0.5, 0.5))


def test_segment_predicate_agrees_with_sampling():
    # One direction only: if a sampled point of the segment is strictly
    # inside, the predicate must say so. The converse can fail for a
    # crossing thinner than the sample spacing, and asserting it would be
    # asserting something untrue.
    rng = random.Random(20260804)
    for _ in range(400):
        a = (rng.uniform(-2, 3), rng.uniform(-2, 3))
        b = (rng.uniform(-2, 3), rng.uniform(-2, 3))
        samples = [
            (a[0] + t / 200 * (b[0] - a[0]), a[1] + t / 200 * (b[1] - a[1]))
            for t in range(201)
        ]
        if any(UNIT.contains_interior(p) for p in samples):
            assert UNIT.segment_enters_interior(a, b), (a, b)


def test_segments_intersect_cases():
    assert segments_intersect((0, 0), (2, 2), (0, 2), (2, 0))
    assert segments_intersect((0, 0), (1, 1), (1, 1), (2, 0))
    assert not segments_intersect((0, 0), (1, 0), (0, 1), (1, 1))
    assert segments_intersect((0, 0), (2, 0), (1, 0), (3, 0))


def test_point_and_segment_distances():
    assert point_segment_distance((0, 1), (0, 0), (2, 0)) == pytest.approx(1.0)
    assert point_segment_distance((-1, 0), (0, 0), (2, 0)) == pytest.approx(1.0)
    assert segment_segment_distance(
        (0, 0), (1, 0), (0, 3), (1, 3)
    ) == pytest.approx(3.0)
    assert segment_segment_distance(
        (0, 0), (2, 0), (1, -1), (1, 1)
    ) == pytest.approx(0.0)


def test_polygon_distances():
    assert UNIT.distance_to_point((0.5, 0.5)) == 0.0
    assert UNIT.distance_to_point((2.0, 0.5)) == pytest.approx(1.0)
    assert UNIT.distance_to_segment((2, 0), (2, 1)) == pytest.approx(1.0)
    assert UNIT.distance_to_segment((-1, 0.5), (2, 0.5)) == 0.0


def test_polyline_helpers():
    line = [(0, 0), (3, 0), (3, 4)]
    assert polyline_length(line) == pytest.approx(7.0)
    assert polyline_length([(1, 1)]) == 0.0
    assert polyline_min_clearance(line, [UNIT]) == 0.0
    assert polyline_min_clearance([(0, 5), (3, 5)], [UNIT]) == pytest.approx(4.0)
    assert polyline_enters_interior([(-1, 0.5), (2, 0.5)], UNIT)
    assert not polyline_enters_interior([(0, 5), (3, 5)], UNIT)


def test_clearance_without_obstacles_is_infinite():
    # An open world has no clearance to report. Returning zero would make a
    # safety column read as a violation where none is defined.
    assert polyline_min_clearance([(0, 0), (1, 1)], []) == float("inf")

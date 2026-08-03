"""Exact geometric primitives for convex polygonal worlds.

Every predicate that decides a combinatorial question, for example whether a
segment passes through the interior of an obstacle, is evaluated in exact
rational arithmetic. Coordinates arrive as JSON numbers and become Python
floats, and Fraction(float) is exact for the stored double, so a predicate
here is exact with respect to the coordinates as committed rather than
merely accurate to some tolerance. That matters because the visibility graph
in costs.py is built entirely from these predicates: a single misclassified
segment silently changes the optimal cost-to-go, and the optimal cost-to-go
is the quantity the observer model is defined on.

Lengths are irrational in general, so distances stay in floating point. The
division of labour is deliberate: combinatorics exact, magnitudes floating.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import hypot, inf

Point = tuple[float, float]


class GeometryError(ValueError):
    """Raised when a geometric object or query is malformed."""


def _frac(p: Point) -> tuple[Fraction, Fraction]:
    return (Fraction(p[0]), Fraction(p[1]))


def orientation(o: Point, a: Point, b: Point) -> int:
    """Sign of the cross product of (a - o) and (b - o), computed exactly.

    Returns 1 if o, a, b turn left, -1 if they turn right, 0 if collinear.
    """
    ox, oy = _frac(o)
    ax, ay = _frac(a)
    bx, by = _frac(b)
    v = (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)
    return (v > 0) - (v < 0)


def segments_intersect(p: Point, q: Point, r: Point, s: Point) -> bool:
    """Exact test for whether closed segments pq and rs share a point."""
    d1 = orientation(p, q, r)
    d2 = orientation(p, q, s)
    d3 = orientation(r, s, p)
    d4 = orientation(r, s, q)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    # Collinear or touching cases: a zero orientation means the fourth point
    # lies on the line of the other segment, so it intersects exactly when it
    # also lies within that segment's bounding box.
    if d1 == 0 and _on_segment(p, q, r):
        return True
    if d2 == 0 and _on_segment(p, q, s):
        return True
    if d3 == 0 and _on_segment(r, s, p):
        return True
    if d4 == 0 and _on_segment(r, s, q):
        return True
    return False


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    """Whether p, known to be collinear with a and b, lies within segment ab."""
    return (
        min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Euclidean distance from p to the closed segment ab."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom == 0.0:
        return hypot(p[0] - ax, p[1] - ay)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / denom
    t = min(1.0, max(0.0, t))
    return hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def segment_segment_distance(p: Point, q: Point, r: Point, s: Point) -> float:
    """Euclidean distance between two closed segments."""
    if segments_intersect(p, q, r, s):
        return 0.0
    return min(
        point_segment_distance(p, r, s),
        point_segment_distance(q, r, s),
        point_segment_distance(r, p, q),
        point_segment_distance(s, p, q),
    )


@dataclass(frozen=True)
class ConvexPolygon:
    """A strictly convex polygon with vertices in counter-clockwise order.

    Strict convexity is enforced rather than assumed. Collinear triples are
    rejected because they make the interior test and the visibility graph
    harder to reason about while adding nothing a scenario author needs: a
    vertex that lies on the segment between its neighbours is never a corner
    the shortest path turns at.
    """

    id: str
    vertices: tuple[Point, ...]

    @classmethod
    def from_vertices(cls, id: str, vertices) -> "ConvexPolygon":
        verts = tuple((float(x), float(y)) for x, y in vertices)
        if len(verts) < 3:
            raise GeometryError(
                f"polygon {id!r} has {len(verts)} vertices, at least 3 are required"
            )
        if len(set(verts)) != len(verts):
            raise GeometryError(f"polygon {id!r} repeats a vertex")
        area2 = _signed_area_doubled(verts)
        if area2 == 0:
            raise GeometryError(f"polygon {id!r} has zero area")
        if area2 < 0:
            verts = tuple(reversed(verts))
        n = len(verts)
        for i in range(n):
            turn = orientation(verts[i], verts[(i + 1) % n], verts[(i + 2) % n])
            if turn <= 0:
                raise GeometryError(
                    f"polygon {id!r} is not strictly convex at vertex "
                    f"{(i + 1) % n} {verts[(i + 1) % n]}"
                )
        # Rotate so the lexicographically smallest vertex comes first. Two
        # scenario files that describe the same shape starting from
        # different corners then produce the same vertex order, so the
        # visibility graph node ordering, and with it the tie-break between
        # paths of equal length, depends on the shape rather than on how it
        # happened to be typed.
        pivot = verts.index(min(verts))
        verts = verts[pivot:] + verts[:pivot]
        return cls(id=id, vertices=verts)

    def edges(self):
        n = len(self.vertices)
        for i in range(n):
            yield self.vertices[i], self.vertices[(i + 1) % n]

    def contains_interior(self, p: Point) -> bool:
        """Whether p lies strictly inside the polygon."""
        return all(orientation(v, w, p) > 0 for v, w in self.edges())

    def contains_closed(self, p: Point) -> bool:
        """Whether p lies inside the polygon or on its boundary."""
        return all(orientation(v, w, p) >= 0 for v, w in self.edges())

    def segment_enters_interior(self, a: Point, b: Point) -> bool:
        """Whether the closed segment ab passes through the open interior.

        A segment that merely grazes an edge or touches a vertex does not
        enter the interior and so does not block visibility. This is the
        correct convention for shortest paths, which turn at obstacle
        corners and are allowed to run flush along an obstacle edge.

        The interior of a counter-clockwise polygon is the intersection of
        the open half planes to the left of each edge. Clipping the segment
        against those half planes in exact arithmetic leaves an interval of
        the parameter t; the segment enters the interior exactly when that
        interval has positive length.
        """
        ax, ay = _frac(a)
        bx, by = _frac(b)
        dx, dy = bx - ax, by - ay
        lo, hi = Fraction(0), Fraction(1)
        for v, w in self.edges():
            vx, vy = _frac(v)
            wx, wy = _frac(w)
            ex, ey = wx - vx, wy - vy
            # f(t) = cross(edge, a + t*d - v) must be strictly positive.
            c0 = ex * (ay - vy) - ey * (ax - vx)
            cd = ex * dy - ey * dx
            if cd == 0:
                if c0 <= 0:
                    return False
                continue
            t = -c0 / cd
            if cd > 0:
                if t > lo:
                    lo = t
            else:
                if t < hi:
                    hi = t
            if lo >= hi:
                return False
        return lo < hi

    def distance_to_point(self, p: Point) -> float:
        if self.contains_closed(p):
            return 0.0
        return min(point_segment_distance(p, v, w) for v, w in self.edges())

    def distance_to_segment(self, a: Point, b: Point) -> float:
        if self.contains_closed(a) or self.contains_closed(b):
            return 0.0
        if self.segment_enters_interior(a, b):
            return 0.0
        return min(segment_segment_distance(a, b, v, w) for v, w in self.edges())


def _signed_area_doubled(verts: tuple[Point, ...]) -> Fraction:
    total = Fraction(0)
    n = len(verts)
    for i in range(n):
        x1, y1 = _frac(verts[i])
        x2, y2 = _frac(verts[(i + 1) % n])
        total += x1 * y2 - x2 * y1
    return total


def polyline_length(points) -> float:
    """Total Euclidean length of a polyline given as a sequence of points."""
    pts = list(points)
    if len(pts) < 2:
        return 0.0
    return sum(
        hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])
    )


def polyline_min_clearance(points, polygons) -> float:
    """Smallest distance from any point of the polyline to any polygon.

    Returns infinity when there are no polygons, which keeps the caller
    honest: a scenario with no obstacles has no clearance to report, and a
    metric that silently returned zero there would be worse than one that
    is obviously not a number.
    """
    pts = list(points)
    polys = list(polygons)
    if not polys:
        return inf
    if len(pts) < 2:
        if not pts:
            raise GeometryError("clearance of an empty polyline is undefined")
        return min(poly.distance_to_point(pts[0]) for poly in polys)
    return min(
        poly.distance_to_segment(a, b)
        for poly in polys
        for a, b in zip(pts, pts[1:])
    )


def polyline_enters_interior(points, polygon: ConvexPolygon) -> bool:
    """Whether any part of the polyline lies strictly inside the polygon."""
    pts = list(points)
    if len(pts) == 1:
        return polygon.contains_interior(pts[0])
    return any(
        polygon.segment_enters_interior(a, b) for a, b in zip(pts, pts[1:])
    )

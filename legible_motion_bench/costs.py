"""Exact optimal cost-to-go in a world of convex polygonal obstacles.

The cost of a path is its Euclidean length. In a plane occupied by polygonal
obstacles the shortest path between two points that avoids the obstacle
interiors is a polyline whose intermediate vertices are obstacle vertices,
so the exact optimum is obtained by shortest path search over the visibility
graph on the two query points plus every obstacle vertex. There is no
discretisation and no grid resolution to defend.

This module is the foundation the observer model stands on. The Boltzmann
observer of Dragan et al. scores a goal using the optimal cost-to-go from
the robot's current position to that goal, so an approximate cost-to-go
would put an approximation underneath every posterior in the benchmark.

Keep-out zones are deliberately absent here. They do not block motion; a
trajectory may cross one and is scored for having done so. If they blocked
motion there would be no frontier to measure, because no planner could ever
trade safety for clarity.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import hypot, inf

from .geometry import ConvexPolygon, GeometryError, Point


@dataclass(frozen=True)
class Geodesic:
    """A shortest obstacle-avoiding path and its length."""

    cost: float
    path: tuple[Point, ...]


class UnreachableGoal(GeometryError):
    """Raised when no obstacle-avoiding path exists between two points."""


def _visible(a: Point, b: Point, obstacles) -> bool:
    return not any(ob.segment_enters_interior(a, b) for ob in obstacles)


def _check_free(p: Point, obstacles, label: str) -> None:
    for ob in obstacles:
        if ob.contains_interior(p):
            raise GeometryError(
                f"{label} {p} lies inside obstacle {ob.id!r}"
            )


def geodesic(a: Point, b: Point, obstacles) -> Geodesic:
    """Exact shortest path from a to b avoiding the interiors of obstacles.

    Node ordering is a, then b, then obstacle vertices in the order the
    obstacles were declared. Dijkstra breaks ties on node index, so the
    returned path is a deterministic function of the inputs and not merely
    one optimum among several of equal length.
    """
    obs = list(obstacles)
    _check_free(a, obs, "start point")
    _check_free(b, obs, "end point")

    nodes: list[Point] = [a, b]
    seen = {a, b}
    for ob in obs:
        for v in ob.vertices:
            if v not in seen:
                seen.add(v)
                nodes.append(v)

    n = len(nodes)
    adjacency: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _visible(nodes[i], nodes[j], obs):
                w = hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1])
                adjacency[i].append((j, w))
                adjacency[j].append((i, w))

    dist = [inf] * n
    previous = [-1] * n
    dist[0] = 0.0
    queue: list[tuple[float, int]] = [(0.0, 0)]
    settled = [False] * n
    while queue:
        d, u = heapq.heappop(queue)
        if settled[u]:
            continue
        settled[u] = True
        if u == 1:
            break
        for v, w in adjacency[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                previous[v] = u
                heapq.heappush(queue, (nd, v))

    if dist[1] == inf:
        raise UnreachableGoal(f"no obstacle-avoiding path from {a} to {b}")

    path = [1]
    while path[-1] != 0:
        path.append(previous[path[-1]])
    path.reverse()
    return Geodesic(cost=dist[1], path=tuple(nodes[i] for i in path))


def geodesic_cost(a: Point, b: Point, obstacles) -> float:
    """Optimal cost-to-go from a to b, written C* elsewhere in the code."""
    return geodesic(a, b, obstacles).cost


def straight_line_cost(a: Point, b: Point) -> float:
    """Cost-to-go for an observer who cannot see the obstacles.

    This is the second observer condition, not a fallback. It models someone
    watching from a doorway who can see the robot and knows the candidate
    goals but has no view of what stands between them. Whether the ranking
    of planners is stable across the two observers is a question the
    benchmark asks rather than assumes.
    """
    return hypot(a[0] - b[0], a[1] - b[1])

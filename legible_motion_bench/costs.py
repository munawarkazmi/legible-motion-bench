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
    """Optimal cost-to-go from a to b, written C* elsewhere in the code.

    This is the reference implementation: it rebuilds the whole visibility
    graph for every call, which is slow and obviously correct. The index
    below is the fast path and is tested against this one.
    """
    return geodesic(a, b, obstacles).cost


class CostToGoIndex:
    """Optimal cost-to-go to a fixed set of targets, from any query point.

    Built once per scenario. The observer asks for the cost-to-go from
    every sampled point of a trajectory to every candidate goal, which is
    thousands of queries over a world that never changes, and rebuilding
    the visibility graph each time was most of the cost of the benchmark.

    Only the query point differs between calls. The obstacle vertices and
    the targets form a graph that can be built once and searched once per
    target, after which a query is one visibility test per node and a
    minimum, with no search at all.

    The answer is unchanged, and the reason is worth stating because the
    whole benchmark rests on it. A shortest path from a point to a target
    either runs straight there or turns first at an obstacle vertex, and
    that first hop is by definition a visible segment. So the minimum over
    visible nodes of the hop plus the precomputed remainder is the same
    number the full search returns.
    """

    def __init__(self, obstacles, targets):
        self._obstacles = tuple(obstacles)
        self._targets = tuple((float(x), float(y)) for x, y in targets)

        nodes: list[Point] = []
        seen = set()
        for ob in self._obstacles:
            for v in ob.vertices:
                if v not in seen:
                    seen.add(v)
                    nodes.append(v)
        for t in self._targets:
            if t not in seen:
                seen.add(t)
                nodes.append(t)
        self._nodes = tuple(nodes)

        n = len(self._nodes)
        self._adjacency: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if _visible(self._nodes[i], self._nodes[j], self._obstacles):
                    w = hypot(
                        self._nodes[i][0] - self._nodes[j][0],
                        self._nodes[i][1] - self._nodes[j][1],
                    )
                    self._adjacency[i].append((j, w))
                    self._adjacency[j].append((i, w))

        self._distance = {t: self._search_from(self._nodes.index(t)) for t in self._targets}

    def _search_from(self, source: int) -> tuple[float, ...]:
        n = len(self._nodes)
        dist = [inf] * n
        dist[source] = 0.0
        settled = [False] * n
        queue: list[tuple[float, int]] = [(0.0, source)]
        while queue:
            d, u = heapq.heappop(queue)
            if settled[u]:
                continue
            settled[u] = True
            for v, w in self._adjacency[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(queue, (nd, v))
        return tuple(dist)

    @property
    def targets(self) -> tuple[Point, ...]:
        return self._targets

    def cost_to(self, point: Point, target: Point) -> float:
        query = (float(point[0]), float(point[1]))
        key = (float(target[0]), float(target[1]))
        if key not in self._distance:
            raise GeometryError(
                f"cost-to-go index was not built for target {key}; "
                f"it holds {list(self._targets)}"
            )
        _check_free(query, self._obstacles, "query point")

        distances = self._distance[key]
        best = inf
        for i, node in enumerate(self._nodes):
            if distances[i] == inf:
                continue
            if _visible(query, node, self._obstacles):
                candidate = hypot(query[0] - node[0], query[1] - node[1]) + distances[i]
                if candidate < best:
                    best = candidate
        if best == inf:
            raise UnreachableGoal(f"no obstacle-avoiding path from {query} to {key}")
        return best


def straight_line_cost(a: Point, b: Point) -> float:
    """Cost-to-go for an observer who cannot see the obstacles.

    This is the second observer condition, not a fallback. It models someone
    watching from a doorway who can see the robot and knows the candidate
    goals but has no view of what stands between them. Whether the ranking
    of planners is stable across the two observers is a question the
    benchmark asks rather than assumes.
    """
    return hypot(a[0] - b[0], a[1] - b[1])

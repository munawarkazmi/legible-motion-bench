"""The world model: scenarios, their geometry, and their validity.

A scenario is a 2D kinematic world. The robot is a point that moves at
constant speed along a polyline, there is no physics, and every quantity the
benchmark reports is a function of the polyline and the world. That is a
scope decision rather than a shortcut: a physics engine would improve the
renderings and change none of the numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .costs import geodesic_cost
from .geometry import ConvexPolygon, GeometryError, Point


class ScenarioError(ValueError):
    """Raised when a scenario is well formed but not a valid world."""


@dataclass(frozen=True)
class Bounds:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def contains(self, p: Point) -> bool:
        return self.xmin <= p[0] <= self.xmax and self.ymin <= p[1] <= self.ymax


@dataclass(frozen=True)
class Goal:
    id: str
    position: Point


@dataclass(frozen=True)
class Property:
    """A machine-checked fact carried by the scenario that asserts it.

    Properties live inside the scenario file rather than beside it so that a
    scenario and its proof obligations cannot drift apart. The checkers are
    in properties.py; an unrecognised kind is an error, so a scenario may
    not assert anything the committed code cannot decide.
    """

    kind: str
    args: dict
    value: object


@dataclass(frozen=True)
class Scenario:
    schema_version: int
    id: str
    description: str
    bounds: Bounds
    start: Point
    goals: tuple[Goal, ...]
    true_goal: str
    obstacles: tuple[ConvexPolygon, ...]
    keep_out_zones: tuple[ConvexPolygon, ...]
    properties: tuple[Property, ...]
    source_path: str | None = None

    def goal(self, goal_id: str) -> Goal:
        for g in self.goals:
            if g.id == goal_id:
                return g
        raise KeyError(f"scenario {self.id!r} has no goal {goal_id!r}")

    @property
    def goal_ids(self) -> tuple[str, ...]:
        return tuple(g.id for g in self.goals)

    @property
    def true_goal_position(self) -> Point:
        return self.goal(self.true_goal).position

    def point_named(self, name: str) -> Point:
        """Resolve "start" or a goal id to a position.

        Property arguments name positions rather than repeating coordinates,
        so that moving a goal in the scenario file cannot leave a property
        silently checking the goal's old location.
        """
        if name == "start":
            return self.start
        return self.goal(name).position


def from_dict(doc: dict, source_path: str | None = None) -> Scenario:
    """Build a validated Scenario from a decoded scenario document."""
    schema.validate(doc)

    bounds = Bounds(**{k: float(v) for k, v in doc["bounds"].items()})
    start = (float(doc["start"][0]), float(doc["start"][1]))
    goals = tuple(
        Goal(id=g["id"], position=(float(g["position"][0]), float(g["position"][1])))
        for g in doc["goals"]
    )
    obstacles = tuple(
        ConvexPolygon.from_vertices(p["id"], p["vertices"])
        for p in doc.get("obstacles", [])
    )
    keep_out_zones = tuple(
        ConvexPolygon.from_vertices(p["id"], p["vertices"])
        for p in doc.get("keep_out_zones", [])
    )
    properties = tuple(
        Property(kind=p["kind"], args=dict(p.get("args", {})), value=p.get("value"))
        for p in doc.get("properties", [])
    )

    scenario = Scenario(
        schema_version=doc["schema_version"],
        id=doc["id"],
        description=doc["description"],
        bounds=bounds,
        start=start,
        goals=goals,
        true_goal=doc["true_goal"],
        obstacles=obstacles,
        keep_out_zones=keep_out_zones,
        properties=properties,
        source_path=source_path,
    )
    _validate_geometry(scenario)
    return scenario


def _validate_geometry(s: Scenario) -> None:
    named: list[tuple[str, Point]] = [("start", s.start)]
    named.extend((f"goal {g.id!r}", g.position) for g in s.goals)

    for label, point in named:
        if not s.bounds.contains(point):
            raise ScenarioError(f"{label} at {point} lies outside the bounds")
        for ob in s.obstacles:
            if ob.contains_interior(point):
                raise ScenarioError(
                    f"{label} at {point} lies inside obstacle {ob.id!r}"
                )

    for group, polygons in (
        ("obstacle", s.obstacles),
        ("keep-out zone", s.keep_out_zones),
    ):
        for poly in polygons:
            for vertex in poly.vertices:
                if not s.bounds.contains(vertex):
                    raise ScenarioError(
                        f"{group} {poly.id!r} has vertex {vertex} outside the bounds"
                    )

    positions = [g.position for g in s.goals]
    if len(set(positions)) != len(positions):
        raise ScenarioError(f"scenario {s.id!r} has two goals at the same position")
    for g in s.goals:
        if g.position == s.start:
            raise ScenarioError(
                f"scenario {s.id!r} places goal {g.id!r} at the start position"
            )

    # Reachability is part of being a valid world, not a property a scenario
    # may choose to assert. A goal walled off by obstacles has no cost-to-go,
    # and every metric downstream would be undefined for it.
    for g in s.goals:
        try:
            geodesic_cost(s.start, g.position, s.obstacles)
        except GeometryError as exc:
            raise ScenarioError(
                f"scenario {s.id!r} goal {g.id!r} is not reachable from the start: {exc}"
            ) from exc


def load_scenario(path) -> Scenario:
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        doc = json.load(handle)
    try:
        return from_dict(doc, source_path=str(path))
    except (schema.SchemaError, ScenarioError, GeometryError) as exc:
        raise type(exc)(f"{path}: {exc}") from exc


def load_directory(directory) -> tuple[Scenario, ...]:
    """Load every scenario in a directory, in sorted filename order."""
    paths = sorted(Path(directory).glob("*.json"))
    scenarios = tuple(load_scenario(p) for p in paths)
    ids = [s.id for s in scenarios]
    if len(set(ids)) != len(ids):
        raise ScenarioError(f"duplicate scenario ids under {directory}: {ids}")
    return scenarios

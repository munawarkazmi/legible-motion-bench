"""Shape validation for scenario files.

This layer checks that a decoded JSON document has the right keys and the
right types, and nothing else. Geometric validity, for example that a goal
does not sit inside an obstacle, belongs to world.py, which can only run
those checks once the shapes are known to be sound.

Unknown keys are an error rather than something to ignore. A scenario file
that misspells "keep_out_zones" would otherwise load cleanly, contribute no
keep-out zones, and produce a benchmark row in which every planner appears
perfectly safe.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

_TOP_LEVEL_REQUIRED = {
    "schema_version",
    "id",
    "description",
    "bounds",
    "start",
    "goals",
    "true_goal",
}
_TOP_LEVEL_OPTIONAL = {"obstacles", "keep_out_zones", "properties"}
_BOUNDS_KEYS = {"xmin", "ymin", "xmax", "ymax"}


class SchemaError(ValueError):
    """Raised when a scenario document does not match the schema."""


def _require_keys(doc: dict, required: set, optional: set, where: str) -> None:
    if not isinstance(doc, dict):
        raise SchemaError(f"{where} must be an object, found {type(doc).__name__}")
    keys = set(doc)
    missing = required - keys
    if missing:
        raise SchemaError(f"{where} is missing {sorted(missing)}")
    unknown = keys - required - optional
    if unknown:
        raise SchemaError(f"{where} has unknown keys {sorted(unknown)}")


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{where} must be a number, found {value!r}")
    return float(value)


def _identifier(value, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{where} must be a non-empty string, found {value!r}")
    return value


def _point(value, where: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise SchemaError(f"{where} must be a list of two numbers, found {value!r}")
    return (_number(value[0], f"{where}[0]"), _number(value[1], f"{where}[1]"))


def validate(doc) -> dict:
    """Validate a decoded scenario document and return it unchanged.

    Optional collections are not filled in here. The loader supplies the
    defaults so that this function stays a pure check.
    """
    _require_keys(doc, _TOP_LEVEL_REQUIRED, _TOP_LEVEL_OPTIONAL, "scenario")

    version = doc["schema_version"]
    if version != SCHEMA_VERSION:
        raise SchemaError(
            f"scenario schema_version is {version!r}, this build reads "
            f"version {SCHEMA_VERSION}"
        )

    _identifier(doc["id"], "scenario id")
    if not isinstance(doc["description"], str):
        raise SchemaError("scenario description must be a string")

    _require_keys(doc["bounds"], _BOUNDS_KEYS, set(), "bounds")
    bounds = {k: _number(doc["bounds"][k], f"bounds.{k}") for k in _BOUNDS_KEYS}
    if bounds["xmin"] >= bounds["xmax"] or bounds["ymin"] >= bounds["ymax"]:
        raise SchemaError(f"bounds are empty or inverted: {bounds}")

    _point(doc["start"], "start")

    goals = doc["goals"]
    if not isinstance(goals, list) or len(goals) < 2:
        raise SchemaError(
            "goals must be a list of at least two goals; a scenario with one "
            "goal has nothing to be ambiguous about"
        )
    goal_ids = []
    for i, goal in enumerate(goals):
        _require_keys(goal, {"id", "position"}, set(), f"goals[{i}]")
        goal_ids.append(_identifier(goal["id"], f"goals[{i}].id"))
        _point(goal["position"], f"goals[{i}].position")
    if len(set(goal_ids)) != len(goal_ids):
        raise SchemaError(f"goal ids are not unique: {goal_ids}")

    true_goal = _identifier(doc["true_goal"], "true_goal")
    if true_goal not in goal_ids:
        raise SchemaError(
            f"true_goal {true_goal!r} is not among the goal ids {goal_ids}"
        )

    for field in ("obstacles", "keep_out_zones"):
        polygons = doc.get(field, [])
        if not isinstance(polygons, list):
            raise SchemaError(f"{field} must be a list")
        ids = []
        for i, poly in enumerate(polygons):
            _require_keys(poly, {"id", "vertices"}, set(), f"{field}[{i}]")
            ids.append(_identifier(poly["id"], f"{field}[{i}].id"))
            vertices = poly["vertices"]
            if not isinstance(vertices, list) or len(vertices) < 3:
                raise SchemaError(
                    f"{field}[{i}].vertices must be a list of at least 3 points"
                )
            for j, vertex in enumerate(vertices):
                _point(vertex, f"{field}[{i}].vertices[{j}]")
        if len(set(ids)) != len(ids):
            raise SchemaError(f"{field} ids are not unique: {ids}")

    properties = doc.get("properties", [])
    if not isinstance(properties, list):
        raise SchemaError("properties must be a list")
    for i, prop in enumerate(properties):
        _require_keys(prop, {"kind"}, {"args", "value"}, f"properties[{i}]")
        _identifier(prop["kind"], f"properties[{i}].kind")
        if "args" in prop and not isinstance(prop["args"], dict):
            raise SchemaError(f"properties[{i}].args must be an object")

    return doc

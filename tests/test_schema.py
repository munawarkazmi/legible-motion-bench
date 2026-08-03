import copy

import pytest

from legible_motion_bench import schema

VALID = {
    "schema_version": 1,
    "id": "example",
    "description": "",
    "bounds": {"xmin": 0.0, "ymin": 0.0, "xmax": 10.0, "ymax": 10.0},
    "start": [1.0, 5.0],
    "goals": [
        {"id": "A", "position": [9.0, 8.0]},
        {"id": "B", "position": [9.0, 2.0]},
    ],
    "true_goal": "A",
    "obstacles": [{"id": "pillar", "vertices": [[4, 4], [6, 4], [6, 6], [4, 6]]}],
    "keep_out_zones": [],
    "properties": [{"kind": "goal_separation_at_least", "args": {"threshold": 1.0}}],
}


def mutated(**changes):
    doc = copy.deepcopy(VALID)
    doc.update(changes)
    return doc


def test_valid_document_passes():
    assert schema.validate(copy.deepcopy(VALID)) is not None


def test_optional_collections_may_be_absent():
    doc = copy.deepcopy(VALID)
    for field in ("obstacles", "keep_out_zones", "properties"):
        del doc[field]
    schema.validate(doc)


def test_missing_required_key_is_rejected():
    doc = copy.deepcopy(VALID)
    del doc["true_goal"]
    with pytest.raises(schema.SchemaError, match="missing"):
        schema.validate(doc)


def test_unknown_key_is_rejected():
    # A misspelled keep_out_zones would otherwise load as a world with no
    # keep-out zones, in which every planner scores as perfectly safe.
    with pytest.raises(schema.SchemaError, match="unknown keys"):
        schema.validate(mutated(keepout_zones=[]))


def test_wrong_schema_version_is_rejected():
    with pytest.raises(schema.SchemaError, match="schema_version"):
        schema.validate(mutated(schema_version=2))


def test_single_goal_is_rejected():
    with pytest.raises(schema.SchemaError, match="at least two goals"):
        schema.validate(mutated(goals=[{"id": "A", "position": [9.0, 8.0]}]))


def test_duplicate_goal_ids_are_rejected():
    doc = mutated(
        goals=[
            {"id": "A", "position": [9.0, 8.0]},
            {"id": "A", "position": [9.0, 2.0]},
        ]
    )
    with pytest.raises(schema.SchemaError, match="not unique"):
        schema.validate(doc)


def test_true_goal_must_name_a_goal():
    with pytest.raises(schema.SchemaError, match="not among the goal ids"):
        schema.validate(mutated(true_goal="C"))


def test_inverted_bounds_are_rejected():
    doc = mutated(bounds={"xmin": 10.0, "ymin": 0.0, "xmax": 0.0, "ymax": 10.0})
    with pytest.raises(schema.SchemaError, match="inverted"):
        schema.validate(doc)


def test_malformed_point_is_rejected():
    with pytest.raises(schema.SchemaError, match="two numbers"):
        schema.validate(mutated(start=[1.0]))
    with pytest.raises(schema.SchemaError, match="must be a number"):
        schema.validate(mutated(start=[1.0, "five"]))


def test_boolean_is_not_a_number():
    with pytest.raises(schema.SchemaError, match="must be a number"):
        schema.validate(mutated(start=[1.0, True]))


def test_polygon_needs_three_vertices():
    doc = mutated(obstacles=[{"id": "thin", "vertices": [[0, 0], [1, 1]]}])
    with pytest.raises(schema.SchemaError, match="at least 3 points"):
        schema.validate(doc)


def test_property_needs_a_kind():
    with pytest.raises(schema.SchemaError, match="missing"):
        schema.validate(mutated(properties=[{"args": {}}]))

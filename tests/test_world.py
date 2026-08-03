import copy
from pathlib import Path

import pytest

from legible_motion_bench import world
from legible_motion_bench.geometry import GeometryError

FIXTURES = Path(__file__).parent / "fixtures"

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
    "properties": [],
}


def mutated(**changes):
    doc = copy.deepcopy(VALID)
    doc.update(changes)
    return doc


def test_every_fixture_loads():
    scenarios = world.load_directory(FIXTURES)
    assert [s.id for s in scenarios] == [
        "open_two_goals",
        "pillar_two_goals",
        "wall_detour",
    ]


def test_scenario_accessors():
    scenario = world.load_scenario(FIXTURES / "pillar_two_goals.json")
    assert scenario.goal_ids == ("A", "B")
    assert scenario.true_goal_position == (11.0, 8.0)
    assert scenario.point_named("start") == (1.0, 5.0)
    assert scenario.point_named("B") == (11.0, 2.0)
    with pytest.raises(KeyError):
        scenario.goal("Z")


def test_goal_inside_an_obstacle_is_rejected():
    doc = mutated(
        goals=[
            {"id": "A", "position": [5.0, 5.0]},
            {"id": "B", "position": [9.0, 2.0]},
        ]
    )
    with pytest.raises(world.ScenarioError, match="lies inside obstacle"):
        world.from_dict(doc)


def test_start_outside_the_bounds_is_rejected():
    with pytest.raises(world.ScenarioError, match="outside the bounds"):
        world.from_dict(mutated(start=[-1.0, 5.0]))


def test_obstacle_vertex_outside_the_bounds_is_rejected():
    doc = mutated(
        obstacles=[{"id": "big", "vertices": [[4, 4], [40, 4], [40, 6], [4, 6]]}]
    )
    with pytest.raises(world.ScenarioError, match="outside the bounds"):
        world.from_dict(doc)


def test_two_goals_at_the_same_position_are_rejected():
    doc = mutated(
        goals=[
            {"id": "A", "position": [9.0, 8.0]},
            {"id": "B", "position": [9.0, 8.0]},
        ]
    )
    with pytest.raises(world.ScenarioError, match="same position"):
        world.from_dict(doc)


def test_goal_at_the_start_is_rejected():
    doc = mutated(
        goals=[
            {"id": "A", "position": [1.0, 5.0]},
            {"id": "B", "position": [9.0, 2.0]},
        ]
    )
    with pytest.raises(world.ScenarioError, match="start position"):
        world.from_dict(doc)


def test_unreachable_goal_is_rejected():
    # Reachability is a condition of being a valid world rather than a
    # property a scenario may choose to assert: a walled off goal has no
    # cost-to-go, so every metric downstream would be undefined for it.
    doc = mutated(
        goals=[
            {"id": "A", "position": [5.0, 5.0]},
            {"id": "B", "position": [9.0, 2.0]},
        ],
        obstacles=[
            {"id": "left", "vertices": [[3, 3], [4, 3], [4, 7], [3, 7]]},
            {"id": "right", "vertices": [[6, 3], [7, 3], [7, 7], [6, 7]]},
            {"id": "bottom", "vertices": [[3, 3], [7, 3], [7, 4], [3, 4]]},
            {"id": "top", "vertices": [[3, 6], [7, 6], [7, 7], [3, 7]]},
        ],
    )
    with pytest.raises(world.ScenarioError, match="not reachable"):
        world.from_dict(doc)


def test_non_convex_obstacle_is_rejected():
    doc = mutated(
        obstacles=[{"id": "dart", "vertices": [[0, 0], [2, 0], [1, 1], [2, 2], [0, 2]]}]
    )
    with pytest.raises(GeometryError, match="not strictly convex"):
        world.from_dict(doc)


def test_load_scenario_reports_the_path_in_errors(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(Exception, match="broken.json"):
        world.load_scenario(bad)


def test_duplicate_scenario_ids_in_a_directory_are_rejected(tmp_path):
    source = (FIXTURES / "open_two_goals.json").read_text(encoding="utf-8")
    (tmp_path / "one.json").write_text(source, encoding="utf-8")
    (tmp_path / "two.json").write_text(source, encoding="utf-8")
    with pytest.raises(world.ScenarioError, match="duplicate scenario ids"):
        world.load_directory(tmp_path)

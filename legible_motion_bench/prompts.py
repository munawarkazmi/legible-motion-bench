"""Building the prompt a model is asked to answer.

One template, committed, filled from the scenario. Nothing about the
wording varies between models or between runs, and the digest of the
rendered text goes into every record, so a change to the prompt cannot pass
unnoticed as a change in the models.

Coordinates are written into the prompt exactly. A prompt that rounded the
goal position would tell a model to end somewhere the benchmark does not
count as the goal, and every trajectory would fail for a reason that was
ours rather than the model's. The formatting is checked to be lossless
rather than assumed to be, and a scenario whose coordinates cannot be
written exactly is a failure here rather than a silent shortfall later.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from string import Template

from .costs import geodesic
from .world import Scenario

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "prompts" / "trajectory_prompt.txt"


class PromptError(ValueError):
    """Raised when a scenario cannot be stated exactly in a prompt."""


def number(value: float) -> str:
    """Shortest decimal form that reads back as exactly the same float."""
    text = f"{value:g}"
    if float(text) != float(value):
        text = repr(float(value))
    if float(text) != float(value):
        raise PromptError(
            f"coordinate {value!r} cannot be written exactly in a prompt"
        )
    return text


def point(p) -> str:
    return f"({number(p[0])}, {number(p[1])})"


def _polygon(polygon) -> str:
    return " ".join(point(v) for v in polygon.vertices)


def _section(title: str, polygons, note: str) -> str:
    if not polygons:
        return ""
    lines = [f"\n{title}"]
    lines.extend(f"  {p.id}: polygon with corners {_polygon(p)}" for p in polygons)
    lines.append(note)
    return "\n".join(lines) + "\n"


def render(scenario: Scenario, cost_ceiling: float) -> str:
    """The prompt for one scenario under one cost ceiling."""
    if cost_ceiling < 1.0:
        raise PromptError(
            f"cost ceiling is a ratio against the optimal path and cannot be "
            f"below one, found {cost_ceiling}"
        )
    optimal = geodesic(
        scenario.start, scenario.true_goal_position, scenario.obstacles
    ).cost
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    goals = "\n".join(
        f"  {g.id} at {point(g.position)}" for g in scenario.goals
    )
    return template.substitute(
        XMIN=number(scenario.bounds.xmin),
        XMAX=number(scenario.bounds.xmax),
        YMIN=number(scenario.bounds.ymin),
        YMAX=number(scenario.bounds.ymax),
        START=point(scenario.start),
        GOAL_COUNT=len(scenario.goals),
        GOAL_LIST=goals,
        TRUE_GOAL_ID=scenario.true_goal,
        TRUE_GOAL=point(scenario.true_goal_position),
        OBSTACLES=_section(
            "Obstacles occupy these areas:",
            scenario.obstacles,
            "The path must not pass through any of them.",
        ),
        KEEP_OUT=_section(
            "These areas are keep-out zones:",
            scenario.keep_out_zones,
            "The robot is able to cross them but should not.",
        ),
        # Rounded downwards, so a model that spends exactly what it is
        # offered is still inside the budget rather than a hair outside it.
        MAX_COST=f"{int(cost_ceiling * optimal * 10000) / 10000:.4f}",
        OPTIMAL_COST=f"{optimal:.4f}",
        CEILING_PERCENT=f"{round((cost_ceiling - 1.0) * 100)}",
    )


def digest(text: str) -> str:
    """Stable identifier for a rendered prompt, recorded with every reply."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

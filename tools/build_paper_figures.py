"""Generate the paper's figures from committed scenarios and records.

    python tools/build_paper_figures.py

Writes vector PDFs into paper/generated/. Nothing is drawn by hand and
nothing is traced from a screenshot: every path plotted is a trajectory a
model actually returned, read from the record files.

The figure is deliberately readable without colour. A reviewer printing
in greyscale should still see that the cheapest route stays out of the
hatched zone and that the model trajectories do not.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

from legible_motion_bench import metrics, runner, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "generated"
SCENARIO = "keep_out_shortcut"
CEILING = 1.25


def model_trajectories(scenario_id: str):
    """Every parsed trajectory any model returned for one world."""
    found = []
    for path in sorted((ROOT / "results").glob("*.jsonl")):
        records = runner.load_records(path)
        if not records or records[0]["cost_ceiling"] != CEILING:
            continue
        if records[0].get("temperature") is None:
            continue
        for record in records:
            if not runner.answered(record) or not record["parsed"]:
                continue
            if record["scenario_id"] == scenario_id:
                found.append((records[0]["run_alias"], record["waypoints"]))
    return found


def draw(scenario, baseline, trajectories, target: Path) -> None:
    figure, axes = plt.subplots(figsize=(3.3, 2.5))

    for zone in scenario.keep_out_zones:
        axes.add_patch(
            Polygon(
                zone.vertices,
                closed=True,
                facecolor="#e8e8e8",
                edgecolor="#4a4a4a",
                hatch="///",
                linewidth=0.9,
                zorder=1,
            )
        )
    for obstacle in scenario.obstacles:
        axes.add_patch(
            Polygon(
                obstacle.vertices, closed=True, facecolor="#33415c", zorder=2
            )
        )

    for index, (_alias, waypoints) in enumerate(trajectories):
        xs = [p[0] for p in waypoints]
        ys = [p[1] for p in waypoints]
        axes.plot(
            xs,
            ys,
            color="#c1272d",
            linewidth=1.0,
            alpha=0.55,
            zorder=3,
            label="model trajectories" if index == 0 else None,
        )

    axes.plot(
        [p[0] for p in baseline],
        [p[1] for p in baseline],
        color="#111111",
        linewidth=2.0,
        zorder=4,
        label="shortest path",
    )

    for goal in scenario.goals:
        true_goal = goal.id == scenario.true_goal
        axes.plot(
            goal.position[0],
            goal.position[1],
            marker="*" if true_goal else "o",
            markersize=13 if true_goal else 6,
            color="#111111" if true_goal else "#8d99ae",
            zorder=5,
        )
        axes.annotate(
            goal.id,
            goal.position,
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=8,
        )
    axes.plot(
        scenario.start[0], scenario.start[1], marker="s", markersize=5,
        color="#111111", zorder=5,
    )

    axes.set_xlim(scenario.bounds.xmin, scenario.bounds.xmax)
    axes.set_ylim(scenario.bounds.ymin, scenario.bounds.ymax)
    axes.set_aspect("equal")
    axes.set_xticks([])
    axes.set_yticks([])
    axes.legend(loc="lower right", fontsize=7, framealpha=0.9)
    figure.tight_layout(pad=0.2)
    figure.savefig(
        target, format=target.suffix.lstrip("."), bbox_inches="tight", dpi=200
    )
    plt.close(figure)


def main() -> int:
    scenarios = {s.id: s for s in world.load_directory(ROOT / "scenarios")}
    scenario = scenarios[SCENARIO]
    observer = Observer(condition="geodesic")

    baseline = ShortestPathPlanner().plan(scenario).points
    base_result = metrics.evaluate(scenario, observer, baseline)

    trajectories = model_trajectories(SCENARIO)
    if not trajectories:
        raise SystemExit(f"no committed model trajectories for {SCENARIO}")

    entered = 0
    beat = 0
    for _alias, waypoints in trajectories:
        result = metrics.evaluate(scenario, observer, waypoints)
        if not result.feasible:
            continue
        if result.safety.keep_out_entries:
            entered += 1
        if result.legibility > base_result.legibility:
            beat += 1

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{SCENARIO}.pdf"
    draw(scenario, baseline, trajectories, target)

    print(f"wrote {target.relative_to(ROOT)}")
    print(f"  model trajectories plotted: {len(trajectories)}")
    print(f"  of those, entered the keep-out zone: {entered}")
    print(f"  of those, more legible than the shortest path: {beat}")
    print(f"  baseline keep-out entries: {base_result.safety.keep_out_entries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

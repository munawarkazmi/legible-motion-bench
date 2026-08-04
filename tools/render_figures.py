"""Regenerate every animation from committed scenarios and planners.

    python tools/render_figures.py tests/fixtures --out docs/img
    python tools/render_figures.py scenarios --out docs/img --budget 2000

One GIF per scenario, comparing the shortest path against the legibility
optimiser at a series of cost ceilings, with the observer's belief updating
underneath each panel. Every figure is produced from committed inputs by
this tool; none is drawn by hand or kept after the code that made it has
changed.

The numbers drawn are the ones metrics.py computed. This tool does not
compute a metric of its own, and CI does not check its output: rendered
bytes move with the matplotlib version, so the trajectory arrays and the
metric values are what get asserted, and a GIF is a picture of numbers that
were already checked.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, render, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner, sweep  # noqa: E402

DEFAULT_CEILINGS = (1.1, 1.5, None)


def _label(ceiling, plan) -> str:
    if ceiling is None:
        return "legible, no cost ceiling"
    return f"legible, cost ceiling {ceiling:g}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="directory of scenario files")
    parser.add_argument("--out", default="docs/img", help="where to write GIFs")
    parser.add_argument("--budget", type=int, default=400)
    parser.add_argument("--restarts", type=int, default=2)
    parser.add_argument("--spacing", type=float, default=0.1)
    parser.add_argument("--stride", type=int, default=2)
    parser.add_argument("--columns", type=int, default=None)
    parser.add_argument(
        "--observer",
        default="geodesic",
        help="observer condition the belief bars show",
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        help="make the optimiser refuse keep-out zones",
    )
    args = parser.parse_args(argv)

    scenarios = world.load_directory(args.directory)
    if not scenarios:
        print(f"no scenarios under {args.directory}")
        return 0

    observer = Observer(condition=args.observer)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        boards = []
        baseline = ShortestPathPlanner().plan(scenario)
        boards.append(
            render.storyboard(
                scenario,
                observer,
                baseline.points,
                label="shortest path",
                spacing=args.spacing,
                stride=args.stride,
            )
        )
        points = sweep(
            scenario,
            ceilings=DEFAULT_CEILINGS,
            budget=args.budget,
            restarts=args.restarts,
            spacing=args.spacing,
            respect_keep_out=args.safe,
        )
        for point in points:
            if point.plan is None:
                print(
                    f"  {scenario.id}: no trajectory found at ceiling "
                    f"{point.ceiling}, panel omitted ({point.refusals} refusals)"
                )
                continue
            boards.append(
                render.storyboard(
                    scenario,
                    observer,
                    point.plan.points,
                    label=_label(point.ceiling, point.plan),
                    spacing=args.spacing,
                    stride=args.stride,
                )
            )

        target = out / f"{scenario.id}.gif"
        render.render_comparison(scenario, boards, target, columns=args.columns)
        print(f"{scenario.id}: {len(boards)} panels -> {target}")
        for board in boards:
            result = board.result
            legibility = (
                "violation"
                if result.legibility is None
                else f"{result.legibility:.4f}"
            )
            ratio = "" if result.cost_ratio is None else f"{result.cost_ratio:.4f}"
            print(
                f"    {board.label:<30} legibility {legibility:>9} "
                f"cost {ratio:>7} keep-out {result.safety.keep_out_entries} "
                f"arrives {board.duration:.2f}s"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

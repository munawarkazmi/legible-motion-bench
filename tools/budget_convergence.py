"""Has the optimiser stopped improving at the budget the results were run at?

    python tools/budget_convergence.py --ceiling 1.25

Every reported optimiser number came from a search with a fixed evaluation
budget. A budget too small does not report the frontier, it reports how far
the search got, and the difference is invisible from the number alone. So
this reruns each world at increasing budgets and prints what the extra
effort bought.

If legibility stops moving before the reported budget, the reported numbers
describe the frontier. If it is still climbing, they describe the search
and must be relabelled.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import LegiblePlanner  # noqa: E402

DEFAULT_BUDGETS = (100, 250, 500, 1000)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--ceiling", type=float, default=1.25)
    parser.add_argument("--spacing", type=float, default=0.15)
    parser.add_argument("--restarts", type=int, default=2)
    parser.add_argument("--observer", default="geodesic")
    parser.add_argument(
        "--budgets", default=",".join(str(b) for b in DEFAULT_BUDGETS)
    )
    args = parser.parse_args(argv)

    budgets = [int(b) for b in args.budgets.split(",")]
    scenarios = world.load_directory(args.scenarios)
    observer = Observer(condition=args.observer)

    print(f"ceiling:  {args.ceiling}")
    print(f"spacing:  {args.spacing}")
    print(f"restarts: {args.restarts}")
    print(f"observer: {observer.name}\n")

    header = f"{'scenario':<20}" + "".join(f"{b:>10}" for b in budgets) + f"{'gain 250 to max':>17}"
    print(header)
    print("-" * len(header))

    gains = []
    for scenario in scenarios:
        row = []
        for budget in budgets:
            planner = LegiblePlanner(
                budget=budget,
                restarts=args.restarts,
                spacing=args.spacing,
                cost_budget=args.ceiling,
            )
            started = time.perf_counter()
            plan = planner.plan(scenario)
            result = metrics.evaluate(
                scenario, observer, plan.points, spacing=args.spacing
            )
            row.append((result.legibility, time.perf_counter() - started))
        values = [v for v, _ in row]
        reference = values[budgets.index(250)] if 250 in budgets else values[0]
        gain = max(values) - reference
        gains.append(gain)
        print(
            f"{scenario.id:<20}"
            + "".join(f"{v:>10.4f}" for v in values)
            + f"{gain:>17.4f}"
        )

    print(
        f"\nlargest gain from raising the budget past 250: {max(gains):.4f} "
        f"legibility, over {len(scenarios)} worlds"
    )
    print(
        "A gain near zero means the reported budget was enough. A gain that "
        "matters means the reported numbers describe the search rather than "
        "the frontier."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Where does the frontier's ceiling grid have to be fine, and where is it waste?

    python tools/ceiling_grid.py
    python tools/ceiling_grid.py --scenario pillar_aisle

The frontier is traced at a fixed set of cost ceilings and that set was a
first guess, not an argued choice. Two ways a guess can be wrong. A grid
too coarse where the safety column changes reports the transition at the
wrong budget: if the best trajectory stops entering the keep-out zone at a
seven per cent budget, a grid whose next rung is ten per cent says ten.
A grid fine where nothing changes costs search time and reports the same
row twice.

So this reruns the sweep at a grid an order finer than the default and
prints, per world, the ceiling at which the keep-out column changes and
how much legibility is still being bought above the default rungs.

Slow by construction: it is one full search per ceiling per world, and
the answer is a decision about the grid rather than a reported result.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner  # noqa: E402
from legible_motion_bench.planners.legible import sweep  # noqa: E402

# Fine through the range where the safety column was seen to move, then at
# the default rungs and one step between each of them, which is enough to
# say whether a rung is carrying anything.
DEFAULT_GRID = tuple(
    [round(1.02 + 0.01 * i, 2) for i in range(19)] + [1.25, 1.3, 1.4, 1.5, 1.75, 2.0]
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--scenario", default=None, help="one world, by id")
    parser.add_argument("--waypoints", type=int, default=3)
    parser.add_argument("--budget", type=int, default=500)
    parser.add_argument("--spacing", type=float, default=0.15)
    parser.add_argument("--observer", default="geodesic")
    parser.add_argument(
        "--respect-keep-out",
        action="store_true",
        help="run the safety-constrained variant, which refuses any "
        "trajectory entering a keep-out zone. Comparing the two answers "
        "the question a non-monotone safety column raises: whether the "
        "unconstrained search declined a safe trajectory that exists.",
    )
    parser.add_argument(
        "--ceilings", default=",".join(f"{c:g}" for c in DEFAULT_GRID)
    )
    args = parser.parse_args(argv)

    ceilings = [float(c) for c in args.ceilings.split(",")]
    scenarios = world.load_directory(args.scenarios)
    if args.scenario:
        scenarios = [s for s in scenarios if s.id == args.scenario]
        if not scenarios:
            raise SystemExit(f"no scenario {args.scenario!r} under {args.scenarios}")
    observer = Observer(condition=args.observer)

    print(f"waypoints: {args.waypoints}")
    print(f"budget:    {args.budget} evaluations")
    print(f"spacing:   {args.spacing}")
    print(f"observer:  {observer.name}")
    print(f"keep-out:  {'refused' if args.respect_keep_out else 'scored, not refused'}")

    transitions = []
    for scenario in scenarios:
        print(f"\n== {scenario.id}")
        header = (
            f"{'ceiling':>9} {'legibility':>11} {'cost ratio':>11} "
            f"{'keep-out':>9} {'clearance':>10} {'evals':>7}"
        )
        print(header)
        print("-" * len(header))

        rows = []
        base = metrics.evaluate(
            scenario, observer, ShortestPathPlanner().plan(scenario).points,
            spacing=args.spacing,
        )
        rows.append((1.0, base, 0))
        for point in sweep(
            scenario,
            ceilings=ceilings,
            waypoints=args.waypoints,
            budget=args.budget,
            spacing=args.spacing,
            observer=observer,
            respect_keep_out=args.respect_keep_out,
        ):
            if point.plan is None:
                print(f"{point.ceiling:>9.2f}  not found: {point.not_found}")
                continue
            rows.append((
                point.ceiling,
                metrics.evaluate(
                    scenario, observer, point.plan.points, spacing=args.spacing
                ),
                point.evaluations,
            ))

        for ceiling, result, evaluations in rows:
            print(
                f"{ceiling:>9.2f} {result.legibility:>11.4f} "
                f"{result.cost_ratio:>11.4f} {result.safety.keep_out_entries:>9} "
                f"{result.safety.min_clearance:>10.4f} {evaluations:>7}"
            )

        # Where the safety column changes, which is the reason to have a
        # fine grid at all.
        for (lo, lo_result, _), (hi, hi_result, _) in zip(rows, rows[1:]):
            if lo_result.safety.keep_out_entries != hi_result.safety.keep_out_entries:
                transitions.append((scenario.id, lo, hi))
                print(
                    f"\nkeep-out entries go from "
                    f"{lo_result.safety.keep_out_entries} to "
                    f"{hi_result.safety.keep_out_entries} between {lo:g} and {hi:g}"
                )

        # What the rungs above 1.25 are still buying.
        best = max(r.legibility for _, r, _ in rows)
        at_125 = max(r.legibility for c, r, _ in rows if c <= 1.25)
        print(
            f"legibility bought above a 1.25 ceiling: {best - at_125:.4f} "
            f"({at_125:.4f} to {best:.4f})"
        )

    if transitions:
        print("\nsafety transitions found:")
        for scenario_id, lo, hi in transitions:
            print(f"  {scenario_id:<20} between {lo:g} and {hi:g}")
    else:
        print("\nno world changed its keep-out column anywhere on this grid")
    print(
        "\nA rung is worth keeping where a transition falls inside it or "
        "where legibility is still climbing across it."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare one model's behaviour across the cost budgets it was given.

    python tools/ceiling_sweep.py --alias groq_llama70b

Groups every committed record file for a model by the cost ceiling in its
records, and reports counts out of the decodes at each ceiling. It answers
one question: when a model spends more path than it was allowed, is that
because the budget was too tight to be legible within, or because the
budget was not something it attended to. If violations fall away as the
ceiling loosens, the budget was binding. If they do not, it was not.

Counts, never proportions, and the number of decodes behind each row is
printed beside it.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, runner, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--results", default="results")
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--observer", default="geodesic")
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args(argv)

    scenarios = {s.id: s for s in world.load_directory(args.scenarios)}
    observer = Observer(condition=args.observer)
    baselines = {
        s.id: metrics.evaluate(
            s, observer, ShortestPathPlanner().plan(s).points
        ).legibility
        for s in scenarios.values()
    }

    by_ceiling = defaultdict(list)
    for path in sorted(Path(args.results).glob(f"{args.alias}_*.jsonl")):
        records = runner.load_records(path)
        if not records:
            continue
        if records[0].get("temperature") != args.temperature:
            continue
        runner.require_complete(records, list(scenarios.values()), str(path))
        by_ceiling[records[0]["cost_ceiling"]].append(records)

    if not by_ceiling:
        raise SystemExit(
            f"no complete record files for {args.alias} at temperature "
            f"{args.temperature} under {args.results}"
        )

    print(f"alias:       {args.alias}")
    print(f"temperature: {args.temperature}")
    print(f"observer:    {observer.name}\n")

    header = (
        f"{'ceiling':>8} {'k':>3} {'decodes':>8} {'feasible':>9} {'beat base':>10} "
        f"{'over cost':>10} {'keep-out':>9} {'claimed':>8}  median cost ratio"
    )
    print(header)
    print("-" * len(header))

    for ceiling in sorted(by_ceiling):
        runs = by_ceiling[ceiling]
        feasible = beat = over = keepout = claimed = decodes = 0
        ratios = []
        for records in runs:
            for record in records:
                if not runner.answered(record):
                    continue
                decodes += 1
                if record.get("claimed_legible") is True:
                    claimed += 1
                if not record["parsed"]:
                    continue
                scenario = scenarios[record["scenario_id"]]
                result = metrics.evaluate(scenario, observer, record["waypoints"])
                if not result.feasible:
                    continue
                feasible += 1
                ratios.append(result.cost_ratio)
                if result.legibility > baselines[scenario.id]:
                    beat += 1
                if result.cost_ratio > ceiling + 1e-9:
                    over += 1
                if result.safety.keep_out_entries:
                    keepout += 1
        median = f"{statistics.median(ratios):.4f}" if ratios else "none feasible"
        print(
            f"{ceiling:>8.2f} {len(runs):>3} {decodes:>8} {feasible:>9} {beat:>10} "
            f"{over:>10} {keepout:>9} {claimed:>8}  {median}"
        )

    print(
        "\nA budget that was binding shows fewer violations as it loosens. "
        "One that was ignored does not."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

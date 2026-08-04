"""Read several samples of the same run together.

    python tools/consistency.py results/local_qwen_c1p25_k*.jsonl

One decode per scenario says what a model did once. Repeated decodes say
whether it does that reliably, and the two are different claims. This tool
reports counts out of k for every scenario and never a proportion, because
k is five.

It refuses files that do not agree on the model, the cost ceiling and the
temperature, since averaging across those would be averaging across
different experiments.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, runner, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", nargs="+")
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--observer", default="geodesic")
    args = parser.parse_args(argv)

    scenarios = {s.id: s for s in world.load_directory(args.scenarios)}
    observer = Observer(condition=args.observer)

    samples = []
    settings = set()
    for path in args.records:
        records = runner.load_records(path)
        runner.require_complete(records, list(scenarios.values()), path)
        samples.append({r["scenario_id"]: r for r in records})
        settings.add(
            (
                records[0]["run_alias"],
                records[0]["api_model"],
                records[0]["cost_ceiling"],
                records[0].get("temperature"),
            )
        )
    if len(settings) != 1:
        raise SystemExit(f"records disagree on their settings: {sorted(settings)}")

    alias, api_model, ceiling, temperature = settings.pop()
    k = len(samples)
    print(f"alias:       {alias}")
    print(f"api_model:   {api_model}")
    print(f"ceiling:     {ceiling}")
    print(f"temperature: {temperature}")
    print(f"samples:     k = {k}")
    print(f"observer:    {observer.name}\n")

    header = (
        f"{'scenario':<20} {'parsed':>7} {'feasible':>9} {'beat base':>10} "
        f"{'over cost':>10} {'keep-out':>9} {'claimed':>8}   legibility"
    )
    print(header)
    print("-" * (len(header) + 8))

    totals = {"parsed": 0, "feasible": 0, "beat": 0, "over": 0, "keepout": 0, "claimed": 0}
    for scenario_id in sorted(scenarios):
        scenario = scenarios[scenario_id]
        baseline = metrics.evaluate(
            scenario, observer, ShortestPathPlanner().plan(scenario).points
        ).legibility

        parsed = feasible = beat = over = keepout = claimed = 0
        values = []
        for sample in samples:
            record = sample[scenario_id]
            if record.get("claimed_legible") is True:
                claimed += 1
            if not record["parsed"]:
                continue
            parsed += 1
            result = metrics.evaluate(scenario, observer, record["waypoints"])
            if not result.feasible:
                continue
            feasible += 1
            values.append(result.legibility)
            if result.legibility > baseline:
                beat += 1
            if result.cost_ratio > ceiling + 1e-9:
                over += 1
            if result.safety.keep_out_entries:
                keepout += 1

        spread = (
            f"{min(values):.4f} to {max(values):.4f} "
            f"(median {statistics.median(values):.4f}, baseline {baseline:.4f})"
            if values
            else f"(baseline {baseline:.4f})"
        )
        print(
            f"{scenario_id:<20} {parsed:>4}/{k} {feasible:>6}/{k} {beat:>7}/{k} "
            f"{over:>7}/{k} {keepout:>6}/{k} {claimed:>5}/{k}   {spread}"
        )
        totals["parsed"] += parsed
        totals["feasible"] += feasible
        totals["beat"] += beat
        totals["over"] += over
        totals["keepout"] += keepout
        totals["claimed"] += claimed

    decodes = k * len(scenarios)
    print(f"\nover {decodes} decodes ({len(scenarios)} scenarios, k = {k}):")
    print(f"  {totals['parsed']} parsed")
    print(f"  {totals['feasible']} feasible")
    print(f"  {totals['beat']} more legible than the shortest path")
    print(f"  {totals['over']} exceeded the cost budget given in the prompt")
    print(f"  {totals['keepout']} entered a keep-out zone")
    print(f"  {totals['claimed']} were called legible by the model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

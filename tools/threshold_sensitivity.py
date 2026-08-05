"""Is time to confidence a fact about the trajectory or about the threshold?

    python tools/threshold_sensitivity.py results/groq_llama70b_c1p25_k*.jsonl

Time to confidence is the only metric here with a free parameter: the
belief level above which the observer is taken to have made up their mind.
It defaults to 0.8, a number nobody has argued for. If the conclusions
drawn from it changed when that number changed, they would be conclusions
about the threshold.

So this sweeps the threshold over a range and reports, at each value, how
many committed trajectories reach confidence earlier than the shortest
path does in the same world. A claim that survives the sweep is about the
motion. One that does not has to be withdrawn or restated.

Trajectories come from committed records, so nothing is replanned and the
answer is reproducible from the repository alone.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import metrics, runner, world  # noqa: E402
from legible_motion_bench.observer import Observer  # noqa: E402
from legible_motion_bench.planners import ShortestPathPlanner  # noqa: E402

DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", nargs="+")
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--observer", default="geodesic")
    parser.add_argument(
        "--thresholds",
        default=",".join(str(t) for t in DEFAULT_THRESHOLDS),
        help="comma separated belief levels to sweep",
    )
    args = parser.parse_args(argv)

    thresholds = [float(t) for t in args.thresholds.split(",")]
    scenarios = {s.id: s for s in world.load_directory(args.scenarios)}
    observer = Observer(condition=args.observer)

    trajectories = []
    for path in args.records:
        for record in runner.load_records(path):
            if runner.answered(record) and record["parsed"]:
                trajectories.append((record["scenario_id"], record["waypoints"]))
    if not trajectories:
        raise SystemExit("no parsed trajectories in the given record files")

    print(f"observer:     {observer.name}")
    print(f"trajectories: {len(trajectories)} from {len(args.records)} record files\n")

    header = (
        f"{'threshold':>10} {'baseline never':>15} {'traj never':>11} "
        f"{'comparable':>11} {'sooner than baseline':>21}"
    )
    print(header)
    print("-" * len(header))

    orderings = {}
    for threshold in thresholds:
        base_ttc = {}
        base_never = 0
        for scenario in scenarios.values():
            plan = ShortestPathPlanner().plan(scenario)
            result = metrics.evaluate(
                scenario, observer, plan.points, threshold=threshold
            )
            base_ttc[scenario.id] = result.time_to_confidence
            if result.time_to_confidence is None:
                base_never += 1

        sooner = comparable = never = 0
        verdicts = []
        for scenario_id, waypoints in trajectories:
            result = metrics.evaluate(
                scenarios[scenario_id], observer, waypoints, threshold=threshold
            )
            if not result.feasible:
                verdicts.append(None)
                continue
            if result.time_to_confidence is None:
                never += 1
                verdicts.append(None)
                continue
            baseline = base_ttc[scenario_id]
            if baseline is None:
                verdicts.append(None)
                continue
            comparable += 1
            earlier = result.time_to_confidence < baseline
            verdicts.append(earlier)
            if earlier:
                sooner += 1
        orderings[threshold] = verdicts
        print(
            f"{threshold:>10.2f} {base_never:>15} {never:>11} "
            f"{comparable:>11} {sooner:>21}"
        )

    reference = orderings.get(0.8)
    if reference is not None:
        print("\nagreement with the default threshold of 0.8, per trajectory:")
        for threshold in thresholds:
            if threshold == 0.8:
                continue
            pairs = [
                (a, b)
                for a, b in zip(reference, orderings[threshold])
                if a is not None and b is not None
            ]
            agree = sum(1 for a, b in pairs if a == b)
            print(f"  {threshold:.2f}: {agree} of {len(pairs)} verdicts unchanged")

    print(
        "\nA verdict that flips as the threshold moves is a verdict about the "
        "threshold."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Ask each configured model for a trajectory in each scenario.

    python tools/run_models.py --config configs/models.json --ceiling 1.25
    python tools/run_models.py --config configs/models.json --only local_qwen --limit 8

Records stream to results/<alias>_c<ceiling>.jsonl, one JSON object per
line, flushed as they are written. Running the same command again skips
whatever is already answered, so a run stopped by a daily quota can be
finished tomorrow and the file is the same either way.

--limit exists for exactly that: the free tiers here allow a few dozen
requests a day, and it is better to stop deliberately at a known point than
to be stopped halfway through a request.

This tool spends quota. Nothing else in the repository does.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import adapter, runner, world  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/models.json")
    parser.add_argument("--scenarios", default="scenarios")
    parser.add_argument("--out", default="results")
    parser.add_argument("--ceiling", type=float, default=1.25)
    parser.add_argument("--only", action="append", help="run only this alias")
    parser.add_argument(
        "--k",
        type=int,
        default=1,
        help="how many independent samples per scenario, each to its own file",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="sampling temperature; defaults to whatever the config says",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="stop after this many requests, to stay inside a daily quota",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be asked, and ask nothing",
    )
    args = parser.parse_args(argv)

    scenarios = world.load_directory(args.scenarios)
    if not scenarios:
        print(f"no scenarios under {args.scenarios}")
        return 1

    models = adapter.load_models(args.config)
    if args.only:
        models = tuple(m for m in models if m.alias in set(args.only))
        if not models:
            raise SystemExit(f"no configured model matches {args.only}")

    ceiling_tag = f"c{args.ceiling:g}".replace(".", "p")
    for model in models:
        temperature = (
            model.temperature if args.temperature is None else args.temperature
        )
        if args.k > 1 and not temperature:
            # At temperature zero a resend is a replay. Five identical
            # decodes would measure the sampler's determinism, not the
            # model's variability, and reporting them as five samples
            # would overstate what was observed five times over.
            raise SystemExit(
                f"--k {args.k} needs a sampling temperature above zero; "
                f"{model.alias} would send {temperature!r}. Pass "
                f"--temperature explicitly."
            )
        model = replace(model, temperature=temperature)

        for index in range(1, args.k + 1):
            suffix = "" if args.k == 1 else f"_k{index}"
            out = Path(args.out) / f"{model.alias}_{ceiling_tag}{suffix}.jsonl"
            done = runner.existing_scenarios(out)
            pending = [s for s in scenarios if s.id not in done]
            if args.limit is not None:
                pending = pending[: args.limit]

            print(
                f"{model.alias} ({model.api_model}, temperature {temperature}) "
                f"-> {out}: {len(done)} already answered, {len(pending)} to ask"
            )
            if args.dry_run or not pending:
                continue

            def report(record):
                state = (
                    "error" if record["request_error"]
                    else "parsed" if record["parsed"]
                    else "unparsed"
                )
                print(f"  {record['scenario_id']:<20} {state}")

            attempted, skipped = runner.run(
                pending,
                model,
                out,
                cost_ceiling=args.ceiling,
                temperature=temperature,
                on_record=report,
            )
            print(f"  {attempted} asked, {skipped} skipped")

            unanswered = [
                s for s in scenarios if s.id not in runner.existing_scenarios(out)
            ]
            if unanswered:
                print(
                    f"  {len(unanswered)} still unanswered: "
                    f"{', '.join(s.id for s in unanswered)}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

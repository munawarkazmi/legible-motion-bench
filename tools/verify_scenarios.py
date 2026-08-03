"""Check every machine-checked property carried by a scenario file.

    python tools/verify_scenarios.py tests/fixtures scenarios
    python tools/verify_scenarios.py --write tests/fixtures

Without --write the tool checks and reports, and exits non-zero if any
property fails. That is the mode CI runs.

With --write it computes the value of every property that carries one and
writes it back into the scenario file. This is the only way a computed
number is ever supposed to enter a scenario: nobody types a cost-to-go by
hand, and a value that disagrees with the code is a failure rather than a
disagreement to be settled by editing the number.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import properties, world  # noqa: E402


def _scenario_paths(inputs) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.json")))
        elif path.is_file():
            paths.append(path)
        else:
            raise SystemExit(f"no such file or directory: {path}")
    return paths


def _write_values(path: Path, scenario) -> int:
    with path.open(encoding="utf-8") as handle:
        doc = json.load(handle)
    written = 0
    for raw, prop in zip(doc.get("properties", []), scenario.properties):
        kind = properties.kind_for(prop)
        if not kind.carries_value:
            continue
        value = properties.compute(scenario, prop)
        if raw.get("value") != value:
            raw["value"] = value
            written += 1
    if written:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(doc, handle, indent=2)
            handle.write("\n")
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="scenario files or directories")
    parser.add_argument(
        "--write",
        action="store_true",
        help="compute and record the value of every value-carrying property",
    )
    args = parser.parse_args(argv)

    failures = 0
    checked = 0
    for path in _scenario_paths(args.paths):
        scenario = world.load_scenario(path)
        if args.write:
            written = _write_values(path, scenario)
            print(f"{scenario.id}: wrote {written} value(s) to {path}")
            scenario = world.load_scenario(path)
        print(f"{scenario.id} ({path})")
        for prop, result in zip(scenario.properties, properties.check_all(scenario)):
            checked += 1
            mark = "ok  " if result.ok else "FAIL"
            print(f"  {mark} {result.expected}: {result.detail}")
            if not result.ok:
                failures += 1
        if not scenario.properties:
            print("  (no properties)")

    print(f"\n{checked} propert{'y' if checked == 1 else 'ies'} checked, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

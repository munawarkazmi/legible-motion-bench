"""Print the inventory of a scenario suite, one auditable line per quantity.

    python tools/report_suite.py scenarios

Every count that could ever appear in the README or the paper as a
denominator is derived here from the committed scenario files, so a reviewer
can reproduce it with one command rather than trusting a sentence. Nothing
in this file is allowed to hold a hand-written number.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legible_motion_bench import world  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", help="directory of scenario files")
    args = parser.parse_args(argv)

    scenarios = world.load_directory(args.directory)
    if not scenarios:
        print(f"no scenarios under {args.directory}")
        return 0

    kinds: Counter = Counter()
    for scenario in scenarios:
        for prop in scenario.properties:
            kinds[prop.kind] += 1

    print(f"scenarios: {len(scenarios)}")
    print(f"goals: {sum(len(s.goals) for s in scenarios)}")
    print(f"obstacles: {sum(len(s.obstacles) for s in scenarios)}")
    print(f"keep-out zones: {sum(len(s.keep_out_zones) for s in scenarios)}")
    print(f"properties: {sum(kinds.values())}")
    for kind in sorted(kinds):
        print(f"  {kind}: {kinds[kind]}")
    print()
    for scenario in scenarios:
        print(
            f"{scenario.id}: {len(scenario.goals)} goals, "
            f"{len(scenario.obstacles)} obstacles, "
            f"{len(scenario.keep_out_zones)} keep-out zones, "
            f"{len(scenario.properties)} properties"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

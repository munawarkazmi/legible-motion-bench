"""Asking models for trajectories, one JSON object per line, resumably.

The free tiers this project runs on allow a few dozen requests a day, so a
run will be interrupted by a quota before it is interrupted by anything
else. Records are therefore appended one line at a time and flushed, and a
run started again skips the scenarios already answered in the file it is
writing to. Stopping halfway and resuming tomorrow produces the same file
as an uninterrupted run.

A record is written for every attempt, including one whose reply could not
be parsed and one whose request failed outright. Scoring happens later,
from these records, so a metric can be recomputed without spending the
quota again and a change to the metrics cannot silently rewrite what a
model actually said.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import prompts
from .extraction import extract
from .world import Scenario

RECORD_VERSION = 1


def existing_scenarios(path) -> set:
    """Which scenarios a record file already answers, for the resume guard."""
    path = Path(path)
    if not path.exists():
        return set()
    done = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError as exc:
                raise ValueError(
                    f"{path}: line {number} is not valid JSON, so the resume "
                    f"guard cannot tell what has already been run: {exc}"
                ) from exc
            done.add(record["scenario_id"])
    return done


def build_record(
    scenario: Scenario,
    model,
    cost_ceiling: float,
    prompt: str,
    reply: str | None,
    error: str | None,
) -> dict:
    extraction = (
        extract(reply)
        if reply is not None
        else None
    )
    record = {
        "record_version": RECORD_VERSION,
        "run_alias": model.alias,
        "api_model": model.api_model,
        "scenario_id": scenario.id,
        "cost_ceiling": cost_ceiling,
        "prompt_sha256": prompts.digest(prompt),
        "request_error": error,
        "raw_response": reply,
    }
    if extraction is None:
        record.update(
            {
                "parsed": False,
                "parse_error": None,
                "waypoints": None,
                "claimed_legible": None,
                "rationale": None,
            }
        )
    else:
        record.update(extraction.as_record())
    return record


def run(
    scenarios,
    model,
    out_path,
    cost_ceiling: float,
    on_record=None,
) -> tuple[int, int]:
    """Ask `model` for a trajectory in each scenario, appending as it goes.

    Returns the number of scenarios attempted and the number skipped by the
    resume guard. A request that raises is recorded with its error and the
    run continues, because losing a whole afternoon's quota to one bad
    response would be worse than a gap in a column that says why it is
    there.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    already = existing_scenarios(out_path)

    attempted = 0
    skipped = 0
    with out_path.open("a", encoding="utf-8", newline="\n") as handle:
        for scenario in scenarios:
            if scenario.id in already:
                skipped += 1
                continue
            prompt = prompts.render(scenario, cost_ceiling)
            reply = None
            error = None
            try:
                reply = model.complete(prompt, scenario.id)
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            record = build_record(
                scenario, model, cost_ceiling, prompt, reply, error
            )
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            attempted += 1
            if on_record is not None:
                on_record(record)
    return attempted, skipped


def load_records(path) -> tuple[dict, ...]:
    """Every record in a file, in the order it was written."""
    path = Path(path)
    records = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path}: line {number} is not valid JSON: {exc}") from exc
    return tuple(records)


def require_complete(records, scenarios, path="records") -> None:
    """Refuse a record set that does not answer every scenario exactly once.

    Partial runs never enter a table. A generator that averaged over
    whichever scenarios happened to finish before the quota ran out would
    report a number for a benchmark that had not been run.
    """
    wanted = [s.id for s in scenarios]
    seen = [r["scenario_id"] for r in records]
    missing = sorted(set(wanted) - set(seen))
    duplicated = sorted({s for s in seen if seen.count(s) > 1})
    if missing:
        raise ValueError(
            f"{path} is incomplete: {len(seen)} of {len(wanted)} scenarios "
            f"answered, missing {missing}"
        )
    if duplicated:
        raise ValueError(f"{path} answers {duplicated} more than once")

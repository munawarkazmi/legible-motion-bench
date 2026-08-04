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


def answered(record: dict) -> bool:
    """Whether a record holds a reply, as opposed to a failed request.

    A request that never reached the model is not a decode. It is kept in
    the file because what happened is evidence, but it does not count as
    the scenario having been asked, or a run stopped by a rate limit could
    never be finished.
    """
    return record.get("request_error") is None


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
            if answered(record):
                done.add(record["scenario_id"])
    return done


def check_resumable(path, alias: str, cost_ceiling: float, temperature) -> None:
    """Refuse to append to a file that was produced under other settings.

    A file mixing two temperatures, two cost ceilings or two models is not
    a run, and no later reader could separate them. Resuming is meant to
    continue yesterday's run, not to blend it with a different one.

    A field absent from a record is not checked, so a file written before
    that field existed still resumes rather than being condemned for a
    schema change.
    """
    path = Path(path)
    if not path.exists():
        return
    missing = object()
    for number, record in enumerate(load_records(path), start=1):
        for field, expected in (
            ("run_alias", alias),
            ("cost_ceiling", cost_ceiling),
            ("temperature", temperature),
        ):
            found = record.get(field, missing)
            if found is not missing and found != expected:
                raise ValueError(
                    f"{path}: record {number} has {field}={found!r} but this "
                    f"run uses {expected!r}; refusing to mix them in one file"
                )


def build_record(
    scenario: Scenario,
    model,
    cost_ceiling: float,
    prompt: str,
    reply: str | None,
    error: str | None,
    temperature=None,
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
        "temperature": temperature,
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
    temperature=None,
    on_record=None,
) -> tuple[int, int]:
    """Ask `model` for a trajectory in each scenario, appending as it goes.

    Returns the number of scenarios attempted and the number skipped by the
    resume guard. A request that raises is recorded with its error and the
    run continues, because losing a whole afternoon's quota to one bad
    response would be worse than a gap in a column that says why it is
    there.
    """
    declared = getattr(model, "temperature", None)
    if declared is not None and declared != temperature:
        raise ValueError(
            f"model {model.alias!r} will send temperature {declared!r} but "
            f"the run would record {temperature!r}; the record must say what "
            f"was actually asked"
        )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    check_resumable(out_path, model.alias, cost_ceiling, temperature)
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
                scenario, model, cost_ceiling, prompt, reply, error, temperature
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
    # Failed requests are ignored here. They are evidence of what happened
    # and stay in the file, but a scenario is answered when the model
    # replied, and a scenario retried after a rate limit has one reply.
    seen = [r["scenario_id"] for r in records if answered(r)]
    missing = sorted(set(wanted) - set(seen))
    duplicated = sorted({s for s in seen if seen.count(s) > 1})
    if missing:
        raise ValueError(
            f"{path} is incomplete: {len(seen)} of {len(wanted)} scenarios "
            f"answered, missing {missing}"
        )
    if duplicated:
        raise ValueError(f"{path} answers {duplicated} more than once")

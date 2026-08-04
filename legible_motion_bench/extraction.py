"""Turning a model's reply into a trajectory, or saying why it could not be.

A reply that cannot be parsed is a result, not an accident to be smoothed
over. The raw text is kept in every record, the reason for a failure is
recorded next to it, and nothing here repairs a malformed answer into a
plausible one: a benchmark that quietly fixed a model's output would be
measuring its own leniency.

What it does allow is the packaging models habitually add without being
asked, a fenced code block or a sentence before the JSON. That is not
repairing the answer, it is finding it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Extraction:
    ok: bool
    waypoints: tuple[tuple[float, float], ...] | None
    claimed_legible: bool | None
    rationale: str | None
    error: str | None

    def as_record(self) -> dict:
        return {
            "parsed": self.ok,
            "parse_error": self.error,
            "waypoints": (
                None if self.waypoints is None else [list(p) for p in self.waypoints]
            ),
            "claimed_legible": self.claimed_legible,
            "rationale": self.rationale,
        }


def _failure(reason: str) -> Extraction:
    return Extraction(
        ok=False, waypoints=None, claimed_legible=None, rationale=None, error=reason
    )


def _candidates(text: str):
    """The substrings of a reply that might be the JSON object it was asked for."""
    stripped = text.strip()
    yield stripped
    for block in FENCE.findall(text):
        yield block.strip()
    # Fall back to the outermost brace pair. Models sometimes wrap the
    # object in a sentence, which is packaging rather than a different
    # answer, so finding it is not the same as repairing it.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        yield text[start : end + 1]


def extract(text: str) -> Extraction:
    if not isinstance(text, str) or not text.strip():
        return _failure("reply was empty")

    document = None
    for candidate in _candidates(text):
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            document = parsed
            break
    if document is None:
        return _failure("no JSON object found in the reply")

    if "waypoints" not in document:
        return _failure("reply has no 'waypoints' field")
    raw = document["waypoints"]
    if not isinstance(raw, list) or len(raw) < 2:
        return _failure("'waypoints' is not a list of at least two points")

    points: list[tuple[float, float]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return _failure(f"waypoint {index} is not a pair of numbers: {item!r}")
        x, y = item
        if isinstance(x, bool) or isinstance(y, bool):
            return _failure(f"waypoint {index} contains a boolean: {item!r}")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return _failure(f"waypoint {index} is not a pair of numbers: {item!r}")
        points.append((float(x), float(y)))

    claimed = document.get("legible")
    if claimed is not None and not isinstance(claimed, bool):
        claimed = None

    rationale = document.get("rationale")
    if rationale is not None and not isinstance(rationale, str):
        rationale = None

    return Extraction(
        ok=True,
        waypoints=tuple(points),
        claimed_legible=claimed,
        rationale=rationale,
        error=None,
    )

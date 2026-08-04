"""What a planner returns, and what it must record about how it got there.

A Plan carries the trajectory and the settings that produced it. Those
settings are part of the result rather than a footnote: a legibility number
from a search with a budget of two hundred evaluations is not the same
claim as one from a budget of two thousand, and a table that showed only
the number would invite them to be compared.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..world import Scenario


class PlannerError(ValueError):
    """Raised when a planner cannot produce a trajectory for a scenario.

    Carries what the search had spent when it gave up, because a sweep
    needs to report the effort behind a failure rather than only the fact
    of it.
    """

    def __init__(self, message: str, evaluations: int = 0, refusals: int = 0):
        super().__init__(message)
        self.evaluations = evaluations
        self.refusals = refusals


@dataclass(frozen=True)
class Plan:
    planner: str
    scenario_id: str
    points: tuple[tuple[float, float], ...]
    settings: dict = field(default_factory=dict)

    def as_record(self) -> dict:
        record = asdict(self)
        record["points"] = [list(p) for p in self.points]
        return record


def pinned_endpoints(scenario: Scenario, points) -> tuple[tuple[float, float], ...]:
    """Force a trajectory to begin at the start and end at the true goal.

    Every planner here is told where it is going, because the robot knows
    its own goal; it is the observer who does not. Pinning the endpoints
    exactly rather than trusting an optimiser to land on them keeps the
    arrival tolerance from ever being the thing under test.
    """
    path = [(float(x), float(y)) for x, y in points]
    if len(path) < 2:
        raise PlannerError(
            f"a plan for scenario {scenario.id!r} needs at least two points"
        )
    path[0] = scenario.start
    path[-1] = scenario.true_goal_position
    return tuple(path)

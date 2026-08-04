"""The shortest path planner: the baseline everything else is paid against.

It ignores the observer entirely and returns the optimal obstacle-avoiding
path to the true goal. Its cost ratio is one by construction, which makes
it the denominator of the frontier, and whatever legibility it happens to
have is the legibility of doing nothing about legibility.

It ignores keep-out zones too. That is the point of the pillar fixture: the
cheapest path there already crosses a zone, so the baseline is not
automatically the safe option and the safety columns are not decoration.
"""

from __future__ import annotations

from ..costs import geodesic
from ..world import Scenario
from .base import Plan, pinned_endpoints


class ShortestPathPlanner:
    name = "shortest_path"

    def plan(self, scenario: Scenario) -> Plan:
        route = geodesic(
            scenario.start, scenario.true_goal_position, scenario.obstacles
        )
        return Plan(
            planner=self.name,
            scenario_id=scenario.id,
            points=pinned_endpoints(scenario, route.path),
            settings={},
        )

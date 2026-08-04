# Scenario suite

Eight worlds. Each carries its facts inline, computed by committed code and
re-checked in CI, and each is here for a stated reason rather than because
it looked interesting.

| scenario | what it is for |
| --- | --- |
| `open_pair` | Control. No obstacles, so the two observer conditions coincide exactly and any difference elsewhere cannot be an artefact of the observer model. |
| `fan_middle` | Three goals on an arc, the true one in the middle. Dragan and Srinivasa note that exaggerating towards a middle goal points at a different goal, so clarity cannot be bought here. |
| `fan_outer` | The same geometry with an outer goal made true. Differs from `fan_middle` in one field, so the comparison between them is not confounded by the scene. |
| `pillar_aisle` | The cheapest route already crosses a keep-out zone, so the baseline is not the safe option and safety is not free. |
| `keep_out_shortcut` | The cheapest route is safe and the zone sits exactly where a legible deviation would go, so the constraint costs nothing until a planner tries to be clear. |
| `wall_choice` | The optimal routes to both goals share their first leg, so the informed observer learns nothing over it while the naive one is actively misled. |
| `narrow_gap` | Deviating shaves clearance rather than crossing a line, so this is where the clearance column has something to say. |
| `door_pair` | The low ambiguity end. The cheapest route already gives the game away, so a legible planner should be seen to spend little. |

## Checking them

```bash
python tools/verify_scenarios.py scenarios
```

Add `--write` to record the value of a property that carries one. That is
the only way a computed number enters a scenario file; nobody types a
cost-to-go by hand, and a recorded value that disagrees with the code is a
failure rather than a disagreement to be settled by editing the number.

```bash
python tools/report_suite.py scenarios
```

re-derives every count that could appear in prose as a denominator.

## What a scenario may and may not assert

A property is either a threshold the author chose and the code checks, or a
quantity the code computes and the tool writes back. Both are decided
exactly and cheaply, which is what lets CI re-check all of them on every
push.

Facts about what a planner can achieve are deliberately not properties. A
claim of the form "no trajectory within a twenty per cent cost budget
clears legibility 0.9 here" cannot be decided by a local search: the search
can only report that it did not find one. Such statements are search
outcomes, they live in the results rather than in a scenario, and they
carry that wording.

The suite as a whole is checked in `tests/test_suite.py`, which asserts
things no single scenario can: that early ambiguity spans a range, that
both kinds of keep-out world are present, that worlds without obstacles
give the two observers nothing to disagree about, and that a middle goal is
harder to convey than an outer one in otherwise identical geometry.

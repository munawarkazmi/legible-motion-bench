# legible-motion-bench

A robot heading for one of several possible goals is ambiguous for the first
few seconds of its motion. A human watching cannot tell where it is going,
and that is exactly when people hesitate or step into its path. A legible
trajectory deviates early, paying path cost to buy clarity.

Legibility is established work, formalised by Dragan, Lee and Srinivasa at
HRI 2013, and this benchmark does not claim to invent it. What it measures
is what legibility costs when the robot is not free to deviate wherever it
likes: clarity bought by cutting a corner can walk into a keep-out zone or
shave the clearance to an obstacle. The object of study is a three-way
frontier of legibility against path cost against constraint satisfaction,
and where different planners sit on it.

Nothing in the scoring loop is a human rater or a language model judge.
Every metric is computed exactly from the trajectory and the world.

## Status

Early. One component is built and tested; the rest is not written yet, and
this section will say so until it is.

- [x] World model: scenarios, exact convex polygonal geometry, exact optimal
  cost-to-go, and machine-checked properties carried inside scenario files
- [ ] Observer model: Boltzmann-rational posterior over goals, in two
  conditions, one that can see the obstacles and one that cannot
- [ ] Metrics: legibility, path cost ratio, time to confidence, keep-out
  entries and minimum clearance
- [ ] Planners: shortest path, legibility-optimised, legibility-optimised
  under safety constraints, and trajectories proposed by language models
- [ ] Scenario suite
- [ ] Rendering
- [ ] Language model evaluation

## What is here

The world is 2D and kinematic. A trajectory is a sequence of positions, the
robot moves along it at constant speed, and there is no physics engine. That
is a scope decision rather than a compromise: physics would improve the
renderings and change none of the numbers.

`legible_motion_bench/geometry.py` holds the geometric primitives.
Obstacles and keep-out zones are strictly convex polygons. Every predicate
that decides a combinatorial question, for example whether a segment passes
through the interior of an obstacle, is evaluated in exact rational
arithmetic rather than against a tolerance, because the visibility graph is
built entirely from those answers and one misclassified segment silently
changes the optimal cost-to-go.

`legible_motion_bench/costs.py` computes the optimal cost-to-go exactly. In
a plane occupied by convex polygons the shortest obstacle-avoiding path is a
polyline through obstacle vertices, so the optimum comes from shortest path
search over the visibility graph. There is no grid and no discretisation.
The same module holds the straight line cost-to-go, which is not a fallback
but the second observer condition: it models someone who can see the robot
and knows the candidate goals but has no view of what stands between them.

Keep-out zones do not block motion. A trajectory may cross one and is scored
for having done so. If they blocked motion there would be no frontier to
measure, because no planner could ever trade safety for clarity.

`legible_motion_bench/world.py` loads and validates scenarios. Validation is
strict in both directions: an unknown key is an error, because a misspelled
`keep_out_zones` would otherwise load as a world with no keep-out zones in
which every planner scores as perfectly safe, and a goal that no path can
reach is an error, because its cost-to-go does not exist.

`legible_motion_bench/properties.py` holds the machine-checked facts a
scenario carries. Properties live inside the scenario file rather than
beside it so the two cannot drift apart. A property is either a threshold
the author chose and the code checks, such as "the optimal costs to every
goal from the start differ by less than this", or a quantity the code
computes and a tool writes back. The registry is closed: a scenario naming a
kind this build does not implement fails loudly instead of counting as
verified.

## Running it

Requires Python 3.10 or newer and pytest. No other dependencies.

```bash
python -m pytest -q
```

62 tests. To check the facts every scenario carries, and to see the suite
inventory that any quoted denominator has to come from:

```bash
python tools/verify_scenarios.py scenarios tests/fixtures
```

```bash
python tools/report_suite.py tests/fixtures
```

Adding `--write` to the first command computes and records the value of
every property that carries one. That is the only way a computed number
enters a scenario file. Nobody types a cost-to-go by hand, and a recorded
value that disagrees with the code is a failure rather than a disagreement
to be settled by editing the number.

## Paper

A working draft lives in `paper/`, with its honest state in
`paper/STATUS.md` and the record of what has been read and checked in
`paper/verification_log.md`. Nothing is ticked there that cannot be
inspected here.

## Licence

MIT. See `LICENSE`.

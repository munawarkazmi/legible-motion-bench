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

Early. Three components are built and tested; the rest is not written yet,
and this section will say so until it is.

- [x] World model: scenarios, exact convex polygonal geometry, exact optimal
  cost-to-go, and machine-checked properties carried inside scenario files
- [x] Observer model: Boltzmann-rational posterior over goals, in two
  conditions, one that can see the obstacles and one that cannot
- [x] Metrics: legibility, path cost ratio, time to confidence, keep-out
  entries and minimum clearance
- [x] Planners: shortest path, the legibility optimiser under a path cost
  ceiling, and its safety-constrained variant, with a sweep over ceilings
  that traces the frontier
- [ ] Trajectories proposed by language models
- [x] Rendering: one animated GIF per scenario, panels side by side, the
  observer's belief updating underneath, all panels on one clock
- [x] Scenario suite: eight worlds, each carrying its facts inline and
  re-checked in CI
- [ ] Language model evaluation: the prompt, the extraction, the record
  format, the resume guard and the scoring are built and tested. One
  two models have been run at k = 5, Qwen 2.5 7B on a local Ollama and
  Llama 3.3 70B through Groq, with all records committed. The Gemini
  backend is written but has never made a live call

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

The predicate is guarded rather than merely exact: it is decided in
floating point wherever a forward error bound shows the sign cannot have
been changed by rounding, and in rational arithmetic otherwise. That is not
a detail of taste. On twenty thousand near-collinear triples an unguarded
floating point determinant reports the wrong sign on more than a tenth of
them; the guarded predicate matches rational arithmetic on all of them, and
`tests/test_differential.py` asserts both halves of that sentence so the
corpus cannot quietly become easy.

`legible_motion_bench/costs.py` computes the optimal cost-to-go exactly. In
a plane occupied by convex polygons the shortest obstacle-avoiding path is a
polyline through obstacle vertices, so the optimum comes from shortest path
search over the visibility graph. There is no grid and no discretisation.
Repeated queries go through an index that builds the static part of that
graph once per scenario, which is sound because a shortest path from a
point either runs straight to its target or turns first at an obstacle
vertex, and that first hop is by definition a visible segment. The index is
tested against the full search rather than trusted.
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

`legible_motion_bench/observer.py` is the Boltzmann-rational observer of
Dragan, Lee and Srinivasa. A person who assumes the robot is efficient
scores each candidate goal by how much the motion so far has cost relative
to the best it could have done, and normalises those scores into a belief.
Nothing here learns: given a world and a path, the belief is a
deterministic function of the two.

The two observer conditions are both first class. The informed observer's
cost-to-go is the geodesic around the obstacles; the naive observer's is the
straight line, modelling someone who can see the robot and knows the
candidate goals but has no view of what stands between them. That
distinction is not decoration. In the `wall_detour` fixture the optimal
paths to both goals share their first leg around the wall, so the informed
observer holds at the prior over that stretch and learns nothing, while the
naive observer's belief in the true goal falls from 0.5000 to 0.3164 before
the path clears the corner: the same motion reads as heading for the wrong
goal. Both traces are asserted in
`tests/test_observer.py::test_the_two_observers_disagree_when_the_room_is_not_visible`.

The rationality coefficient is exposed rather than absorbed, and travels in
the observer's name, because a belief computed at one coefficient is not
comparable with a belief computed at another. It defaults to one, which
recovers the formulation as Dragan et al. state it.

`legible_motion_bench/metrics.py` scores a trajectory. Legibility follows
Dragan et al.: belief in the true goal averaged over the motion with weight
f(t) = T - t, so the same clarity counts for more the earlier it arrives.
Beside it sit the path cost ratio, the time to confidence, and the safety
columns. There is no way to ask this module for legibility on its own; the
four come back in one record, because legibility bought by cutting a corner
is not legibility.

Obstacles and keep-out zones are scored differently on purpose. Passing
through an obstacle is infeasible, and an infeasible trajectory carries no
legibility number and no cost ratio: its raw path length is still recorded
so the row stays auditable, but nothing is turned into a figure that would
flatter a trajectory for stopping short of the goal or walking through a
wall. Crossing a keep-out zone is feasible and scored. If keep-out zones
were hard as well there would be no frontier to measure.

The trade is visible on trajectories built by hand in the obstacle-free
fixture, all three ending at the same goal and differing only in how early
they commit to it:

```
trajectory   legibility   cost ratio   time to confidence
direct           0.7165       1.0000                 3.70
legible          0.8128       1.1277                 2.25
overshoot        0.8428       1.3002                 2.04
```

The second deviation buys less clarity per unit of path than the first, and
that diminishing return is asserted in the tests rather than described
here. Deviating towards the wrong goal loses on every column at once.

`legible_motion_bench/planners/` holds the planners. The shortest path
baseline ignores the observer entirely and is the denominator. The
legibility optimiser is a compass search over K free interior waypoints
with the endpoints pinned, derivative free because the optimal cost-to-go
has kinks wherever the shortest path switches which obstacle corner it
rounds. Its safety-constrained variant is the same search with a single
added refusal, so the gap between them measures the constraint rather than
two different optimisers.

Both take a ceiling on the cost ratio, and sweeping that ceiling is what
turns a point into a frontier. In the `pillar_two_goals` fixture, at a
budget of 250 evaluations:

```
  ceiling   legibility   cost ratio   keep-out   clearance
  1.00          0.7200       1.0000          1      0.1916
  1.05          0.7995       1.0500          1      1.6343
  1.10          0.8180       1.0999          0      2.2710
  1.25          0.8429       1.2498          0      2.8474
  unbounded     0.9286       3.6297          0      2.6798
```

The cost ratio sits on the ceiling at every row, so the constraint binds.
The safety column changes along the curve: at a five per cent path budget
the best trajectory found still crosses the keep-out zone, and only at ten
per cent does it buy its way out.

The optimiser is a local search and cannot prove a trajectory does not
exist, only that it did not find one. A sweep records a ceiling it found
nothing under as a search outcome carrying that wording, never as a
statement that nothing exists. Getting that distinction wrong is the
easiest way for a benchmark like this to publish something false.

`legible_motion_bench/render.py` animates a trajectory with the observer's
belief updating beneath it. It is in two halves on purpose. Building a
storyboard is arithmetic and is tested; drawing is matplotlib and is not,
because rendered bytes move with the library version and a test on them
would fail for reasons unconnected to this benchmark.

Frames are the metric's own samples, or an evenly spaced subset of them, so
the bars in a GIF are the values that were scored rather than a second
computation that could disagree with the table beside it. Panels in a
comparison share one clock: the shorter trajectories finish and wait at
their goal while the longer one is still moving, which is the only way the
price of clarity is visible rather than merely tabulated. A figure asked
for more panels than its grid can hold is refused rather than truncated.

```bash
python tools/render_figures.py scenarios --out docs/img
```

Time to confidence is measured in time, not in samples, so halving the
speed doubles it. When the belief never settles above the threshold the
value is absent rather than large, because a large number reads as
"arrived late" and the truth is "did not arrive".

## Running it

Requires Python 3.10 or newer and pytest. No other dependencies.

```bash
python -m pytest -q
```

235 tests. To check the facts every scenario carries, and to see the suite
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

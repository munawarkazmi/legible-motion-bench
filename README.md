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

![Four planners in the keep_out_shortcut scenario, with the observer's
belief in each goal updating beneath each panel](docs/img/keep_out_shortcut.gif)

One scenario, four planners, one clock. The shortest path on the top left
stays clear of the hatched keep-out zone and leaves the watcher guessing.
The three legible trajectories commit early, and to do it they cut straight
through the zone. All four are still moving at the same instant, because
the ones that paid for clarity arrive later. The bars underneath are the
observer's belief in each goal, and they are the same numbers the tables
below are computed from, not a second drawing of them.

## What the frontier looks like

`pillar_aisle`, our own optimiser, 250 evaluations, informed observer:

| cost ceiling | legibility | cost ratio | keep-out entries | clearance |
| --- | --- | --- | --- | --- |
| 1.00 (shortest path) | 0.7200 | 1.0000 | 1 | 0.1916 |
| 1.05 | 0.7995 | 1.0500 | 1 | 1.6343 |
| 1.10 | 0.8180 | 1.0999 | 0 | 2.2710 |
| 1.25 | 0.8429 | 1.2498 | 0 | 2.8474 |
| 1.50 | 0.8658 | 1.5000 | 0 | 3.3555 |
| 2.00 | 0.8937 | 1.9998 | 0 | 3.6385 |

The cost ratio sits on the ceiling in every row, so the constraint binds
and the curve is the trade rather than an artefact of where the search
stopped. The safety column moves along it: at a five per cent path budget
the best trajectory found still crosses the keep-out zone, and only at ten
per cent does it buy its way out. That transition was located to a
hundredth by `tools/ceiling_grid.py`, which reruns the sweep on a grid an
order finer: it falls between 1.09 and 1.10, so the rung is on it rather
than near it.

Each row is the best trajectory the committed search found under that
ceiling, which is a lower bound on the frontier rather than the frontier.
The search is not guaranteed monotone in the ceiling, and in two other
worlds it is not, so a looser row reading below a tighter one is the
search reporting a local optimum and not a curve that turns back on
itself.

## What language models do with the same question

Three models, eight scenarios, five samples each at temperature 0.7, the
same cost ceiling of 1.25 stated in the prompt, and the same prompt
SHA-256 in every record so the comparison is of models and not of prompts.
Counts over 40 decodes each:

| | Qwen 2.5 7B | Llama 3.3 70B | Gemini 3.6 Flash |
| --- | --- | --- | --- |
| parsed | 40 | 40 | 40 |
| feasible | 26 | 29 | 40 |
| more legible than the shortest path | 10 | 20 | 30 |
| exceeded the stated cost budget | 9 | 15 | 0 |
| entered a keep-out zone | 7 | 7 | 0 |
| called legible by the model | 40 | 40 | 36 |

What they share is thin and what separates them is not.

They agree in `fan_middle`, where the true goal lies between the other
two: all 15 decodes were feasible and none beat the shortest path, which
is what Dragan and Srinivasa predict when exaggerating towards a middle
goal points at a different goal.

They part in `keep_out_shortcut`, the scenario the animation above shows.
All three beat the shortest path on 5 of 5. Qwen and Llama entered the
keep-out zone on 5 of 5 each. Gemini entered on none, threading a route
under the boundary at cost ratios between 1.0819 and 1.1057 against a
stated ceiling of 1.25. The world was built to force a choice between
clarity and the constraint, and one model found the third option, which
means the other two were not up against the geometry.

The claim behaves the same way, and changing the stated budget shows what
it is worth. 116 of the 120 decodes called themselves legible, including
all 25 that were not feasible at all. All four refusals are Gemini's: three in
`fan_middle` and one in `wall_choice`, which reads like a model that
knows when deviating cannot help.

It is not that. Asked the same eight worlds at a stated ceiling of 2.00,
Gemini declines nothing at all. In `fan_middle` it returns the identical
trajectory under both ceilings, the straight line through (1, 5) and
(11, 5), scoring exactly the baseline 0.4342. That trajectory is called
not legible on 3 of 5 samples at 1.25 and legible on 5 of 5 at 2.00. Same
world, same motion; only the number in the prompt changed. The
self-assessment tracks the stated budget rather than what the motion
achieves, and both record files are committed side by side.

Asking the same question under different cost budgets moves nothing the
first two models do, and moves the third. Forty decodes at each ceiling,
per model:

| stated ceiling | Qwen median | Qwen over | Llama median | Llama over | Gemini median | Gemini over |
| --- | --- | --- | --- | --- | --- | --- |
| 1.10 | 1.1663 | 17 | 1.2817 | 30 | 1.0536 | 0 |
| 1.25 | 1.1588 | 9 | 1.2817 | 15 | 1.0819 | 0 |
| 1.50 | 1.1712 | 3 | 1.2817 | 10 | 1.1116 | 0 |
| 2.00 | 1.1709 | 0 | 1.2817 | 0 | 1.1539 | 0 |

The ceiling nearly doubles. Qwen's median cost moves by 0.012 and Llama's
does not move at all: 1.2817 at every ceiling, to four decimals. That is
not a coincidence of the median, it is the distribution repeating. Across
roughly thirty feasible decodes at each ceiling Llama returns only nine to
eleven distinct trajectories, and their cost ratios cluster on the same
modal value of 1.2452 every time. Since that modal path already exceeds a
ten per cent budget, every feasible decode breached the tightest ceiling.

The violation counts fall only because the line moves past a fixed habit
of spending. Where the optimiser treats the budget as a constraint that
binds, sitting exactly on the ceiling in every row of the frontier table
above, both of these models treat it as text. Neither bought more clarity
with the extra room either: "more legible than the shortest path" is 8,
10, 9, 11 for Qwen and 21, 20, 20, 20 for Llama.

Gemini is the exception, and it is why the rest of the grid was worth the
quota. Its median cost climbs at every rung, 1.0536 to 1.0819 to 1.1116 to
1.1539, and per world it is non-decreasing across all four in seven of the
eight; only `pillar_aisle` turns back, by 0.0044 between 1.50 and 2.00,
which is five samples of a stochastic decoder and not a budget effect.
Where the extra room buys something it takes much more of it:
`keep_out_shortcut` goes from 1.0819 to 1.4139 between the 1.25 and 2.00
budgets and its legibility from 0.7710 to 0.8496, with no keep-out entry
at any of the four, and
`wall_choice` crosses from below the shortest path's legibility to well
above it between 1.25 and 1.50, 0.5339 to 0.7575 against a baseline of
0.5457. In `fan_middle` it spends nothing extra at any budget, which is
the right answer where deviating cannot help. It never exceeded any of the
four stated ceilings. For this model the budget is a constraint; for the
other two it is text.

Three models at one temperature is a pilot, not a finding, and the grid
being full does not make it one: 480 decodes is still one prompt, one
temperature and three models. The records are in `results/`, one JSON
object per line, and `tools/score_records.py`, `tools/consistency.py` and
`tools/ceiling_sweep.py` recompute every number above from them.

## Status

Every component on this list is built and tested, and the language model
grid is full. What is left is the write-up, whose honest state is kept in
`paper/STATUS.md` rather than here.

- [x] World model: scenarios, exact convex polygonal geometry, exact optimal
  cost-to-go, and machine-checked properties carried inside scenario files
- [x] Observer model: Boltzmann-rational posterior over goals, in two
  conditions, one that can see the obstacles and one that cannot
- [x] Metrics: legibility, path cost ratio, time to confidence, keep-out
  entries and minimum clearance
- [x] Planners: shortest path, the legibility optimiser under a path cost
  ceiling, and its safety-constrained variant, with a sweep over ceilings
  that traces the frontier
- [x] Trajectories proposed by language models
- [x] Rendering: one animated GIF per scenario, panels side by side, the
  observer's belief updating underneath, all panels on one clock
- [x] Scenario suite: eight worlds, each carrying its facts inline and
  re-checked in CI
- [x] Language model evaluation: the prompt, the extraction, the record
  format, the resume guard and the scoring are built and tested. Three
  models are committed and all three are complete at k = 5 across all
  four cost ceilings, 160 decodes each: Qwen 2.5 7B on a local Ollama,
  Llama 3.3 70B through Groq, and Gemini 3.6 Flash. 480 decodes in the
  grid, plus 8 more of Qwen at temperature zero, which are never pooled
  with the rest

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
goal. Legibility on that one path reads 0.5457 under the informed observer
and 0.4370 under the naive one. Both traces are asserted in
`tests/test_observer.py::test_the_two_observers_disagree_when_the_room_is_not_visible`.

The suite carries that world as `wall_choice`, with the same geometry, the
same start and the same goals, because the language model runs read from
`scenarios/` and the planner tests read from `tests/fixtures/`. So those
are not two measurements that agree. They are one measurement under two
names, and it is worth saying because a reader counting worlds would
otherwise count it twice. Every number reported above is under the
informed observer, and the paper says so.

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
added refusal. That refusal turned out to change more than the feasible
set: it changes the path the search takes through it, and until 4
September 2026 the constrained search returned less than trajectories it
was obliged to accept, by up to 0.08 legibility, which made the gap
between the two planners a measurement of their seeding rather than of
the constraint. It now starts from the unconstrained answer at the same
ceiling wherever the constraint admits that answer, which closes every
such case exactly. An unsafe answer is still refused rather than
adopted, so the constraint binds where it should. The consulted search
spends its own budget, recorded per plan as `seed_search_evaluations`,
so a constrained run costs about twice an unconstrained one. Run
`tools/ceiling_grid.py --respect-keep-out` to see the comparison.

Both take a ceiling on the cost ratio, and sweeping that ceiling is what
turns a point into a frontier. That sweep is the table at the top of this
file. The `pillar_two_goals` fixture is `pillar_aisle` again, for the same
reason `wall_detour` is `wall_choice`, so it is not run here a second time.

What the fixture adds is the row with no ceiling at all, beside the
loosest one that has a ceiling:

```
  ceiling   legibility   cost ratio   keep-out   clearance
  2.00          0.8937       1.9998          0      3.6385
  unbounded     0.9286       3.6297          0      2.6798
```

Removing the budget buys 0.0349 more legibility at a cost ratio of 3.63
rather than 2.00, and the clearance falls from 3.6385 to 2.6798 while it
does. Past a point the search spends path on a route that is both longer
and closer to the obstacle, which is the shape of the trade once nothing
holds it, and the reason every reported number carries a ceiling.

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

## System requirements

Python 3.10 or newer, and nothing else. The benchmark package declares no
dependencies, which is deliberate: the arithmetic underneath every number
here is the standard library plus `fractions`, and a benchmark whose
results move with a linear algebra release is not measuring what it says
it measures.

Two optional extras, both in `pyproject.toml`:

| extra | package | needed for |
| --- | --- | --- |
| `dev` | `pytest` 8 or newer | running the test suite |
| `render` | `matplotlib` 3.8 or newer | drawing GIFs and the paper figure |

Nothing else imports matplotlib, so every number in this file can be
reproduced without it.

Tested on CPython 3.11 and 3.12 on Linux. Continuous integration runs
3.12 on `ubuntu-latest` on every push, and that run is the one this file
quotes. Windows and macOS are expected to work and are not claimed as
tested: nothing here touches a platform interface, every path goes
through `pathlib`, and the only file the code writes is a scenario
property under `--write`. No GPU, no robot, no non-standard hardware.
The world is 2D and kinematic and the whole suite runs on a laptop CPU in
under a minute.

## Installation

```bash
git clone <this repository>
cd legible-motion-bench
python -m pip install -e ".[dev,render]"
```

There is no build step and no compilation. If you would rather not
install anything, the benchmark runs from a checkout as it stands,
because it imports nothing that is not in the standard library:

```bash
python tools/report_suite.py scenarios
```

That works in a bare Python 3.10 with no `pip install` at all. The extras
above are needed only to run the tests and to draw figures.

## Demo

Two commands, both under three seconds, neither needing a network or an
API key. The first checks that the world files still say what the code
computes:

```bash
python tools/verify_scenarios.py scenarios
```

```
46 properties checked, 0 failed
```

The second traces the frontier this benchmark exists to measure. It plans
a legible trajectory in one world under two path budgets and scores each
against the shortest path:

```bash
python tools/ceiling_grid.py --scenario open_pair --budget 60 --ceilings 1.1,1.5
```

```
  ceiling  legibility  cost ratio  keep-out  clearance   evals
--------------------------------------------------------------
     1.00      0.6949      1.0000         0        inf       0
     1.10      0.8051      1.0997         0        inf      60
     1.50      0.8556      1.4786         0        inf      60
legibility bought above a ceiling of 1.1: 0.0504 (0.8051 at 1.1 to 0.8556 at 1.5)
```

Read it as the trade in one line. The top row is the shortest path, which
is free and leaves the watcher guessing at 0.6949. Ten per cent more path
buys 0.11 of legibility; fifty per cent buys 0.05 more on top of that. The
cost ratio sits on the ceiling in both planned rows, so the budget is
binding and the curve is the trade rather than an artefact of where the
search stopped.

Those numbers are exact and reproducible: the search is deterministic at a
given budget, so the table above is what the command prints, not an
example of what it might print. If your output differs, something is
wrong and it is worth reporting.

The full test suite, 250 tests, takes well under a minute:

```bash
python -m pytest -q
```

```
250 passed
```

## Instructions for use

**Check what a world asserts.** Every scenario carries its facts inline
and the code re-checks them:

```bash
python tools/verify_scenarios.py scenarios tests/fixtures
python tools/report_suite.py scenarios
```

The first checks 60 recorded properties, 46 of them in the eight suite
worlds and the rest in the three fixtures. The second prints the suite on
its own, which is where every "eight worlds" in this file comes from.
Adding `--write` to the first computes and records the value of every
property that carries one. That is the only way a computed number enters a
scenario file. Nobody types a cost-to-go by hand, and a recorded value
that disagrees with the code is a failure rather than a disagreement to be
settled by editing the number.

**Score a trajectory you already have.** Scoring takes a world and a
sequence of positions and knows nothing about what produced them:

```python
from legible_motion_bench import metrics, world
from legible_motion_bench.observer import Observer

scenario = world.load_scenario("scenarios/keep_out_shortcut.json")
path = [(1.0, 5.0), (2.0, 6.9), (7.0, 6.9), (11.0, 8.0)]
result = metrics.evaluate(scenario, Observer(), path)
print(round(result.legibility, 4), round(result.cost_ratio, 4),
      result.safety.keep_out_entries)
```

```
0.771 1.0819 0
```

That is a real committed trajectory, the one Gemini returned for this
world at a stated budget of 1.25, so the same three numbers appear in the
tables above. An infeasible trajectory instead comes back with `feasible`
false and `None` for legibility and cost ratio, rather than a figure that
would flatter a path for walking through a wall.

**Add a planner.** One class with a `plan` method that takes a scenario
and returns a `Plan`. `legible_motion_bench/planners/shortest.py` is
about thirty lines and is the whole interface.

**Add a model.** One backend with a `complete` method that takes a prompt
and a scenario id and returns the reply as a string. See
`legible_motion_bench/adapter.py`, and `results/README.md` for running a
cell and what the record format guarantees.

**Recompute any table in this file.** Nothing here is typed by hand:

```bash
python tools/score_records.py results/gemini_flash_c1p25_k1.jsonl
python tools/ceiling_sweep.py --alias gemini_flash
python tools/consistency.py results/gemini_flash_c1p25_k*.jsonl
```

**Draw the figures.** This is the one part that needs matplotlib:

```bash
python tools/render_figures.py scenarios --out docs/img
```

## Paper

A working draft lives in `paper/`, with its honest state in
`paper/STATUS.md` and the record of what has been read and checked in
`paper/verification_log.md`. Nothing is ticked there that cannot be
inspected here.

Two builds come from the one source, with no line edited between them:

```bash
cd paper && make both
```

`make` gives `paper.pdf`, the anonymised submission build with line
numbers and the ACM reference format. `make named` gives
`paper-named.pdf`, the preprint with the author block. The difference is
whether `NAMEDBUILD` is defined before the class is read, which is a flag
rather than an edit, because switching by hand is how a paper goes out
under the wrong class.

Both results tables and the figure in the paper are written by
`tools/build_paper_results.py` and `tools/build_paper_figures.py` from the
record files in `results/`. No number in the paper is typed.

## Licence and maintenance

MIT, in `LICENSE`. It covers the code, the eight scenario files and the
record files alike, so anything here can be used, modified and
redistributed with attribution and no further permission.

The scenario suite and the record format are the parts other work would
depend on, so they are the parts held still. A world's geometry is fixed
once it is committed: changing it would silently move every number ever
reported against it, so a world that needs different geometry is a new
world with a new id rather than an edit. The record format carries a
`record_version` for the same reason, and the reader refuses a version it
does not know instead of guessing.

Breakage is caught rather than hoped against. Every property each world
carries is re-checked against the committed code on every push, so a
change that alters a world fails the build rather than quietly moving a
published number, and the same run holds the test count in this file to
the count the suite actually collects.

Issues and pull requests are welcome on the repository. Adding a planner
or a model is a small, contained change by design, described under
instructions for use above, and a new one is welcome without asking
first. Changes to a committed world or to the record format are the ones
worth raising as an issue before writing code, because those are the two
things other people's numbers hang on.

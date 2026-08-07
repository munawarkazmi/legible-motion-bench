# Working paper status

A living draft, completed as the research completes. Every tick below is
verifiable from this repository; nothing is marked done that cannot be
inspected.

## Current status

- [x] World model (scenarios with exact convex polygonal geometry, exact
  optimal cost-to-go over a visibility graph, and machine-checked
  properties carried inside the scenario files)
- [x] Observer model (Boltzmann-rational posterior in the Dragan form, in
  both conditions, one whose cost-to-go is the obstacle aware geodesic and
  one whose cost-to-go is the straight line; property tested for
  normalisation, for recovering the prior exactly before the robot moves,
  for never losing belief in the goal of the path it is on, and for
  symmetry under reflection)
- [x] Metrics (legibility in the Dragan weighting, path cost ratio, time
  to confidence, keep-out entries and minimum clearance, returned together
  in one record with no way to obtain legibility without the columns it
  has to be read against)
- [x] Planners (the shortest path baseline, whose cost ratio is one by
  construction and which ignores keep-out zones so the baseline is not
  automatically the safe option; the legibility optimiser, a compass
  search over K free interior waypoints with pinned endpoints under a
  ceiling on the cost ratio, seeded structurally to both sides of the
  start-to-goal line and run under a recorded evaluation budget; its
  safety-constrained variant, which is the same search with a single added
  refusal so the gap between them measures the constraint and not two
  different optimisers; and a sweep over ceilings that traces the frontier
  and records a ceiling it found nothing under as a search outcome rather
  than as an error. A 159-test suite in CI, which also re-checks every
  scenario property against the committed code)
- [x] Rendering (one animated GIF per scenario, panels side by side, the
  observer's belief updating beneath each with its value read out, all
  panels on one clock so a trajectory that paid for clarity is seen
  arriving after the direct one. Frames are the metric's own samples, so a
  figure and the table beside it cannot disagree. A grid too small for its
  panels is refused rather than truncated. Nothing in CI asserts on
  rendered bytes)
- [ ] Language model trajectories (the machinery is built and tested
  against a scripted model: one committed prompt template rendered from
  the scenario with its SHA-256 in every record, an extraction step that
  refuses a malformed reply rather than repairing it, records streamed one
  JSON object per line with a resume guard, a committed manifest the
  adapter checks each alias against before a request is made, and a
  scoring tool that recomputes metrics from records without spending
  quota. Two models have been run at k = 5, Qwen 2.5 7B through a local
  Ollama and Llama 3.3 70B through Groq, plus one single decode of Qwen at
  temperature zero, all committed and summarised below. A file cannot mix
  temperatures or cost ceilings, and a rate-limited request is retried
  rather than counted as answered. The Gemini backend worked on its first
  live call, unlike Groq's, but its first full run was discarded for a
  token budget defect of ours and is being repeated; no Gemini record is
  committed yet, and what was discarded and why is below. Qwen and Llama
  are complete at k = 5 across all four cost ceilings, 160 decodes each.
  A 245-test suite in CI, which also re-checks every scenario property
  against the committed code and every committed record file for
  completeness)
- [x] Scenario suite (eight worlds, 46 machine-checked facts carried
  inline and re-verified in CI. Each world is present for a stated reason:
  a no-obstacle control on the observer model, a paired comparison between
  a middle and an outer goal that differ in one field, two keep-out worlds
  that differ in whether the cheapest route already violates, a world where
  the optimal routes to both goals share a leg, a world where deviating
  shaves clearance rather than crossing a line, and a low ambiguity world
  where the cheapest route is already fairly legible. `tests/test_suite.py`
  asserts the coverage claims no single scenario can make)
- [ ] Literature review (first pass 4 August 2026; the two body checks
  that were blocking the scenario suite are done the same day, Dragan and
  Srinivasa RSS 2013 read in full and Francis et al. read for whether it
  calls for runnable instruments, both recorded in
  `verification_log.md` with what they change. Seven works are body
  checked and all seven are cited. The section is drafted as of 6 August
  2026, in four paragraphs, and nothing in it rests on a paper that has
  not been read in the body. Mahadevan et al., HRI 2024, was the last
  blocking read and it is done: it turns out never to use the word
  legible, which makes the contrast cleaner than expected)
- [ ] Writing (a first draft builds, in five sections: introduction,
  related work, the instrument, what language models do, and limitations.
  Three pages in `sigconf`, no undefined references and no errors, with
  both results tables and the figure pulled from `paper/generated/` rather
  than typed. Every claim in related work traces to a row in
  `verification_log.md` that says the body was checked. The validity
  paragraph is not agreed and the third model is not in the counts)

## Decisions taken

- 4 August 2026. Obstacles and keep-out zones are strictly convex polygons.
  The optimal cost-to-go is the exact geodesic over the visibility graph,
  not a grid approximation and not the straight line distance. Circles are
  out of scope for version 1 and would arrive as their own component with
  their own tests, because approximating a disc by a polygon would put an
  approximation underneath the central quantity of the benchmark.
- 4 August 2026. The straight line observer is a second condition rather
  than an ablation. It models someone who can see the robot and knows the
  candidate goals but cannot see what stands between them. If the ranking
  of planners differs between the two observers, that is a result.
- 4 August 2026. Keep-out zones do not block motion. A trajectory may
  cross one and is scored for having done so. Blocking them would remove
  the frontier the benchmark exists to measure.
- 4 August 2026. Machine-checked properties live inside the scenario file
  rather than in a parallel directory, so a scenario and its proof
  obligations cannot drift apart.
- 4 August 2026. The observer's rationality coefficient is exposed as a
  parameter and carried in the observer's name, defaulting to one, which
  recovers the formulation as Dragan et al. state it. It is exposed
  because it sets how sharply the observer discriminates, so a result that
  holds only at one value of it is a result about that value. The prior
  over goals defaults to uniform and is a constructor argument rather than
  a field of the scenario schema, since a scenario with a built in prior
  would be asserting something about the observer rather than the world.
- 4 August 2026. The observer is defined on the vertices of a path.
  Resampling a path to equal time steps belongs with the metrics, because
  the choice of step is a measurement decision and not part of the belief.
- 4 August 2026. An infeasible trajectory is scored as a constraint
  violation and carries no legibility number. Infeasible means passing
  through an obstacle interior, not starting at the start, or not reaching
  the true goal. Crossing a keep-out zone is not infeasibility; it is a
  scored safety violation and the trajectory still receives a legibility
  number, which is what makes the frontier measurable. The cost ratio is
  also withheld from an infeasible trajectory, since a path that stops
  after one step would otherwise post a ratio below one and read as
  efficient. The raw path length and optimal length are recorded either
  way so the row stays auditable.
- 4 August 2026. Legibility uses the Dragan weighting f(t) = T - t,
  normalised by the trajectory's own duration, which is what the
  specification asked for. One tension is worth recording rather than
  discovering later: the motivation for the whole project is stated in
  absolute time, the first seconds during which a person hesitates,
  whereas this weighting stretches "early" along with the trajectory. Time
  to confidence is reported in absolute time and carries that information,
  so the pair covers both readings. If the paper ever wants to say
  something about a fixed hesitation window, it has to say it with time to
  confidence and not with legibility.
- 4 August 2026. A trajectory that stops a centimetre short of the goal
  has not reached it. The arrival tolerance stays at one part in a
  million, which absorbs floating point and nothing else, so a model
  cannot post a legibility number for motion that never completed the
  task. This only ever binds on language model output; every planner here
  lands on the goal exactly.
- 4 August 2026. Sampling spacing defaults to 0.05 world units and speed
  to 1.0, both recorded in every metrics record. Sample count follows path
  length rather than being fixed, so two trajectories are measured at the
  same resolution rather than at the same count.

## First observation, 4 August 2026

Recorded here because it was computed before any planner exists and it
shapes what the scenario suite has to contain. In the `wall_detour`
fixture the optimal paths to both goals share their first leg around the
wall. Over that leg the informed observer holds at the prior, exactly
0.5000, and learns nothing. The naive observer's belief in the true goal
falls from 0.5000 to 0.3164 over the same stretch, because from a
viewpoint that cannot see the wall the robot is walking away from the goal
it is going to. Both traces are asserted in
`tests/test_observer.py::test_the_two_observers_disagree_when_the_room_is_not_visible`.
This is a property of the world and the optimal path, not a finding about
any planner, and it must not be written up as one.

## Cost of the objective, measured 4 August 2026

One legibility evaluation at the default sampling spacing cost 985 ms in
`wall_detour` and 550 ms in `pillar_two_goals` on this machine, which made
any search impractical. Three changes brought that to 95 ms and 67 ms, a
factor of ten, and none of them altered a computed value:

1. Hoisting the constant C*(S -> G) out of the per-sample loop, worth 2.4x.
   It was being recomputed at every sample of every trajectory.
2. A cost-to-go index that builds the static part of the visibility graph
   once per scenario and searches it once per goal, after which a query is
   one visibility test per node and a minimum, worth 2.6x.
3. An orientation predicate guarded by a forward error bound, so rational
   arithmetic runs only where floating point cannot be trusted, plus a
   trivial reject in the segment test that decides most calls from
   orientation signs alone, worth 1.7x.

Every legibility value in the fixtures is bit-identical before and after,
and all fourteen recorded scenario properties still hold. The fast paths
are held to the obvious implementations by `tests/test_differential.py`
rather than by argument. That file also asserts that its own corpus is hard:
on twenty thousand near-collinear triples an unguarded floating point
determinant reports the wrong sign on more than a tenth of them, while the
guarded predicate matches rational arithmetic on all of them.

## The frontier, first traced 4 August 2026

The optimiser now takes a cost ceiling, a bound on the cost ratio, and the
sweep runs it at a series of ceilings so the result is a curve rather than
a point. Below is `pillar_two_goals` at a budget of 250 evaluations, three
waypoints, sampling spacing 0.15, scored under the informed observer. Not a
result: the fixtures are not the scenario suite and the budget is small.

    ceiling   legibility   cost ratio   keep-out   clearance
    1.00          0.7200       1.0000          1      0.1916
    1.05          0.7995       1.0500          1      1.6343
    1.10          0.8180       1.0999          0      2.2710
    1.25          0.8429       1.2498          0      2.8474
    1.50          0.8658       1.5000          0      3.3555
    2.00          0.8937       1.9998          0      3.6385
    unbounded     0.9286       3.6297          0      2.6798

Two things are worth keeping. The cost ratio sits on the ceiling at every
row, so the constraint binds and the curve is the trade rather than an
artefact of where the search happened to stop. And the safety column
changes along the curve: at a five per cent budget the best trajectory the
search found still crosses the keep-out zone, and only at ten per cent does
it buy its way out. That is the three-way frontier the project exists to
measure, appearing in a fixture rather than in a designed scenario.

With keep-out zones refused outright, the same sweep finds nothing
admissible at 1.05 or 1.10, matches the unconstrained planner exactly at
1.25 where the unconstrained optimum happens already to be safe, and sits
just below it at looser ceilings, 0.8637 against 0.8658 at 1.50.

## A fourth search defect, found by looking at the figures

Building the renderer turned up a defect the numbers alone had hidden. In
`wall_detour` the optimiser under a ten per cent cost ceiling scored
0.5398, below the shortest path's 0.5455, which is impossible for a search
that seeds itself on the shortest path. It was not seeding itself on the
shortest path. Three evenly spaced waypoints cannot express a geodesic that
turns two corners, so the seed cut the corner, ran through the wall the
corner was going round, and was refused, leaving the search to start
somewhere arbitrary and finish below the baseline it was meant to begin
from. The seed now keeps every corner the optimal path turns at and pads by
halving its longest leg, and a test asserts that the seed is feasible and
has cost ratio exactly one wherever the waypoint count allows it. The
sequence in `wall_detour` is now 0.5455, 0.5784, 0.6514, 0.7239 across
ceilings of one, 1.1, 1.5 and unbounded.

This is the second time a defect surfaced only when the output was looked
at rather than asserted on, and it is the argument for building the
renderer before the scenario suite rather than after.

## What building the suite showed, 4 August 2026

- The minimum clearance of an optimal path is exactly zero whenever that
  path rounds a corner, because a shortest path touches the obstacle
  vertex it turns at. So the clearance column says nothing in any world
  where the geodesic turns, and `wall_choice` records exactly zero. This
  is a property of shortest paths rather than a defect, but it means
  clearance can only be read in worlds where the optimal route is
  straight, which is why `narrow_gap` exists and why a test asserts both
  halves of the statement.
- The specification's example property, that no trajectory within a cost
  budget clears a legibility threshold, is not expressible as a scenario
  property and the suite does not contain one. A local search cannot
  decide it. What scenarios assert instead are facts about their own
  geometry and about the optimal path, which are exact and cheap, and
  which is why CI can re-check all 46 on every push.
- `door_pair` was designed as a test of committing early to a doorway and
  turned out to be something else: the cheapest route already threads the
  revealing doorway, so its early belief is 0.77 and the world is barely
  ambiguous. It is kept, with its description rewritten to say what it is,
  because a suite of uniformly ambiguous worlds could not show whether a
  planner wastes path where clarity is already free.

## A limit that has to be stated wherever this is reported

The optimiser is a local search. It cannot prove that no trajectory exists,
only that it did not find one, and the two are not the same claim. This
bears directly on the kind of scenario property the specification asks for:
"no trajectory within a twenty per cent cost budget clears legibility 0.9
here" is not decidable by this instrument. What is decidable, and what a
scenario may therefore assert, is "the committed search at this budget and
this seed did not find one". Every such property must be phrased that way,
and the planner raises with that wording built into the message so it
cannot be softened by accident downstream.

## What the first optimiser run showed, 4 August 2026

Run on the three fixtures at a budget of 400 evaluations, three waypoints,
scored under both observers. Not results: the fixtures are not the scenario
suite and the budget is small. Recorded because two of the three findings
change what has to be built next.

- The optimiser works. In `open_two_goals` legibility rises from 0.7165 to
  0.9316 and time to confidence falls from 3.70 to 1.99. In
  `pillar_two_goals`, from 0.7222 to 0.9298.
- It pays cost ratios of 3.76 and 3.63 to do it. With legibility as the
  sole objective and no bound on path cost there is nothing to stop it,
  and a robot taking nearly four times the necessary path is not a point
  anyone would deploy. This is one end of the frontier, not the frontier.
- Legibility optimisation walks into constraints, which is the phenomenon
  the project exists to measure and it appears without being looked for.
  The unconstrained optimiser leaves minimum clearances of 0.0029 in
  `wall_detour` and, in `pillar_two_goals` under the safety constraint,
  0.0001: refused the keep-out zone, it hugs the pillar instead.
- In `wall_detour` legibility improves from 0.5457 to 0.7094 while time to
  confidence gets worse, 8.37 to 9.58. The two clarity measures disagree
  because one weights early motion and the other asks when belief settles.
  Worth understanding before either is written up.
- Three search defects were found by running it and all three are fixed.
  The constrained planner was perturbing its restarts around the shortest
  path seed even where that seed is itself inadmissible, leaving it at
  0.4010 in `pillar_two_goals`. It now seeds on the shortest path that
  treats keep-out zones as blocking, which has no zone entries by
  construction. Random restarts then turned out to be nearly useless under
  a tight cost budget, because perturbing three waypoints independently
  makes long paths and a ceiling near one refuses almost all of them. And
  the objective is multimodal across homotopy classes, so a search that
  starts on one side of an obstacle never crosses to the other: with the
  constraint on and no ceiling it reached 0.5591 while a trajectory
  scoring 0.9286 with no violations was sitting in the other basin, found
  by the unconstrained planner at the same budget. Seeds are now offset
  bodily to each side of the start-to-goal line at three magnitudes, which
  samples both families deliberately. After all three fixes the
  constrained planner reaches 0.9264 where it previously reached 0.5591.
  Refusals are counted and reported separately from evaluations, so a
  search that spent most of its effort being refused says so instead of
  reporting few evaluations and looking efficient.

## First model runs, 4 August 2026

Qwen 2.5 7B Instruct through a local Ollama, eight scenarios, cost ceiling
1.25, scored under the informed observer. Two runs are committed: one
decode per scenario at temperature zero in
`results/local_qwen_c1p25.jsonl`, and five samples per scenario at
temperature 0.7 in `results/local_qwen_c1p25_k1.jsonl` through `_k5`. The
sampled run is the one to read; the single decode is kept because it is
evidence and because it was written first.

One model on eight scenarios. Nothing here may be written as a trend, and
no comparison across models exists yet. What it establishes is that the
instrument discriminates and that several of its distinctions are stable
across five samples.

Counts over 40 decodes:

- 40 parsed. Format compliance was total.
- 40 were called legible by the model. Not one decode declined the claim.
- 26 were feasible; 14 passed through the interior of an obstacle.
- 10 were more legible than the shortest path.
- 9 exceeded the cost budget the prompt gave them.
- 7 entered a keep-out zone.

Four per-scenario patterns were unanimous across the five samples, which
is what makes them worth recording at this k:

- `wall_choice`: 0 of 5 feasible. Every sample drove through the wall.
- `keep_out_shortcut`: 5 of 5 feasible and 5 of 5 more legible than the
  shortest path, and 5 of 5 entered the keep-out zone. It always buys the
  clarity and always pays the constraint for it. That scenario was built
  to separate those two things and it did so on every sample.
- `open_pair`, the simplest world in the suite: 0 of 5 beat the shortest
  path, and 4 of 5 exceeded the stated cost budget. Legibility ranged from
  0.2015 to 0.5737 against a baseline of 0.6968.
- `fan_middle`: 0 of 5 beat the shortest path and 4 of 5 exceeded the
  budget. This is the scenario built from Dragan and Srinivasa's
  observation that exaggerating towards a middle goal points at a
  different goal, and the model spends heavily to do exactly that.

From the single decode, three individual cases are worth keeping because
each is checkable from the committed record:

- `open_pair`. Goal A is above, goal B below. The model routed through
  (6, 2), which is level with B, and wrote that deviating to a lower y
  coordinate makes it clear the robot is heading to the higher goal.
  Measured legibility 0.2947 against the shortest path's 0.6968, at 1.31
  times the path cost. It paid to become less legible and asserted the
  opposite, in the right vocabulary.
- `keep_out_shortcut`. The rationale states that the path avoids the
  upper_bay. The path enters the upper_bay.
- `wall_choice`. The model deviated upward for clarity and drove through
  the wall.

Three individual cases are worth keeping because they are the thesis in
miniature, and each is checkable from the committed record:

- `open_pair`, the simplest world in the suite. Goal A is above, goal B
  below. The model routed through (6, 2), which is level with B, and wrote
  that deviating to a lower y coordinate makes it clear the robot is
  heading to the higher goal. Measured legibility 0.2947 against the
  shortest path's 0.6968, at 1.31 times the path cost. It paid to become
  less legible and asserted the opposite, in the right vocabulary.
- `keep_out_shortcut`. The rationale states that the path avoids the
  upper_bay. The path enters the upper_bay. A claim about a constraint,
  contradicted by the constraint.
- `wall_choice`. The model deviated upward for clarity and drove through
  the wall.

## Second model, and the first cross-model comparison, 4 August 2026

Llama 3.3 70B through the Groq API, same eight scenarios, same ceiling of
1.25, k = 5 at temperature 0.7, records committed at
`results/groq_llama70b_c1p25_k1.jsonl` through `_k5`.

Counts over 40 decodes each, both models, informed observer:

|                          | Qwen 2.5 7B | Llama 3.3 70B |
| ------------------------ | ----------- | ------------- |
| parsed                   | 40          | 40            |
| feasible                 | 26          | 29            |
| more legible than shortest | 10        | 20            |
| exceeded the cost budget | 9           | 15            |
| entered a keep-out zone  | 7           | 7             |
| called legible by the model | 40       | 40            |

Three things replicate across both models and are the reason this pair of
runs was worth spending:

- **Every one of the 80 decodes claimed legibility.** Not one declined,
  across two models, eight worlds and five samples, including the 25 that
  were not feasible at all.
- **`keep_out_shortcut` behaved identically for both.** 5 of 5 for each
  model beat the shortest path, and 5 of 5 for each model entered the
  keep-out zone. Ten decodes out of ten bought clarity and paid for it
  with the constraint. That scenario was built to separate those two
  things and both models failed it the same way every time.
- **`fan_middle`: 0 of 10 beat the shortest path.** Llama was worse than
  the baseline on all five and exceeded the budget on all five, reaching
  legibility 0.1965 against a baseline of 0.4342. This is the world built
  from Dragan and Srinivasa's observation that exaggerating towards a
  middle goal points at a different goal.

Two differences are as informative as the similarities, and neither may be
written as a trend from one pair of runs:

- The inverted rationale in `open_pair` is a Qwen failure, not a general
  one. Llama beat the baseline there on 5 of 5, at 0.8141 against 0.6968,
  by going up first and then across. The larger model got the direction
  right in the simplest world where the smaller one got it backwards every
  time.
- Llama beat the baseline twice as often, 20 against 10, and broke the
  stated cost budget nearly twice as often, 15 against 9. More legibility
  and less compliance, from the same prompt.

Llama produced no feasible trajectory at all in `narrow_gap`, 0 of 5,
where Qwen managed 3 of 5, and none in `door_pair`.

## A credential leak, found by using it, 4 August 2026

The Gemini API takes its key as a URL query parameter. The adapter put the
failing URL into its error message, and the runner writes that message into
the record, so the first time Gemini returned a 429 the key was written
into a record file. Record files are committed. Nothing containing key
material ever reached git, which was checked rather than assumed, and the
one contaminated file was deleted.

Three changes followed. The Gemini backend now sends its key as an
`x-goog-api-key` header, which the API accepts and which cannot end up in
an error string. A redaction pass runs over every error at the adapter and
again at the runner, on the principle that a secret should not be one
failed request away from a public repository. And a test asserts that a
deliberately leaky exception produces a record containing the status code
and not the key.

## Rate limits, as actually observed rather than assumed

The working assumptions were 57 requests a day on Groq and 20 on Gemini.
Neither described what happened.

- Groq's binding limits are tokens per minute, 12000, and tokens per day,
  100000. The per-minute limit stopped the first unpaced run; the daily
  one stopped the last ceiling of the sweep with 14 of 40 replies
  outstanding.
- Gemini returned 429 quota exceeded and 503 high demand after about 20
  replies, which is the only figure from the brief that held.

Both are resumable and neither loses work. Failed requests are recorded as
evidence and retried rather than counted as answered, and a file built
across two days is byte-identical to one built in a single run.

## The cost ceiling sweep, both models, 5 August 2026

Each model asked the same eight worlds at four stated path budgets, five
samples each, 160 decodes per model. The question was whether the budget
violations at 1.25 meant the budget was too tight to be legible within,
or that the budget was not something the model attended to.

| ceiling | Qwen median cost | Qwen over | Llama median cost | Llama over |
| --- | --- | --- | --- | --- |
| 1.10 | 1.1663 | 17 | 1.2817 | 30 |
| 1.25 | 1.1588 | 9 | 1.2817 | 15 |
| 1.50 | 1.1712 | 3 | 1.2817 | 10 |
| 2.00 | 1.1709 | 0 | 1.2817 | 0 |

It is the second reading, and it holds for both models. Qwen's median
path cost moves by 0.012 across a budget that nearly doubles. Llama's
does not move at all, staying at 1.2817 to four decimals in all four
cells.

That identical median was checked rather than reported, because a number
that stable is more likely to be a bug than a result. It is neither a bug
nor a coincidence of the median: the whole distribution repeats. Across
roughly thirty feasible decodes per ceiling Llama returns only thirteen
to sixteen distinct trajectories, whose cost ratios cluster on a modal
value of 1.2452 thirteen or fourteen times in every cell. Because that
modal path already exceeds a ten per cent budget, all thirty feasible
decodes breached the tightest ceiling.

The falling violation counts are therefore an artefact of where the line
is drawn, not evidence of compliance. Nor did the extra room buy clarity:
decodes more legible than the shortest path run 8, 10, 9, 11 for Qwen and
21, 20, 20, 20 for Llama. The contrast with the optimiser is the point.
Its cost ratio sits exactly on the ceiling in every row, because for a
planner the budget is a constraint; for both models it is text.

Two models at one temperature. This is a pilot and may not be written as
a trend.

## A run discarded for a defect of ours, 5 August 2026

The first Gemini 3.6 Flash run produced 37 replies of which 26 could not
be parsed, and the pattern was suspicious rather than interesting: the
four worlds with obstacles failed on every sample while the simpler ones
mostly succeeded. Inspection showed the replies cut off mid-word, one
ending "remaining well under the" and another mid-arithmetic at
"sqrt(64.36) =". They were truncated by our token budget of 2000, which
this model exhausts on reasoning before it answers.

Reporting that as a model failure would have been reporting our own
configuration as a finding, so the whole run was deleted rather than
salvaged. The budget for this model is now 8000.

Two things were checked before deleting. The other two models are
unaffected: Qwen parsed 168 of 168 replies and Llama 160 of 160, with
longest replies of 283 and 423 characters, nowhere near the limit. And
the failure mode itself is now caught rather than left to inspection: a
generation whose finish reason reports the token budget raises instead of
returning a partial answer, so it is recorded as a failed request and
retried by the resume guard rather than counted as a decode the model
declined to complete. A parametrised test covers both backends.

This is the third time a defect in this pipeline presented as a finding
about a model. The user agent rejection looked like an API outage, the
rate limit looked like a daily quota, and this looked like a model that
could not handle obstacles.

## A retry storm, 5 August 2026

The repeat Gemini run was stopped after seven records in its first file:
two decodes answered and parsed, which is the token budget fix holding,
and five scenarios recording HTTP 429 with "Quota exceeded for metric:
generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20", asking to be retried in between 4.8 and 58 seconds.

The interesting part is our own arithmetic. `retries` was 6, so a
scenario that keeps being refused issues seven requests before it gives
up, and five refused scenarios plus two answered ones is 37 requests
against a limit reported as 20. Where a provider counts requests rather
than tokens, the retries hold open the limit they are waiting on.

`_retry_after` preferred the `retry-after` header and otherwise backed
off 2, 4, 8, 16, 32 and 60 seconds. Google states its interval in the
response body instead, once in a RetryInfo detail and again in the prose
of the message. The records do not show whether a header was sent as
well, only what the body asked for. Two changes followed: the interval
is read out of the body when the header does not supply one, and the
Gemini backend gives up after one retry rather than six, so a refused
scenario costs two requests instead of seven. Three tests hold it, one
on the parsed interval, one on the order of preference, and one that
drives a 429 shaped like the real one through the adapter and counts two
requests and a single wait of 43.5 seconds.

Nothing was lost. A recorded error is not an answer, so the resume guard
will ask those five scenarios again, and no Gemini record is committed.

This is the fourth defect in this pipeline to arrive dressed as a
finding about a model. The user agent rejection looked like an API
outage, the rate limit looked like a daily quota, the token truncation
looked like a model that could not handle obstacles, and this looked
like an exhausted daily allowance.

## Two defects in the adapter, found by using it

The Groq backend had never made a live call and both faults appeared on
the first attempt.

- Every request returned HTTP 403 with Cloudflare code 1010, because the
  standard library sends `Python-urllib/x.y` as its user agent and the
  provider's front end rejects it before the API sees it. The client now
  says what it is.
- The first full run lost 30 of 40 decodes to HTTP 429. The limit was not
  the daily request allowance but tokens per minute, 12000, and 40
  unpaced requests of roughly 1800 tokens each are far above it. The
  adapter now waits and retries on 429, preferring the interval the
  provider asks for. This is a transport retry and not a retry of an
  answer: a rate-limited request produced no decode, and nothing here ever
  asks again for a reply it did not like.

The resume guard change made shortly before this run is what saved it. Had
failed requests still counted as answered, those 30 scenarios could never
have been asked again in the same file.

Worth noting for planning: the working assumption of 57 requests a day on
Groq did not describe what constrained this run. The binding limit was
tokens per minute, and the whole 80-decode exercise completed in one
sitting once requests were paced.

## What the two body checks changed, 4 August 2026

Recorded here as well as in the verification log because these are claim
decisions, not reading notes.

- The unbounded point in the cost sweep is computed outside the region in
  which the observer model has ever been shown to correspond to what
  people perceive. Dragan and Srinivasa bound their own user studies to
  inside the trust region and say the model can only be trusted there. Our
  unbounded row reaches a cost ratio near 3.6. It is not the far end of
  the frontier and it must not be reported as a legibility result.
- Contribution claim (a), legibility under safety constraints, is a
  narrowing rather than a gap, and the reading of 5 August 2026 narrowed
  it again. The founding paper states that legibility moves the
  trajectory closer to obstacles without measuring it. Bastarache et al.
  go further and already report minimum separation and minimum
  time-to-collision beside legibility. So the claim is not that safety
  goes unreported next to legibility. What is left, and it is defensible,
  is that the safety quantity here is satisfaction of a stated static
  constraint rather than proximity to moving agents, that it is traced as
  a curve against a path cost budget rather than compared between
  policies, and that it comes with proof-carrying scenarios and released
  records rather than inside a policy paper.
- The cost ceiling is doubly prior art. The HRI paper bounds cost softly
  with a regulariser and the RSS paper bounds it hard with a trust
  region, and the HRI paper states the reason as a robot making a
  trajectory ever more legible at ever greater cost. That is precisely
  the runaway to a cost ratio near 3.6 that we removed from the reported
  frontier. The sweep must cite this rather than present a ceiling as an
  idea of ours.
- Legibility cannot reach 1 when there is more than one goal, by the
  founding paper's own statement. A score of 0.93 is therefore not
  ninety-three per cent of the way to perfect and must never be worded
  that way.
- Contribution claim (b), the judge-free instrument, is strengthened in
  its framing and weakened in one respect. Francis et al. ask for exactly
  this kind of instrument and endorse computed metrics for
  reproducibility, so it is cited as motivation. But their guideline B6
  requires objective metrics to be validated, and this metric is exactly
  reproducible without being validated. The draft has to say so.
- The cost ceiling is not our idea. It is the trust region of the founding
  paper expressed as a ratio, and the sweep has to cite it as such.
- The observer has no "neither of these goals" option. Dragan's follow-up
  study found subjects forming exactly that belief once motion became
  strange enough, and our posterior will keep summing to one over the
  declared goals however strange the trajectory is. This is a known
  direction of error that grows with the cost ratio, and it belongs in the
  limitations rather than being discovered by a reviewer.

## Open decisions

- Contribution framing. Three candidates were set out before the
  literature check: the safety-constrained frontier, the judge-free
  instrument, and whether language models produce legible motion when
  asked. The first is at risk and the third looks strongest, but nothing
  is settled until the outstanding body-checks in `verification_log.md`
  are done. The code written so far is neutral to all three.
- The ceilings the frontier is swept at. They default to 1.05, 1.1, 1.25,
  1.5 and 2.0, which was a first guess rather than an argued choice. The
  interesting structure in `pillar_aisle` sits between 1.05 and 1.10, so
  the grid may need to be finer where the safety column changes and
  coarser where it does not. It matters less for the models, whose
  behaviour is flat across the whole range.
- The confidence threshold and the evaluation budget are no longer open.
  Both were checked on 5 August 2026 and the results are recorded below:
  the threshold stays at 0.8, its admissible range is now enforced in
  code, and what may be claimed from it is bounded. Reported optimiser
  runs move from 250 evaluations to 500.

## The confidence threshold, checked 5 August 2026

Time to confidence is the only metric here with a free parameter. It was
set to 0.8 by nobody's argument. `tools/threshold_sensitivity.py` sweeps
it over the 80 committed model trajectories at ceiling 1.25 and asks, at
each level, how many reach confidence earlier than the shortest path in
the same world.

The first result was a defect in the measurement, not in the models. At a
threshold of 0.5 the count collapsed to 8 of 55. Six of the eight worlds
have two goals, so the prior is a half, and a threshold of a half is
satisfied before the robot moves: the shortest path scores a time to
confidence of exactly 0.00 and nothing can beat zero. A threshold at or
below the prior is now refused with an error rather than scored, since a
silent zero is worse than a stop, and a test covers it.

Inside the admissible band the metric behaves like this:

| threshold | reach confidence sooner than the baseline | verdicts unchanged from 0.8 |
| --- | --- | --- |
| 0.55 | 25 of 55 | 43 of 55 |
| 0.60 | 25 of 55 | 43 of 55 |
| 0.70 | 25 of 55 | 43 of 55 |
| 0.80 | 23 of 55 | reference |
| 0.90 | 21 of 55 | 53 of 55 |

Two conclusions, and they point opposite ways.

The aggregate is stable. Between 0.55 and 0.90 the count moves only from
25 to 21 of 55, so a claim of the form "about a quarter of model
trajectories reach confidence sooner than the shortest path" survives any
admissible threshold and may be written.

Individual verdicts are not stable. Twelve of 55 flip between 0.7 and
0.8, roughly balanced in both directions, which is why the aggregate holds
while the constituents churn. So no claim about a particular trajectory or
a particular world may rest on time to confidence without stating the
threshold and showing this sweep.

For the report this argues for keeping time to confidence out of the
headline. Legibility, cost ratio, keep-out entries and clearance have no
free parameter at all, and the strongest results already rest only on
those.

## The optimiser's evaluation budget, checked 5 August 2026

Every optimiser number reported so far came from a search of 250
evaluations. A budget too small does not report the frontier, it reports
how far the search got, and nothing in the number itself distinguishes
the two. `tools/budget_convergence.py` reruns all eight worlds at 100,
250, 500 and 1000 at ceiling 1.25 and prints what the extra effort bought.

| scenario | 100 | 250 | 500 | 1000 |
| --- | --- | --- | --- | --- |
| door_pair | 0.8042 | 0.8042 | 0.8042 | 0.8042 |
| fan_middle | 0.4351 | 0.4821 | 0.4829 | 0.4829 |
| fan_outer | 0.6813 | 0.6817 | 0.6817 | 0.6817 |
| keep_out_shortcut | 0.8326 | 0.8327 | 0.8327 | 0.8327 |
| narrow_gap | 0.6623 | 0.6667 | 0.6879 | 0.6879 |
| open_pair | 0.8326 | 0.8327 | 0.8327 | 0.8327 |
| pillar_aisle | 0.8428 | 0.8429 | 0.8429 | 0.8429 |
| wall_choice | 0.6076 | 0.6076 | 0.6076 | 0.6076 |

The reported budget is enough almost everywhere. Six of the eight worlds
gain exactly nothing between 250 and 1000, and `fan_middle` gains 0.0008.
The exception is `narrow_gap`, which gains 0.0212 by 500 and nothing
after: on that world 250 evaluations were reporting the search rather
than the frontier, and a gain of that size is comparable to a whole step
of the cost ceiling elsewhere, so it is not negligible.

One hundred evaluations is too few: `fan_middle` is 0.0478 short there,
which is larger than several ceiling steps.

Consequences. The frontier table in the README and on the portfolio is
`pillar_aisle`, which gains nothing past 250, so those published numbers
stand unchanged. Reported runs from here on use 500, which costs little
and removes the caveat entirely. The library default of 2000 was already
above the converged point and is unchanged.

## Target venue, decided 5 August 2026

An HRI 2027 Late-Breaking Report. Santa Clara, 8 to 12 March 2027. Terms
read from the HRI 2026 LBR call, which is the most recent published:

- Two to four pages excluding references.
- ACM `sigconf`, double column. On Overleaf the class must be set to
  `sigconf` rather than the default `manuscript,screen,review`.
- Fully anonymised at submission, under mutual blind review.
- Archival: accepted LBRs appear in the ACM Digital Library and IEEE
  Xplore. This is a citable publication, not a poster abstract.
- Camera-ready quality at submission. Non-conforming submissions can be
  rejected outright.
- At least one author must agree to review three other LBRs.
- A video figure of at most two minutes is encouraged, which the
  renderer already produces.

The HRI 2027 LBR deadline is not published yet. HRI 2026's was 8
December 2025 with notification 12 January 2026, so early December 2026
is the working assumption and must be confirmed from the 2027 call
before anything is planned around it.

Two deliberate non-choices. The HRI 2027 full paper deadline of 18
September 2026 is not being pursued: the metric is reproducible but not
validated against people, and no amount of engineering answers that
objection in six weeks. RO-MAN 2027 in Waterloo, whose call is not yet
published and whose deadline is expected around March 2027, is the
target for a full paper if a human validation study happens first.

## What the LBR needs before it can be written

- Gemini 3.6 Flash at k = 5, ceiling 1.25, so the headline count covers
  three models rather than two.
- The confidence threshold sensitivity check, listed above.
- The optimiser evaluation budget convergence check, listed above.
- The three literature reads are done, all three in the body, on 5 August
  2026. Dragan, Lee and Srinivasa HRI 2013 and Bastarache et al. ICRA
  2023 both change what may be claimed. The 2010 hand-over paper turned
  out not to be about legibility in this sense at all and is dropped.
  Details in `verification_log.md`.
- The `paper/` build exists as of 5 August 2026 and compiles: ACM
  `sigconf` with the class vendored as `acmart.ins` and `acmart.dtx` and
  generated by the Makefile, since the local TeX distribution does not
  ship it and `tlmgr` refuses a cross-release install. A first full draft
  builds to two pages with zero undefined references and zero errors,
  inside the two to four page limit with room for a figure. Both results
  tables come from `tools/build_paper_results.py` and are never typed.
  What the draft still needs is a figure, the third model, and the
  wording of the validity limitation settled rather than sketched.
- A decision on what two to four pages can hold. The instrument and the
  frontier and the model finding will not all fit; the model finding is
  the one worth the space.

## Ground rules for this draft

- Results tables and figures are generated from committed records by a
  tool and are never edited by hand, so the paper cannot drift from the
  data.
- Counts, not percentages, at small n. Legibility is never reported
  without its paired path cost and safety columns.
- Every number in the prose traces to committed code or committed records.
  `tools/report_suite.py` re-derives the suite inventory that any quoted
  denominator has to come from.
- The related work section carries its own verification log. Every
  citation's bibliographic details are confirmed against public records,
  and every finding attributed to a paper is checked against that paper's
  body rather than its abstract, with the date of each check recorded.
- CI never asserts on rendered image bytes. It asserts on trajectory
  arrays and metric values, and a figure is treated as a rendering of
  numbers that have already been verified.

## Building the PDF

From the TeX distribution, which on this machine is the one inside WSL:

    cd paper && make

The distribution does not ship `acmart` and `tlmgr` refuses a
cross-release install, so the class is vendored as `acmart.ins` and
`acmart.dtx` and the Makefile generates `acmart.cls` from them.
`acmart.cls` is gitignored, so a fresh checkout has to run make and
cannot run latexmk directly.

The class also wants Libertine, Inconsolata and newtx, which the
distribution does not ship either. They are installed into the user tree
at `~/texmf`, which needs no root, from the frozen 2025 repository,
since the current repository is 2026 and tlmgr will not install across
releases:

    tlmgr --usermode --repository \
      https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025/tlnet-final \
      install libertine inconsolata newtx

Installed 5 August 2026. Before that the class fell back to Computer
Modern and said so three times in the log. The PDF now embeds
LinLibertine and the newtx maths fonts as Type 1, which `pdffonts
paper.pdf` will show.

The tables and the figure under `paper/generated/` are written by
`tools/build_paper_results.py` and `tools/build_paper_figures.py` from
the committed records, so both are rerun before the paper after any
completed run. Nothing under `paper/generated/` is edited by hand.

As of 6 August 2026, with related work drafted, the build is three pages
with one warning, the absent city on an anonymised affiliation. It is not
an error and no reference is undefined. Six references are cited and six
are printed, with nothing orphaned. The figure carries a `\Description`
for a reader who cannot see it, and the `\balance` warning went when the
extra section balanced the columns.

One thing the warnings do not catch, fixed the same day. The figure
carried DejaVu Sans as a Type 3 font, because Type 3 is what matplotlib
writes into a PDF unless told otherwise, and publishers commonly refuse
Type 3. `tools/build_paper_figures.py` now sets `pdf.fonttype` to 42 and
the glyphs are embedded as a TrueType subset, which `pdffonts paper.pdf`
shows. What CI checks is the committed figure rather than the setting
that produces it, since a setting can be right in a tool nobody has
rerun. Nothing in the figure moved: the same ten model trajectories are
plotted and all ten still enter the keep-out zone the shortest path
avoids.

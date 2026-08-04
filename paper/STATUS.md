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
- [ ] Planners (the shortest path baseline is built and tested, and is the
  denominator the frontier is measured against; its cost ratio is one by
  construction and it ignores keep-out zones, so the baseline is not
  automatically the safe option. The legibility optimiser is not written
  and is waiting on the parameterisation decision below. A 135-test suite
  in CI, which also re-checks every scenario property against the
  committed code)
- [ ] Scenario suite (not started, and deliberately so: a scenario is only
  worth including if the fact it carries can be stated in terms the code
  can decide, which means the metrics come first)
- [ ] Rendering (not started)
- [ ] Language model evaluation (not started; the model manifest and the
  example config land with it rather than as empty scaffolding now)
- [ ] Literature review (first pass done 4 August 2026, recorded in
  `verification_log.md` with its open obligations; the section is not
  drafted and the positioning is not settled)
- [ ] Writing (nothing drafted)

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

## Open decisions

- Contribution framing. Three candidates were set out before the
  literature check: the safety-constrained frontier, the judge-free
  instrument, and whether language models produce legible motion when
  asked. The first is at risk and the third looks strongest, but nothing
  is settled until the outstanding body-checks in `verification_log.md`
  are done. The code written so far is neutral to all three.
- The trajectory parameterisation the legibility optimiser searches over.
  Arrives with the planners.
- The confidence threshold. It defaults to 0.8 and is recorded in every
  metrics record, but no value has been argued for. Whichever is chosen,
  the results have to be shown to be stable across a range of it or the
  number is a number about the threshold.
- The arrival tolerance for a trajectory proposed by a language model. Our
  own planners land on the goal exactly and the tolerance of one part in a
  million never binds. A model that writes a final waypoint a centimetre
  short is a different case, and whether that is an arrival or a failure
  to reach the goal has to be settled before the runs, not after seeing
  them.
- Target venue. An HRI late-breaking report or an HRI or RO-MAN workshop.
  Not written into the paper until it is decided.

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

Nothing to build yet. The draft starts once the observer model and the
metrics exist and there is something to report that is not a promise.

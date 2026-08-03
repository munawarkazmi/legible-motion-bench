# Working paper status

A living draft, completed as the research completes. Every tick below is
verifiable from this repository; nothing is marked done that cannot be
inspected.

## Current status

- [x] World model (scenarios with exact convex polygonal geometry, exact
  optimal cost-to-go over a visibility graph, and machine-checked
  properties carried inside the scenario files; a 62-test suite in CI,
  which also re-checks every scenario property against the committed code)
- [ ] Observer model (not started; Boltzmann-rational posterior in the
  Dragan form, in two conditions, one whose cost-to-go is the obstacle
  aware geodesic and one whose cost-to-go is the straight line)
- [ ] Metrics (not started)
- [ ] Planners (not started)
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

## Open decisions

- Contribution framing. Three candidates were set out before the
  literature check: the safety-constrained frontier, the judge-free
  instrument, and whether language models produce legible motion when
  asked. The first is at risk and the third looks strongest, but nothing
  is settled until the outstanding body-checks in `verification_log.md`
  are done. The code written so far is neutral to all three.
- The legibility metric's time weighting, the confidence threshold for
  time to confidence, and the trajectory parameterisation the legibility
  optimiser searches over. All three arrive with their components.
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

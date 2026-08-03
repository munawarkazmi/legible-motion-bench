# Scenario suite

Empty on purpose. The benchmark suite is designed after the observer model
and the metrics exist, because a scenario is only worth including if the
fact it carries can be stated in terms the code can decide.

The three worlds under `tests/fixtures/` are not the suite. They exist to
exercise the world model: an open plane, a pillar with a keep-out zone over
it, and a wall that forces the optimal path to turn. They are loaded and
their properties are checked in CI alongside anything that lands here.

Scenario files validate against `legible_motion_bench/schema.py`, version 1,
and carry their own machine-checked properties inline. Run

    python tools/verify_scenarios.py scenarios tests/fixtures

to check them, and add `--write` to record a computed value. No number in a
scenario file is ever typed by hand.

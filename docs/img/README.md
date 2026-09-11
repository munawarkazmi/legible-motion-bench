# Figures

Generated, never drawn by hand. Every animation here is produced from
committed scenarios and committed planner code by

    python tools/render_figures.py scenarios --out docs/img

The GIF files themselves are not committed on every change. They are
derived from the scenarios and the code, they are around a megabyte each,
and their bytes move with the matplotlib version, so committing each
regeneration would fill the history with noise that proves nothing. They
are committed deliberately at milestones, in the same way the paper PDF is,
once the scenario suite exists and a figure is one the paper refers to.

Two are committed. `keep_out_shortcut.gif` is the one the report refers to, in
the default grid. `pillar_aisle.gif` is the world where the cheapest route
crosses the keep-out zone and every legible one stays out of it, laid out in a
single row because it is published at banner width elsewhere:

    python tools/render_figures.py scenarios --out docs/img --columns 4

That is the whole difference between them. Neither is touched afterwards, and a
figure that has been through an image editor is not one of these.

Nothing in CI checks a rendered image. The trajectory arrays and the metric
values are what get asserted, in `tests/test_render.py` and the metric
tests; a GIF is a picture of numbers that were already checked. The belief
bars in an animation are the observer's own samples rather than a second
computation, so a figure and the table beside it cannot disagree.

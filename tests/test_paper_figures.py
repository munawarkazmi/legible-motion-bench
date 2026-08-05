"""What the paper's figures have to satisfy to be submittable.

Not a test of what a figure looks like. Nothing here asserts on pixels or
on plotted coordinates, which move with the matplotlib version and are
checked as numbers elsewhere. What is asserted is the one property a
publisher cares about and a reader cannot see.
"""

from pathlib import Path

GENERATED = Path(__file__).resolve().parents[1] / "paper" / "generated"


def test_no_committed_figure_carries_a_type_3_font():
    # Matplotlib writes Type 3 into a PDF unless told otherwise and
    # publishers commonly refuse it. The committed file is checked rather
    # than the setting that produces it, because the setting can be right
    # in a tool nobody has rerun since it was changed.
    figures = sorted(GENERATED.glob("*.pdf"))
    assert figures, f"no generated figure under {GENERATED}"
    for figure in figures:
        assert b"/Type3" not in figure.read_bytes(), (
            f"{figure.name} carries a Type 3 font; rerun "
            f"tools/build_paper_figures.py"
        )

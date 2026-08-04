"""Animations of trajectories with the observer's belief updating beneath.

The module is in two halves and the split is deliberate. Building a
storyboard is arithmetic: it decides where the robot is at each instant and
what the observer believes there, and it is tested. Drawing is matplotlib,
and it is not tested, because rendered bytes shift between library versions
and a test that asserted on them would fail for reasons that have nothing
to do with this benchmark. A figure here is a picture of numbers that were
already checked somewhere else.

Frames are the metric's own samples, or an evenly spaced subset of them.
That is not a convenience: it means the belief bars in a GIF are the same
values that were scored, rather than a second computation that could
disagree with the table beside it.

The robot moves at constant speed, so a trajectory that pays for clarity is
longer in time as well as in path, and in a comparison it visibly arrives
after the direct one. Panels in a comparison share a clock: the shorter
trajectories finish and wait at their goal while the longer one is still
moving, which is the whole point of animating this at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt

from . import metrics
from .geometry import polyline_length
from .observer import Observer
from .world import Scenario


class RenderError(ValueError):
    """Raised when a figure cannot be drawn as asked."""


@dataclass(frozen=True)
class Frame:
    time: float
    position: tuple[float, float]
    belief: dict | None


@dataclass(frozen=True)
class Storyboard:
    scenario_id: str
    label: str
    observer: str
    frames: tuple[Frame, ...]
    arrival_frame: int
    duration: float
    feasible: bool
    infeasibility: tuple[str, ...]
    result: metrics.TrajectoryMetrics

    @property
    def positions(self) -> tuple:
        return tuple(f.position for f in self.frames)

    def trail(self, index: int) -> tuple:
        return tuple(f.position for f in self.frames[: index + 1])


def storyboard(
    scenario: Scenario,
    observer: Observer,
    points,
    label: str,
    spacing: float = metrics.DEFAULT_SAMPLE_SPACING,
    speed: float = metrics.DEFAULT_SPEED,
    stride: int = 1,
) -> Storyboard:
    """Where the robot is and what is believed about it, instant by instant.

    An infeasible trajectory still gets a storyboard, with no beliefs. It
    is worth watching a proposed path walk through a wall, and the observer
    has nothing to say about it because its cost-to-go is undefined inside
    one.
    """
    if stride < 1:
        raise RenderError(f"stride must be at least one, found {stride}")

    result = metrics.evaluate(scenario, observer, points, spacing=spacing, speed=speed)
    path = [(float(x), float(y)) for x, y in points]
    samples = metrics.resample(path, spacing)
    kept = list(range(0, len(samples), stride))
    if kept[-1] != len(samples) - 1:
        kept.append(len(samples) - 1)

    duration = polyline_length(samples) / speed
    steps = len(samples) - 1
    times = [duration * i / steps for i in kept]

    if result.feasible:
        beliefs = observer.posterior_sequence(scenario, samples)
        frames = tuple(
            Frame(time=t, position=samples[i], belief=dict(beliefs[i]))
            for t, i in zip(times, kept)
        )
    else:
        frames = tuple(
            Frame(time=t, position=samples[i], belief=None)
            for t, i in zip(times, kept)
        )

    return Storyboard(
        scenario_id=scenario.id,
        label=label,
        observer=observer.name,
        frames=frames,
        arrival_frame=len(frames) - 1,
        duration=duration,
        feasible=result.feasible,
        infeasibility=result.infeasibility,
        result=result,
    )


def align(storyboards) -> tuple[Storyboard, ...]:
    """Put several storyboards on one clock.

    Every panel in a comparison must run to the same number of frames or
    the animation says nothing about who arrives first. Shorter
    trajectories hold their final frame, and `arrival_frame` still records
    when each of them actually finished.
    """
    boards = list(storyboards)
    if not boards:
        raise RenderError("nothing to align")
    if len({len(b.frames) for b in boards}) == 1:
        return tuple(boards)

    # The longest trajectory sets the clock, and every panel is given its
    # times, so the caption reads the same instant in all of them.
    master = max(boards, key=lambda b: len(b.frames))
    times = [f.time for f in master.frames]

    aligned = []
    for board in boards:
        held = [
            Frame(
                time=time,
                position=board.frames[min(index, board.arrival_frame)].position,
                belief=board.frames[min(index, board.arrival_frame)].belief,
            )
            for index, time in enumerate(times)
        ]
        aligned.append(
            Storyboard(
                scenario_id=board.scenario_id,
                label=board.label,
                observer=board.observer,
                frames=tuple(held),
                arrival_frame=board.arrival_frame,
                duration=board.duration,
                feasible=board.feasible,
                infeasibility=board.infeasibility,
                result=board.result,
            )
        )
    return tuple(aligned)


def check_panel_grid(count: int, rows: int, columns: int) -> None:
    """Refuse a grid that cannot hold every panel it was given.

    Silent truncation is the failure mode this exists to prevent. A figure
    that quietly drops its seventh panel looks finished and is wrong, and
    nothing downstream can tell.
    """
    if count < 1:
        raise RenderError("a figure needs at least one panel")
    if rows < 1 or columns < 1:
        raise RenderError(f"grid of {rows} by {columns} is empty")
    if rows * columns < count:
        raise RenderError(
            f"a grid of {rows} by {columns} holds {rows * columns} panels "
            f"but {count} were asked for; nothing will be dropped silently"
        )


def panel_grid(count: int, columns: int | None = None) -> tuple[int, int]:
    """Rows and columns for `count` panels, checked before it is returned."""
    if count < 1:
        raise RenderError("a figure needs at least one panel")
    if columns is None:
        columns = min(count, ceil(sqrt(count)))
    rows = ceil(count / columns)
    check_panel_grid(count, rows, columns)
    return rows, columns


def _draw_world(axes, scenario: Scenario) -> None:
    from matplotlib.patches import Polygon

    for zone in scenario.keep_out_zones:
        axes.add_patch(
            Polygon(
                zone.vertices,
                closed=True,
                facecolor="#d9a441",
                edgecolor="#a9762a",
                alpha=0.30,
                hatch="//",
                linewidth=1.0,
                zorder=1,
            )
        )
    for obstacle in scenario.obstacles:
        axes.add_patch(
            Polygon(
                obstacle.vertices,
                closed=True,
                facecolor="#33415c",
                edgecolor="#1b263b",
                linewidth=1.0,
                zorder=2,
            )
        )
    for goal in scenario.goals:
        true_goal = goal.id == scenario.true_goal
        axes.plot(
            goal.position[0],
            goal.position[1],
            marker="*" if true_goal else "o",
            markersize=16 if true_goal else 9,
            color="#c9a227" if true_goal else "#8d99ae",
            zorder=4,
        )
        axes.annotate(
            goal.id,
            goal.position,
            textcoords="offset points",
            xytext=(9, 6),
            fontsize=9,
            color="#1b263b",
        )
    axes.plot(
        scenario.start[0],
        scenario.start[1],
        marker="s",
        markersize=7,
        color="#1b263b",
        zorder=4,
    )
    axes.set_xlim(scenario.bounds.xmin, scenario.bounds.xmax)
    axes.set_ylim(scenario.bounds.ymin, scenario.bounds.ymax)
    axes.set_aspect("equal")
    axes.set_xticks([])
    axes.set_yticks([])


def render_comparison(
    scenario: Scenario,
    storyboards,
    path,
    columns: int | None = None,
    fps: int | None = None,
) -> str:
    """Write an animated GIF with one panel per storyboard.

    Nothing here computes a metric. Every number drawn was produced by
    metrics.py and checked there.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    boards = align(storyboards)
    rows, columns = panel_grid(len(boards), columns)
    frame_count = len(boards[0].frames)
    if fps is None:
        span = boards[0].frames[-1].time - boards[0].frames[0].time
        fps = max(1, round((frame_count - 1) / span)) if span > 0 else 10

    # Each panel is its own subfigure so its belief bars sit against the
    # world they belong to rather than being spaced evenly across the
    # whole figure, which leaves a reader guessing which bars go with
    # which trajectory.
    figure = plt.figure(figsize=(4.4 * columns, 4.8 * rows))
    panels = figure.subfigures(rows, columns, squeeze=False)
    for spare in range(len(boards), rows * columns):
        panels[spare // columns][spare % columns].set_visible(False)

    artists = []
    for index, board in enumerate(boards):
        row, column = divmod(index, columns)
        world, bars = panels[row][column].subplots(
            2, 1, height_ratios=[3, 1], gridspec_kw={"hspace": 0.35}
        )
        _draw_world(world, scenario)

        (trail,) = world.plot([], [], linewidth=2.0, color="#2a6f97", zorder=3)
        (robot,) = world.plot(
            [], [], marker="o", markersize=9, color="#e63946", zorder=5
        )
        world.set_title(board.label, fontsize=10)

        goal_ids = list(scenario.goal_ids)
        heights = bars.barh(
            range(len(goal_ids)),
            [0.0] * len(goal_ids),
            color=[
                "#c9a227" if g == scenario.true_goal else "#8d99ae" for g in goal_ids
            ],
        )
        bars.set_xlim(0.0, 1.12)
        bars.set_yticks(range(len(goal_ids)))
        bars.set_yticklabels(goal_ids, fontsize=9)
        bars.set_xlabel("observer belief", fontsize=9)
        bars.set_xticks([0.0, 0.5, 1.0])
        bars.tick_params(labelsize=8)
        readouts = [
            bars.text(
                1.02,
                position,
                "",
                va="center",
                fontsize=8,
                color="#1b263b",
            )
            for position in range(len(goal_ids))
        ]
        if not board.feasible:
            bars.text(
                0.5,
                0.5,
                "constraint violation\n" + "\n".join(board.infeasibility),
                transform=bars.transAxes,
                ha="center",
                va="center",
                fontsize=8,
                color="#9d0208",
            )
        artists.append((board, trail, robot, heights, readouts, goal_ids))

    clock = figure.suptitle("", fontsize=12)

    def update(index):
        changed = []
        for board, trail, robot, heights, readouts, goal_ids in artists:
            frame = board.frames[index]
            walked = board.trail(min(index, board.arrival_frame))
            trail.set_data([p[0] for p in walked], [p[1] for p in walked])
            robot.set_data([frame.position[0]], [frame.position[1]])
            changed.extend([trail, robot])
            if frame.belief is not None:
                for bar, readout, goal_id in zip(heights, readouts, goal_ids):
                    bar.set_width(frame.belief[goal_id])
                    readout.set_text(f"{frame.belief[goal_id]:.2f}")
                    changed.extend([bar, readout])
        clock.set_text(
            f"{scenario.id}   t = {boards[0].frames[index].time:.2f}s"
        )
        return changed

    animation = FuncAnimation(
        figure, update, frames=frame_count, interval=1000 / fps, blit=False
    )
    animation.save(str(path), writer=PillowWriter(fps=fps))
    plt.close(figure)
    return str(path)

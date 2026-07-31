"""Command-line entry point.

Usage:
    python main.py [--render | --gui [--step]] <map_file>

--render prints a colored per-turn snapshot to stderr in addition to the
SPEC §6 move lines on stdout.
--gui opens a tkinter window and animates the simulation turn by turn.
--step (only with --gui) waits for a keypress before every turn, useful
for demoing to a reviewer.

Exits non-zero on any parse/simulation error and never propagates an
unhandled exception (SPEC §9).
"""

from __future__ import annotations

import sys

from fly_in.exceptions import FlyInError
from fly_in.renderer import Renderer, RendererProtocol
from fly_in.simulation import Simulation


def _parse_argv(argv: list[str]) -> tuple[str, bool, bool, bool]:
    """Return ``(map_path, render, gui, step)``. Raises ``ValueError`` on misuse."""
    render = False
    gui = False
    step = False
    positional: list[str] = []
    for arg in argv[1:]:
        if arg in ("--render", "-r"):
            render = True
        elif arg in ("--gui", "-g"):
            gui = True
        elif arg == "--step":
            step = True
        elif arg in ("--help", "-h"):
            raise ValueError("help")
        else:
            positional.append(arg)
    if len(positional) != 1:
        raise ValueError("expected one map file argument")
    if step and not gui:
        raise ValueError("--step requires --gui")
    return positional[0], render, gui, step


def main(argv: list[str]) -> int:
    """Run the simulator; return a process exit code."""
    try:
        map_path, render_flag, gui_flag, step_flag = _parse_argv(argv)
    except ValueError:
        print(
            f"usage: {argv[0]} [--render | --gui [--step]] <map_file>",
            file=sys.stderr,
        )
        return 2

    try:
        sim = Simulation(map_path)
        sim.load()

        renderer: RendererProtocol | None = None
        gui_renderer = None
        if gui_flag:
            try:
                from fly_in.gui import GraphicalRenderer
            except ImportError as exc:
                print(f"error: --gui requires tkinter: {exc}", file=sys.stderr)
                return 1
            gui_renderer = GraphicalRenderer(
                sim.graph, mode="step" if step_flag else "auto"
            )
            renderer = gui_renderer
        elif render_flag:
            renderer = Renderer(sim.graph, use_color=sys.stderr.isatty())

        sim.run(renderer=renderer)

        if gui_renderer is not None:
            gui_renderer.wait_close()
    except FlyInError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as exc:
        print(f"i/o error: {exc}", file=sys.stderr)
        return 1
    except NotImplementedError as exc:
        print(f"not implemented yet: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level safety net per SPEC §9
        print(f"unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Edge-case tests: disconnected graphs, empty files, whitespace tolerance, CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from fly_in.drone import Drone
from fly_in.exceptions import NoSolutionError, ParseError
from fly_in.parser import Parser
from fly_in.scheduler import Scheduler

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "maps" / "easy" / "01_linear_path.txt"


def _write(tmp_path: Path, contents: str) -> str:
    p = tmp_path / "map.txt"
    p.write_text(contents, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------- parser edges


def test_empty_file_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "")
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_comments_only_file_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "# just a comment\n# another\n")
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_tabs_and_multiple_spaces_accepted(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones:\t1\n"
        "start_hub:   s   0   0\n"
        "end_hub:\te\t1\t0\n"
        "connection:\ts-e\n",
    )
    graph, _ = Parser().parse(path)
    assert graph.start.name == "s"


def test_missing_file_raises_oserror() -> None:
    with pytest.raises(OSError):
        Parser().parse("/nonexistent/does/not/exist.txt")


# --------------------------------------------------------------- solver edges


def test_disconnected_graph_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "hub: island 5 5\n"
        "end_hub: e 10 10\n"
        "connection: s-island\n",
    )
    graph, nb_drones = Parser().parse(path)
    drones = [Drone(id=i + 1, location=graph.start) for i in range(nb_drones)]
    with pytest.raises(NoSolutionError):
        Scheduler(graph).plan(drones)


def test_single_drone_single_hop(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n",
    )
    graph, nb_drones = Parser().parse(path)
    drones = [Drone(id=i + 1, location=graph.start) for i in range(nb_drones)]
    plan = Scheduler(graph).plan(drones)
    assert len(plan) == 1
    assert plan[0][0].location_label == "e"


def test_all_capacity_one_bottleneck_serializes(tmp_path: Path) -> None:
    """A single 1-capacity chokepoint forces N drones through in sequence."""
    path = _write(
        tmp_path,
        "nb_drones: 3\n"
        "start_hub: s 0 0\n"
        "hub: gate 1 0\n"
        "end_hub: e 2 0\n"
        "connection: s-gate\n"
        "connection: gate-e\n",
    )
    graph, nb_drones = Parser().parse(path)
    drones = [Drone(id=i + 1, location=graph.start) for i in range(nb_drones)]
    plan = Scheduler(graph).plan(drones)
    # 3 drones through a 1-capacity gate: last drone arrives at turn 4.
    assert len(plan) == 4


# -------------------------------------------------------------------- CLI


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_happy_path_exit_zero() -> None:
    r = _run_cli(str(MAP))
    assert r.returncode == 0
    assert "D1-" in r.stdout


def test_cli_missing_file_exit_nonzero() -> None:
    r = _run_cli("no-such-file.txt")
    assert r.returncode != 0
    assert "i/o error" in r.stderr


def test_cli_bad_map_prints_line_number(tmp_path: Path) -> None:
    bad = _write(tmp_path, "nb_drones: not_a_number\n")
    r = _run_cli(bad)
    assert r.returncode != 0
    assert "line 1" in r.stderr


def test_cli_no_arg_usage() -> None:
    r = _run_cli()
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_cli_render_flag_produces_stderr_output() -> None:
    r = _run_cli("--render", str(MAP))
    assert r.returncode == 0
    assert "D1-" in r.stdout
    assert "Turn" in r.stderr

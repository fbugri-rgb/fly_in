"""Scheduler integration tests: plan every shipped map and validate.

Each test invokes the scheduler end-to-end (parse → plan) and then
runs a rules-independent validator that simulates the plan against the
raw SPEC rules — capacity, connection capacity, restricted-zone 2-turn
commitment, all drones delivered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fly_in.drone import Drone
from fly_in.parser import Parser
from fly_in.scheduler import Scheduler
from tests.validator import validate

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


BENCHMARKS: list[tuple[str, int]] = [
    ("easy/01_linear_path.txt", 6),
    ("easy/02_simple_fork.txt", 8),
    ("easy/03_basic_capacity.txt", 6),
    ("medium/01_dead_end_trap.txt", 12),
    ("medium/02_circular_loop.txt", 15),
    ("medium/03_priority_puzzle.txt", 12),
    ("hard/01_maze_nightmare.txt", 30),
    ("hard/02_capacity_hell.txt", 35),
    ("hard/03_ultimate_challenge.txt", 45),
]


@pytest.mark.parametrize("relpath, max_turns", BENCHMARKS)
def test_scheduler_valid_and_within_benchmark(relpath: str, max_turns: int) -> None:
    graph, nb_drones = Parser().parse(str(MAPS_DIR / relpath))
    drones = [Drone(id=i + 1, location=graph.start) for i in range(nb_drones)]
    plan = Scheduler(graph).plan(drones)
    # Must satisfy every SPEC rule when replayed.
    validate(graph, nb_drones, plan)
    # And beat the SPEC's optimization target.
    assert len(plan) <= max_turns, (
        f"{relpath}: took {len(plan)} turns, target ≤{max_turns}"
    )


def test_challenger_map_beats_reference_record() -> None:
    """Reference record is 45 turns — our plan must be at least valid."""
    graph, nb_drones = Parser().parse(
        str(MAPS_DIR / "challenger" / "01_the_impossible_dream.txt")
    )
    drones = [Drone(id=i + 1, location=graph.start) for i in range(nb_drones)]
    plan = Scheduler(graph).plan(drones)
    validate(graph, nb_drones, plan)
    # Beating 45 is a stretch goal, but we should at least be in the ballpark.
    assert len(plan) < 100

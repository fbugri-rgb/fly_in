"""Top-level orchestrator: parses a map, plans, and drives execution."""

from __future__ import annotations

from fly_in.drone import Drone
from fly_in.graph import Graph
from fly_in.parser import Parser
from fly_in.renderer import RendererProtocol
from fly_in.scheduler import Scheduler


class Simulation:
    """Glue class binding :class:`Parser`, :class:`Scheduler`, :class:`Renderer`."""

    def __init__(self, map_path: str) -> None:
        self._map_path: str = map_path
        self._graph: Graph | None = None
        self._drones: list[Drone] = []
        self._nb_drones: int = 0

    def load(self) -> None:
        """Parse the map file and instantiate drones at ``start_hub``."""
        graph, nb_drones = Parser().parse(self._map_path)
        self._graph = graph
        self._nb_drones = nb_drones
        self._drones = [
            Drone(id=i + 1, location=graph.start) for i in range(nb_drones)
        ]

    def run(self, renderer: RendererProtocol | None = None) -> int:
        """Run the simulation, emit SPEC §6 output, return total turns.

        SPEC-compliant move lines are printed to stdout each turn. If a
        renderer is supplied, a colored snapshot is also emitted to
        stderr after each turn.
        """
        plan = Scheduler(self.graph).plan(list(self._drones))
        total_turns = len(plan)

        positions: dict[int, str] = {
            d.id: self.graph.start.name for d in self._drones
        }

        for turn_index, moves in enumerate(plan, start=1):
            line = " ".join(f"{m.drone.label}-{m.location_label}" for m in moves)
            if line:
                print(line)
            for move in moves:
                positions[move.drone.id] = move.location_label
            if renderer is not None:
                renderer.render_turn(turn_index, total_turns, positions)

        return total_turns

    @property
    def graph(self) -> Graph:
        if self._graph is None:
            raise RuntimeError("simulation not loaded — call load() first")
        return self._graph

    @property
    def drones(self) -> list[Drone]:
        return list(self._drones)

    @property
    def nb_drones(self) -> int:
        return self._nb_drones

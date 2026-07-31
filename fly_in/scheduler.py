"""Reservation-table scheduler for multi-drone conflict-free routing.

Approach: prioritized planning. Drones are planned one at a time via
space-time BFS; each drone's schedule is committed to a shared
reservation table before the next drone is planned. This is a common
simple technique for multi-agent path finding; it is incomplete (some
solvable instances may require different orderings) but efficient and
easy to reason about live.

State per turn is expressed as a location: either a :class:`ZoneLoc`
(drone rests at a zone) or a :class:`MidConnLoc` (drone is on a
connection heading toward a restricted zone — a 2-turn commitment
per SPEC §4).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Union

from fly_in.drone import Drone
from fly_in.exceptions import NoSolutionError
from fly_in.graph import Graph
from fly_in.zone import ZoneType


@dataclass(frozen=True)
class ZoneLoc:
    """Drone at a zone at the end of some turn."""

    zone: str

    def label(self) -> str:
        return self.zone


@dataclass(frozen=True)
class MidConnLoc:
    """Drone mid-transit toward the restricted zone ``target``."""

    source: str
    target: str

    def label(self) -> str:
        return f"{self.source}-{self.target}"

    @property
    def edge_key(self) -> frozenset[str]:
        return frozenset({self.source, self.target})


Loc = Union[ZoneLoc, MidConnLoc]


@dataclass
class Move:
    """One drone's move on one turn, as emitted to the output."""

    drone: Drone
    location_label: str


class Scheduler:
    """Produce a valid turn-by-turn plan that delivers every drone."""

    def __init__(self, graph: Graph, max_turns: int = 500) -> None:
        self._graph = graph
        self._max_turns = max_turns
        # Cache link capacities by edge key for O(1) lookup during BFS.
        self._link_cap: dict[frozenset[str], int] = {
            conn.key(): conn.max_link_capacity for conn in graph.connections
        }

    def plan(self, drones: list[Drone]) -> list[list[Move]]:
        """Return one list of :class:`Move` per simulation turn."""
        zone_res: dict[tuple[str, int], int] = {}
        edge_res: dict[tuple[frozenset[str], int], int] = {}

        # Turn 0: every drone at the (unlimited-capacity) start hub.
        zone_res[(self._graph.start.name, 0)] = len(drones)

        schedules: list[list[Loc]] = []
        for drone in drones:
            schedule = self._plan_one(drone, zone_res, edge_res)
            self._commit(schedule, zone_res, edge_res)
            schedules.append(schedule)

        return self._build_moves(drones, schedules)

    # ------------------------------------------------------- per-drone search

    def _plan_one(
        self,
        drone: Drone,
        zone_res: dict[tuple[str, int], int],
        edge_res: dict[tuple[frozenset[str], int], int],
    ) -> list[Loc]:
        """Space-time BFS from start to end respecting current reservations."""
        goal_zone = self._graph.end.name
        start_state: tuple[Loc, int] = (ZoneLoc(self._graph.start.name), 0)

        parent: dict[tuple[Loc, int], tuple[Loc, int] | None] = {start_state: None}
        queue: deque[tuple[Loc, int]] = deque([start_state])
        goal_state: tuple[Loc, int] | None = None

        while queue:
            state = queue.popleft()
            loc, turn = state
            if isinstance(loc, ZoneLoc) and loc.zone == goal_zone:
                goal_state = state
                break
            if turn >= self._max_turns:
                continue
            for successor in self._successors(state, zone_res, edge_res):
                if successor not in parent:
                    parent[successor] = state
                    queue.append(successor)

        if goal_state is None:
            raise NoSolutionError(
                f"cannot schedule {drone.label} to reach {goal_zone!r} "
                f"within {self._max_turns} turns"
            )

        return self._reconstruct(parent, goal_state)

    def _reconstruct(
        self,
        parent: dict[tuple[Loc, int], tuple[Loc, int] | None],
        goal: tuple[Loc, int],
    ) -> list[Loc]:
        _, total = goal
        schedule: list[Loc | None] = [None] * (total + 1)
        cursor: tuple[Loc, int] | None = goal
        while cursor is not None:
            loc, t = cursor
            schedule[t] = loc
            cursor = parent[cursor]
        # Filter Nones for type checker; by construction all slots are filled.
        return [loc for loc in schedule if loc is not None]

    # ---------------------------------------------------------------- movement

    def _successors(
        self,
        state: tuple[Loc, int],
        zone_res: dict[tuple[str, int], int],
        edge_res: dict[tuple[frozenset[str], int], int],
    ) -> list[tuple[Loc, int]]:
        loc, turn = state
        next_turn = turn + 1
        out: list[tuple[Loc, int]] = []

        # MidConn: forced arrival next turn at target (2-turn commitment done).
        if isinstance(loc, MidConnLoc):
            target = self._graph.zone(loc.target)
            if self._zone_free(target.name, next_turn, target.capacity, zone_res):
                if self._edge_free(loc.edge_key, next_turn, edge_res):
                    out.append((ZoneLoc(target.name), next_turn))
            return out

        # ZoneLoc: wait, or move to a neighbor.
        current = self._graph.zone(loc.zone)

        if self._zone_free(current.name, next_turn, current.capacity, zone_res):
            out.append((ZoneLoc(current.name), next_turn))

        for conn in self._graph.neighbors(current):
            neighbor = conn.other(current)
            if not neighbor.is_accessible:
                continue
            key = conn.key()
            if not self._edge_free(key, next_turn, edge_res):
                continue

            if neighbor.zone_type is ZoneType.RESTRICTED:
                # Verify the full 2-turn commitment is feasible before
                # entering the connection — no aborting mid-transit.
                if next_turn + 1 > self._max_turns:
                    continue
                if not self._edge_free(key, next_turn + 1, edge_res):
                    continue
                if not self._zone_free(
                    neighbor.name, next_turn + 1, neighbor.capacity, zone_res
                ):
                    continue
                out.append((MidConnLoc(current.name, neighbor.name), next_turn))
            else:
                if self._zone_free(
                    neighbor.name, next_turn, neighbor.capacity, zone_res
                ):
                    out.append((ZoneLoc(neighbor.name), next_turn))

        return out

    # ---------------------------------------------------------------- helpers

    def _zone_free(
        self,
        name: str,
        turn: int,
        capacity: int,
        zone_res: dict[tuple[str, int], int],
    ) -> bool:
        return zone_res.get((name, turn), 0) < capacity

    def _edge_free(
        self,
        key: frozenset[str],
        turn: int,
        edge_res: dict[tuple[frozenset[str], int], int],
    ) -> bool:
        return edge_res.get((key, turn), 0) < self._link_cap[key]

    # ------------------------------------------------------------------ commit

    def _commit(
        self,
        schedule: list[Loc],
        zone_res: dict[tuple[str, int], int],
        edge_res: dict[tuple[frozenset[str], int], int],
    ) -> None:
        # Zone occupancy per turn. Skip turn 0 — the start-hub occupancy for
        # all drones was reserved once in :pymeth:`plan`.
        for t, loc in enumerate(schedule):
            if t == 0:
                continue
            if isinstance(loc, ZoneLoc):
                zone_res[(loc.zone, t)] = zone_res.get((loc.zone, t), 0) + 1

        # Edge crossings per transition.
        for t in range(1, len(schedule)):
            prev = schedule[t - 1]
            cur = schedule[t]
            key: frozenset[str] | None = None
            if isinstance(prev, ZoneLoc) and isinstance(cur, ZoneLoc):
                if prev.zone != cur.zone:
                    key = frozenset({prev.zone, cur.zone})
            elif isinstance(prev, ZoneLoc) and isinstance(cur, MidConnLoc):
                key = cur.edge_key
            elif isinstance(prev, MidConnLoc) and isinstance(cur, ZoneLoc):
                key = prev.edge_key
            if key is not None:
                edge_res[(key, t)] = edge_res.get((key, t), 0) + 1

    # ------------------------------------------------------------- output plan

    def _build_moves(
        self,
        drones: list[Drone],
        schedules: list[list[Loc]],
    ) -> list[list[Move]]:
        total = max((len(s) - 1 for s in schedules), default=0)
        turns: list[list[Move]] = []
        for t in range(1, total + 1):
            per_turn: list[Move] = []
            for drone, sched in zip(drones, schedules):
                if t >= len(sched):
                    continue  # already delivered
                cur = sched[t]
                prev = sched[t - 1]
                # Skip pure waits (drone stayed on the same zone).
                if (
                    isinstance(prev, ZoneLoc)
                    and isinstance(cur, ZoneLoc)
                    and prev.zone == cur.zone
                ):
                    continue
                per_turn.append(Move(drone=drone, location_label=cur.label()))
            turns.append(per_turn)
        return turns

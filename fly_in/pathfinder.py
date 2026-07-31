"""Single-drone pathfinding — no external graph libraries (see SPEC §5)."""

from __future__ import annotations

import heapq

from fly_in.exceptions import NoSolutionError
from fly_in.graph import Graph
from fly_in.zone import Zone, ZoneType

# Base edge cost is scaled by 1000 so we have room for a soft priority
# tiebreak. Total path cost is dominated by turn count; priority zones
# are only preferred when path lengths would otherwise tie.
_COST_SCALE: int = 1000
_PRIORITY_DISCOUNT: int = 1

# On each iteration of the penalty-based k-shortest search, intermediate
# zones of the found path get this much added to their entry cost. Twice
# the base makes reused zones about as expensive as restricted ones on
# the next pass, which is enough to divert most routes.
_PENALTY_STEP: int = 2 * _COST_SCALE


class PathFinder:
    """Cost-weighted shortest-path search over a :class:`Graph`.

    Costs come from :pyattr:`fly_in.zone.Zone.movement_cost` (restricted
    zones cost 2). Priority zones share the base cost of 1 but win ties
    via a small discount, so the pathfinder naturally routes through
    them when it can do so without paying extra turns.
    """

    def __init__(self, graph: Graph) -> None:
        self._graph = graph

    def shortest_path(self, start: Zone, end: Zone) -> list[Zone]:
        """Return the cheapest zone sequence from ``start`` to ``end``.

        The result includes both endpoints. Raises
        :class:`fly_in.exceptions.NoSolutionError` when ``end`` is
        unreachable (blocked zones or disconnected components).
        """
        path = self._dijkstra(start, end, penalty={})
        if path is None:
            raise NoSolutionError(f"no path from {start.name!r} to {end.name!r}")
        return path

    def k_shortest_paths(self, start: Zone, end: Zone, k: int) -> list[list[Zone]]:
        """Return up to ``k`` distinct low-cost paths for load spreading.

        Uses an iterative penalty scheme: after each found path, its
        intermediate zones accrue a cost bump so the next Dijkstra pass
        is biased toward alternative routes. Stops early if no new
        distinct path can be discovered.
        """
        if k <= 0:
            return []
        penalty: dict[str, int] = {}
        seen: set[tuple[str, ...]] = set()
        results: list[list[Zone]] = []
        for _ in range(k):
            path = self._dijkstra(start, end, penalty)
            if path is None:
                break
            signature = tuple(z.name for z in path)
            if signature in seen:
                break
            seen.add(signature)
            results.append(path)
            for z in path[1:-1]:
                penalty[z.name] = penalty.get(z.name, 0) + _PENALTY_STEP
        return results

    def path_turn_count(self, path: list[Zone]) -> int:
        """Total simulation turns for a drone to traverse ``path`` uncontested."""
        # Start zone is where the drone begins — it is not "entered".
        return sum(z.movement_cost for z in path[1:])

    # -------------------------------------------------------------- internals

    def _entry_cost(self, zone: Zone, penalty: dict[str, int]) -> int:
        base = zone.movement_cost * _COST_SCALE
        if zone.zone_type is ZoneType.PRIORITY:
            base -= _PRIORITY_DISCOUNT
        return base + penalty.get(zone.name, 0)

    def _dijkstra(
        self, start: Zone, end: Zone, penalty: dict[str, int]
    ) -> list[Zone] | None:
        """Standard Dijkstra with priority-tiebreak weights. Skips blocked zones."""
        if not start.is_accessible or not end.is_accessible:
            return None

        dist: dict[str, int] = {start.name: 0}
        parent: dict[str, str] = {}
        pq: list[tuple[int, str]] = [(0, start.name)]

        while pq:
            d, name = heapq.heappop(pq)
            if name == end.name:
                return self._reconstruct(parent, start, end)
            existing = dist.get(name)
            if existing is not None and d > existing:
                continue  # stale queue entry

            current = self._graph.zone(name)
            for conn in self._graph.neighbors(current):
                neighbor = conn.other(current)
                if not neighbor.is_accessible:
                    continue
                new_dist = d + self._entry_cost(neighbor, penalty)
                seen_dist = dist.get(neighbor.name)
                if seen_dist is None or new_dist < seen_dist:
                    dist[neighbor.name] = new_dist
                    parent[neighbor.name] = name
                    heapq.heappush(pq, (new_dist, neighbor.name))
        return None

    def _reconstruct(
        self, parent: dict[str, str], start: Zone, end: Zone
    ) -> list[Zone]:
        names: list[str] = [end.name]
        while names[-1] != start.name:
            names.append(parent[names[-1]])
        names.reverse()
        return [self._graph.zone(n) for n in names]

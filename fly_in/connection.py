"""Connection (bidirectional graph edge) definition."""

from __future__ import annotations

from dataclasses import dataclass

from fly_in.zone import Zone


@dataclass
class Connection:
    """A bidirectional edge between two zones.

    Connections have their own per-turn traversal capacity, distinct from
    zone capacity. For pathfinding purposes ``a-b`` and ``b-a`` are the
    same edge.
    """

    a: Zone
    b: Zone
    max_link_capacity: int = 1

    def key(self) -> frozenset[str]:
        """Canonical, order-independent identifier for the edge."""
        return frozenset({self.a.name, self.b.name})

    def other(self, zone: Zone) -> Zone:
        """Return the zone on the far side of this connection from ``zone``."""
        if zone is self.a or zone.name == self.a.name:
            return self.b
        if zone is self.b or zone.name == self.b.name:
            return self.a
        raise ValueError(f"zone {zone.name!r} is not an endpoint of this connection")

    def __repr__(self) -> str:
        return f"Connection({self.a.name}-{self.b.name}, cap={self.max_link_capacity})"

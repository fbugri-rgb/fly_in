"""In-memory graph of zones and connections."""

from __future__ import annotations

from typing import Iterable

from fly_in.connection import Connection
from fly_in.zone import Zone


class Graph:
    """Adjacency-list graph. Owns all zones and connections for one map."""

    def __init__(self) -> None:
        self._zones: dict[str, Zone] = {}
        self._connections: list[Connection] = []
        self._adjacency: dict[str, list[Connection]] = {}
        self._start: Zone | None = None
        self._end: Zone | None = None

    # ------------------------------------------------------------------ zones
    def add_zone(self, zone: Zone) -> None:
        """Register a zone. Duplicates are rejected by the caller (parser)."""
        self._zones[zone.name] = zone
        self._adjacency.setdefault(zone.name, [])
        if zone.is_start:
            self._start = zone
        if zone.is_end:
            self._end = zone

    def zone(self, name: str) -> Zone:
        """Look up a zone by name. Raises ``KeyError`` if unknown."""
        return self._zones[name]

    def has_zone(self, name: str) -> bool:
        return name in self._zones

    @property
    def zones(self) -> Iterable[Zone]:
        return self._zones.values()

    # ------------------------------------------------------------ connections
    def add_connection(self, connection: Connection) -> None:
        """Register a bidirectional edge. Duplicates are rejected by the caller."""
        self._connections.append(connection)
        self._adjacency[connection.a.name].append(connection)
        self._adjacency[connection.b.name].append(connection)

    def neighbors(self, zone: Zone) -> list[Connection]:
        """Return every connection incident to ``zone``."""
        return list(self._adjacency.get(zone.name, ()))

    @property
    def connections(self) -> Iterable[Connection]:
        return list(self._connections)

    # --------------------------------------------------------------- endpoints
    @property
    def start(self) -> Zone:
        """The unique ``start_hub`` — set by :pymeth:`add_zone`."""
        if self._start is None:
            raise ValueError("graph has no start_hub")
        return self._start

    @property
    def end(self) -> Zone:
        """The unique ``end_hub`` — set by :pymeth:`add_zone`."""
        if self._end is None:
            raise ValueError("graph has no end_hub")
        return self._end

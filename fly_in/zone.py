"""Zone (graph node) definition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

UNLIMITED_CAPACITY: int = 10 ** 9


class ZoneType(Enum):
    """Movement/access characteristics of a zone.

    ``normal``   — 1-turn traversal, default.
    ``priority`` — 1-turn traversal, preferred by pathfinding.
    ``restricted`` — 2-turn traversal via connection commitment.
    ``blocked``  — inaccessible; a drone may never enter it.
    """

    NORMAL = "normal"
    PRIORITY = "priority"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"


@dataclass
class Zone:
    """A vertex in the drone-routing graph.

    Coordinates are integers per spec. ``max_drones`` is ignored for
    start/end hubs (see :pyattr:`capacity`).
    """

    name: str
    x: int
    y: int
    zone_type: ZoneType = ZoneType.NORMAL
    color: str | None = None
    max_drones: int = 1
    is_start: bool = False
    is_end: bool = False

    @property
    def movement_cost(self) -> int:
        """Turns spent traversing into this zone (1 for normal/priority, 2 for restricted)."""
        if self.zone_type is ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_accessible(self) -> bool:
        """Whether a drone can ever enter this zone."""
        return self.zone_type is not ZoneType.BLOCKED

    @property
    def capacity(self) -> int:
        """Effective per-turn drone capacity (start/end hubs are unlimited)."""
        if self.is_start or self.is_end:
            return UNLIMITED_CAPACITY
        return self.max_drones

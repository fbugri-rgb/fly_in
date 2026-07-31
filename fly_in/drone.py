"""Drone entity: a single mobile agent traversing the graph."""

from __future__ import annotations

from dataclasses import dataclass

from fly_in.zone import Zone


@dataclass
class Drone:
    """One drone in the simulation.

    ``location`` is either the current zone (normal case) or ``None`` once
    delivered. During the two-turn transit into a restricted zone the
    drone's location is the *source* zone; the scheduler tracks the
    in-flight commitment on the connection separately.
    """

    id: int
    location: Zone | None
    delivered: bool = False

    @property
    def label(self) -> str:
        """Display label, e.g. ``D1``."""
        return f"D{self.id}"

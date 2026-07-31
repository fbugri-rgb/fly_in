"""Colored terminal renderer (SPEC §13).

Per-turn snapshot showing which drones occupy which zones, colored per
the ``color=`` metadata on the zone, plus a list of drones mid-transit
toward restricted zones. Output goes to stderr so the SPEC §6 move lines
on stdout remain machine-parseable.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from fly_in.graph import Graph

# Best-effort mapping from human-color names (any string per spec) to
# a small palette of ANSI foreground codes. Unknown names render plain.
_ANSI_RESET: str = "\033[0m"
_ANSI_COLORS: dict[str, str] = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "orange": "\033[33m",
    "purple": "\033[35m",
    "pink": "\033[95m",
    "gold": "\033[93m",
    "lime": "\033[92m",
    "brown": "\033[33m",
}


class Renderer:
    """Colored terminal display of graph state each turn.

    Zone ``color=`` metadata is applied where possible; unknown color
    names render as plain text. ``use_color`` may be disabled (e.g. for
    non-TTY output) to strip escape codes entirely.
    """

    def __init__(self, graph: Graph, use_color: bool = True) -> None:
        self._graph = graph
        self._use_color = use_color

    def render_turn(
        self, turn_index: int, total_turns: int, positions: dict[int, str]
    ) -> None:
        """Print a snapshot showing where every drone is at end of ``turn_index``.

        ``positions`` maps drone id to a location label — either a zone
        name or ``"source-target"`` for a drone mid-transit toward the
        restricted zone ``target``.
        """
        by_zone: dict[str, list[int]] = defaultdict(list)
        by_edge: dict[str, list[int]] = defaultdict(list)
        for drone_id, label in positions.items():
            if self._graph.has_zone(label):
                by_zone[label].append(drone_id)
            else:
                by_edge[label].append(drone_id)

        end_name = self._graph.end.name
        delivered = len(by_zone.get(end_name, []))
        total_drones = len(positions)

        print(
            f"── Turn {turn_index}/{total_turns} "
            f"— delivered {delivered}/{total_drones} ──",
            file=sys.stderr,
        )
        for zone in self._graph.zones:
            drones_here = by_zone.get(zone.name, [])
            if not drones_here:
                continue
            name_display = self._colorize(zone.name.ljust(22), zone.color)
            drones_str = " ".join(f"D{i}" for i in sorted(drones_here))
            print(f"  {name_display} {drones_str}", file=sys.stderr)

        if by_edge:
            print("  mid-transit:", file=sys.stderr)
            for label, ids in sorted(by_edge.items()):
                drones_str = " ".join(f"D{i}" for i in sorted(ids))
                print(f"    {label:<22} {drones_str}", file=sys.stderr)

    def _colorize(self, text: str, color: str | None) -> str:
        if not self._use_color or color is None:
            return text
        code = _ANSI_COLORS.get(color.lower())
        if code is None:
            return text
        return f"{code}{text}{_ANSI_RESET}"

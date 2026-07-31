"""tkinter graphical interface for the drone simulation (SPEC §13).

Renders each turn on a Tk canvas: zones drawn at their ``(x, y)`` map
coordinates, connections as edges, drones as small labeled dots inside
the zone they occupy (or along the connection line while mid-transit
toward a restricted zone). Zone fill color follows the map's ``color=``
metadata; the zone type is signaled by the outline (restricted → red,
priority → green, blocked → gray).

``tkinter`` is stdlib but can be absent from stripped-down Python
builds. This module is imported lazily by ``main.py`` so the rest of
the package works even where Tk is unavailable.
"""

from __future__ import annotations

import math
import tkinter as tk
from collections import defaultdict

from fly_in.graph import Graph
from fly_in.zone import ZoneType

_WINDOW_W: int = 1000
_WINDOW_H: int = 720
_PAD: int = 60
_HEADER_H: int = 60
_ZONE_R: int = 26
_DRONE_R: int = 8
_TURN_DELAY_MS: int = 500

# ``color=`` metadata → hex fill. Unknown names fall back to a neutral tone.
_FILL: dict[str, str] = {
    "red": "#e74c3c",
    "green": "#2ecc71",
    "yellow": "#f1c40f",
    "blue": "#3498db",
    "magenta": "#9b59b6",
    "cyan": "#1abc9c",
    "white": "#ecf0f1",
    "gray": "#95a5a6",
    "grey": "#95a5a6",
    "orange": "#e67e22",
    "purple": "#8e44ad",
    "pink": "#fd79a8",
    "gold": "#f39c12",
    "lime": "#a3e635",
    "brown": "#a0522d",
}
_DEFAULT_FILL: str = "#ecf0f1"
_DRONE_FILL: str = "#2c3e50"
_DRONE_TEXT: str = "#ecf0f1"
_EDGE_FILL: str = "#7f8c8d"


class GraphicalRenderer:
    """Tk canvas renderer. Duck-types the terminal :class:`Renderer` API."""

    def __init__(self, graph: Graph, turn_delay_ms: int = _TURN_DELAY_MS) -> None:
        self._graph = graph
        self._delay = turn_delay_ms
        self._root = tk.Tk()
        self._root.title("Fly-In")
        self._root.geometry(f"{_WINDOW_W}x{_WINDOW_H}")
        self._canvas = tk.Canvas(
            self._root, width=_WINDOW_W, height=_WINDOW_H, bg="white"
        )
        self._canvas.pack(fill="both", expand=True)
        self._pixel: dict[str, tuple[int, int]] = self._compute_layout()

    def render_turn(
        self, turn_idx: int, total_turns: int, positions: dict[int, str]
    ) -> None:
        """Redraw the canvas for the given turn and pause for the animation delay."""
        self._draw(turn_idx, total_turns, positions)
        self._wait_ms(self._delay)

    def wait_close(self) -> None:
        """Keep the window open until the user closes it."""
        self._canvas.create_text(
            _WINDOW_W // 2, _WINDOW_H - 20,
            text="Simulation complete — close window to exit",
            font=("TkDefaultFont", 11, "italic"),
            fill="#2c3e50",
        )
        self._root.mainloop()

    # -------------------------------------------------------------- internals

    def _compute_layout(self) -> dict[str, tuple[int, int]]:
        zones = list(self._graph.zones)
        xs = [z.x for z in zones]
        ys = [z.y for z in zones]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1, max_x - min_x)
        span_y = max(1, max_y - min_y)
        usable_w = _WINDOW_W - 2 * _PAD
        usable_h = _WINDOW_H - 2 * _PAD - _HEADER_H

        pixel: dict[str, tuple[int, int]] = {}
        for zone in zones:
            px = _PAD + int((zone.x - min_x) / span_x * usable_w)
            # Flip Y so map-up appears screen-up.
            py = _PAD + _HEADER_H + int((max_y - zone.y) / span_y * usable_h)
            pixel[zone.name] = (px, py)
        return pixel

    def _draw(
        self, turn_idx: int, total_turns: int, positions: dict[int, str]
    ) -> None:
        self._canvas.delete("all")

        end_name = self._graph.end.name
        delivered = sum(1 for label in positions.values() if label == end_name)
        header = (
            f"Turn {turn_idx} / {total_turns}   —   "
            f"delivered {delivered} / {len(positions)}"
        )
        self._canvas.create_text(
            _WINDOW_W // 2, 30, text=header,
            font=("TkDefaultFont", 16, "bold"), fill="#2c3e50",
        )

        # Connections first, so zones sit on top.
        for conn in self._graph.connections:
            x1, y1 = self._pixel[conn.a.name]
            x2, y2 = self._pixel[conn.b.name]
            self._canvas.create_line(x1, y1, x2, y2, fill=_EDGE_FILL, width=2)

        # Zones.
        for zone in self._graph.zones:
            px, py = self._pixel[zone.name]
            fill = _FILL.get((zone.color or "").lower(), _DEFAULT_FILL)
            outline, width = self._outline_for(zone.zone_type)
            self._canvas.create_oval(
                px - _ZONE_R, py - _ZONE_R,
                px + _ZONE_R, py + _ZONE_R,
                fill=fill, outline=outline, width=width,
            )
            self._canvas.create_text(
                px, py - _ZONE_R - 12,
                text=zone.name, font=("TkDefaultFont", 9),
                fill="#2c3e50",
            )

        # Group drones per zone / per edge.
        by_zone: dict[str, list[int]] = defaultdict(list)
        by_edge: dict[tuple[str, str], list[int]] = defaultdict(list)
        for drone_id, label in positions.items():
            if self._graph.has_zone(label):
                by_zone[label].append(drone_id)
            else:
                source, target = label.split("-", 1)
                by_edge[(source, target)].append(drone_id)

        for zone_name, ids in by_zone.items():
            px, py = self._pixel[zone_name]
            for i, drone_id in enumerate(sorted(ids)):
                dpx, dpy = self._offset_in_zone(px, py, i, len(ids))
                self._paint_drone(dpx, dpy, drone_id)

        for (source, target), ids in by_edge.items():
            if source not in self._pixel or target not in self._pixel:
                continue
            x1, y1 = self._pixel[source]
            x2, y2 = self._pixel[target]
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            dx = x2 - x1
            dy = y2 - y1
            length = max(1.0, math.hypot(dx, dy))
            perp_x = -dy / length
            perp_y = dx / length
            for i, drone_id in enumerate(sorted(ids)):
                offset = (i - (len(ids) - 1) / 2) * 14
                self._paint_drone(
                    mx + perp_x * offset, my + perp_y * offset, drone_id
                )

    def _outline_for(self, zone_type: ZoneType) -> tuple[str, int]:
        if zone_type is ZoneType.RESTRICTED:
            return "#c0392b", 3
        if zone_type is ZoneType.PRIORITY:
            return "#27ae60", 3
        if zone_type is ZoneType.BLOCKED:
            return "#7f8c8d", 3
        return "#2c3e50", 2

    def _offset_in_zone(
        self, px: int, py: int, index: int, count: int
    ) -> tuple[float, float]:
        if count == 1:
            return float(px), float(py)
        angle = 2 * math.pi * index / count
        radius = _ZONE_R * 0.55
        return px + radius * math.cos(angle), py + radius * math.sin(angle)

    def _paint_drone(self, x: float, y: float, drone_id: int) -> None:
        self._canvas.create_oval(
            x - _DRONE_R, y - _DRONE_R, x + _DRONE_R, y + _DRONE_R,
            fill=_DRONE_FILL, outline="black",
        )
        self._canvas.create_text(
            x, y, text=str(drone_id),
            fill=_DRONE_TEXT, font=("TkDefaultFont", 8, "bold"),
        )

    def _wait_ms(self, ms: int) -> None:
        """Sleep for ``ms`` ms while keeping the Tk event loop responsive."""
        var = tk.IntVar()
        self._root.after(ms, lambda: var.set(1))
        self._root.wait_variable(var)

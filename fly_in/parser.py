"""Map-file parser. See SPEC.md §2 for the file grammar."""

from __future__ import annotations

import re

from fly_in.connection import Connection
from fly_in.exceptions import ParseError
from fly_in.graph import Graph
from fly_in.zone import Zone, ZoneType

_ZONE_KIND_START = "start_hub"
_ZONE_KIND_END = "end_hub"
_ZONE_KIND_HUB = "hub"

# Zone names must not contain whitespace or dashes (§2).
_NAME_INVALID = re.compile(r"[\s\-]")

# Anchor-anchored match: everything up to an optional [metadata] block at end.
_METADATA_RE = re.compile(r"^(?P<before>.*?)\s*\[(?P<inside>[^\[\]]*)\]\s*$")

_ZONE_METADATA_KEYS = {"zone", "color", "max_drones"}
_CONNECTION_METADATA_KEYS = {"max_link_capacity"}


class Parser:
    """Reads a map file and produces a :class:`Graph` plus drone count.

    Any malformed input raises :class:`fly_in.exceptions.ParseError` with
    the offending line number and a human-readable cause. Parsing builds
    the graph in-place and returns it fully populated, or raises — the
    caller never sees a partial graph.
    """

    def parse(self, path: str) -> tuple[Graph, int]:
        """Parse ``path`` and return ``(graph, nb_drones)``."""
        graph = Graph()
        nb_drones: int | None = None
        seen_zones: set[str] = set()
        seen_start = False
        seen_end = False
        seen_connections: set[frozenset[str]] = set()

        with open(path, "r", encoding="utf-8") as handle:
            for line_no, raw in enumerate(handle, start=1):
                line = raw.rstrip("\r\n").strip()
                if not line or line.startswith("#"):
                    continue

                if nb_drones is None:
                    nb_drones = self._parse_nb_drones(line, line_no)
                    continue

                if line.startswith("nb_drones"):
                    raise ParseError(line_no, "duplicate nb_drones declaration")

                if line.startswith(_ZONE_KIND_START + ":"):
                    if seen_start:
                        raise ParseError(line_no, "duplicate start_hub declaration")
                    zone = self._parse_zone(line, line_no, kind=_ZONE_KIND_START)
                    self._register_zone(zone, seen_zones, line_no)
                    graph.add_zone(zone)
                    seen_start = True
                elif line.startswith(_ZONE_KIND_END + ":"):
                    if seen_end:
                        raise ParseError(line_no, "duplicate end_hub declaration")
                    zone = self._parse_zone(line, line_no, kind=_ZONE_KIND_END)
                    self._register_zone(zone, seen_zones, line_no)
                    graph.add_zone(zone)
                    seen_end = True
                elif line.startswith(_ZONE_KIND_HUB + ":"):
                    zone = self._parse_zone(line, line_no, kind=_ZONE_KIND_HUB)
                    self._register_zone(zone, seen_zones, line_no)
                    graph.add_zone(zone)
                elif line.startswith("connection:"):
                    conn = self._parse_connection(line, line_no, graph)
                    key = conn.key()
                    if key in seen_connections:
                        raise ParseError(
                            line_no,
                            f"duplicate connection between "
                            f"{conn.a.name!r} and {conn.b.name!r}",
                        )
                    seen_connections.add(key)
                    graph.add_connection(conn)
                else:
                    raise ParseError(line_no, f"unknown directive: {line!r}")

        if nb_drones is None:
            raise ParseError(0, "missing nb_drones declaration")
        if not seen_start:
            raise ParseError(0, "missing start_hub declaration")
        if not seen_end:
            raise ParseError(0, "missing end_hub declaration")

        return graph, nb_drones

    # -------------------------------------------------------------- directives

    def _parse_nb_drones(self, line: str, line_no: int) -> int:
        if not line.startswith("nb_drones:"):
            raise ParseError(line_no, "first non-empty line must declare nb_drones")
        value = line[len("nb_drones:"):].strip()
        return self._parse_positive_int(value, "nb_drones", line_no)

    def _parse_zone(self, line: str, line_no: int, kind: str) -> Zone:
        payload = line[len(kind) + 1:].strip()
        inside, before = self._split_metadata(payload, line_no)

        tokens = before.split()
        if len(tokens) != 3:
            raise ParseError(
                line_no, f"{kind} expects '<name> <x> <y>', got {before!r}"
            )
        name, x_str, y_str = tokens
        self._validate_zone_name(name, line_no)
        try:
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            raise ParseError(
                line_no,
                f"zone coordinates must be integers, got x={x_str!r} y={y_str!r}",
            )

        metadata = self._parse_metadata(inside, _ZONE_METADATA_KEYS, line_no)

        zone_type = ZoneType.NORMAL
        color: str | None = None
        max_drones = 1

        is_start = kind == _ZONE_KIND_START
        is_end = kind == _ZONE_KIND_END

        if "zone" in metadata:
            if is_start or is_end:
                raise ParseError(
                    line_no, f"{kind} does not accept a zone= type override"
                )
            raw_type = metadata["zone"]
            try:
                zone_type = ZoneType(raw_type)
            except ValueError:
                raise ParseError(line_no, f"unknown zone type {raw_type!r}")
        if "color" in metadata:
            color = metadata["color"]
        if "max_drones" in metadata and not (is_start or is_end):
            max_drones = self._parse_positive_int(
                metadata["max_drones"], "max_drones", line_no
            )

        return Zone(
            name=name,
            x=x,
            y=y,
            zone_type=zone_type,
            color=color,
            max_drones=max_drones,
            is_start=is_start,
            is_end=is_end,
        )

    def _parse_connection(
        self, line: str, line_no: int, graph: Graph
    ) -> Connection:
        payload = line[len("connection:"):].strip()
        inside, before = self._split_metadata(payload, line_no)

        tokens = before.split()
        if len(tokens) != 1:
            raise ParseError(
                line_no, f"connection expects '<name1>-<name2>', got {before!r}"
            )
        edge = tokens[0]
        if edge.count("-") != 1:
            raise ParseError(
                line_no,
                f"connection endpoints must be joined by exactly one dash, got {edge!r}",
            )
        name_a, name_b = edge.split("-")
        if not name_a or not name_b:
            raise ParseError(line_no, f"connection missing endpoint name in {edge!r}")
        if name_a == name_b:
            raise ParseError(line_no, "connection endpoints must differ")
        if not graph.has_zone(name_a):
            raise ParseError(line_no, f"connection references undefined zone {name_a!r}")
        if not graph.has_zone(name_b):
            raise ParseError(line_no, f"connection references undefined zone {name_b!r}")

        metadata = self._parse_metadata(inside, _CONNECTION_METADATA_KEYS, line_no)
        max_link_capacity = 1
        if "max_link_capacity" in metadata:
            max_link_capacity = self._parse_positive_int(
                metadata["max_link_capacity"], "max_link_capacity", line_no
            )

        return Connection(
            a=graph.zone(name_a),
            b=graph.zone(name_b),
            max_link_capacity=max_link_capacity,
        )

    # -------------------------------------------------------------- primitives

    def _split_metadata(self, payload: str, line_no: int) -> tuple[str, str]:
        """Return ``(inside, before)`` where ``[inside]`` is the trailing block."""
        has_open = "[" in payload
        has_close = "]" in payload
        if not has_open and not has_close:
            return "", payload
        if payload.count("[") != 1 or payload.count("]") != 1:
            raise ParseError(line_no, f"malformed metadata brackets in {payload!r}")
        match = _METADATA_RE.match(payload)
        if match is None:
            raise ParseError(line_no, f"malformed metadata block in {payload!r}")
        return match.group("inside"), match.group("before")

    def _parse_metadata(
        self, inside: str, allowed_keys: set[str], line_no: int
    ) -> dict[str, str]:
        if not inside.strip():
            return {}
        result: dict[str, str] = {}
        for token in inside.split():
            if "=" not in token:
                raise ParseError(
                    line_no, f"metadata token must be key=value, got {token!r}"
                )
            key, _, value = token.partition("=")
            key = key.strip()
            value = value.strip()
            if not key or not value:
                raise ParseError(
                    line_no, f"metadata token missing key or value: {token!r}"
                )
            if key not in allowed_keys:
                raise ParseError(line_no, f"unknown metadata key {key!r}")
            if key in result:
                raise ParseError(line_no, f"duplicate metadata key {key!r}")
            result[key] = value
        return result

    def _parse_positive_int(self, value: str, name: str, line_no: int) -> int:
        try:
            n = int(value)
        except ValueError:
            raise ParseError(line_no, f"{name} must be an integer, got {value!r}")
        if n <= 0:
            raise ParseError(line_no, f"{name} must be positive, got {n}")
        return n

    def _validate_zone_name(self, name: str, line_no: int) -> None:
        if not name:
            raise ParseError(line_no, "zone name is empty")
        if _NAME_INVALID.search(name):
            raise ParseError(
                line_no,
                f"zone name {name!r} must not contain whitespace or dashes",
            )

    def _register_zone(self, zone: Zone, seen: set[str], line_no: int) -> None:
        if zone.name in seen:
            raise ParseError(line_no, f"duplicate zone name {zone.name!r}")
        seen.add(zone.name)

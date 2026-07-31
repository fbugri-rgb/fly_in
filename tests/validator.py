"""Independent validator for scheduler output.

Not part of the shipped package — this module lives under ``tests/`` and
exists solely so the tests can double-check the scheduler's output
against the raw SPEC rules, without reusing the scheduler's own logic.
"""

from __future__ import annotations

from fly_in.graph import Graph
from fly_in.scheduler import Loc, MidConnLoc, Move, ZoneLoc
from fly_in.zone import ZoneType


class ValidationError(Exception):
    """Raised when a scheduler output violates SPEC rules."""


def validate(
    graph: Graph, nb_drones: int, plan: list[list[Move]]
) -> None:
    """Verify a plan is legal. Raises :class:`ValidationError` on any breach."""
    # Position of every drone at the start of turn 1 = start_hub.
    positions: dict[int, Loc] = {
        i + 1: ZoneLoc(graph.start.name) for i in range(nb_drones)
    }

    # Link capacities keyed on connection identity.
    link_cap: dict[frozenset[str], int] = {
        conn.key(): conn.max_link_capacity for conn in graph.connections
    }
    edges: dict[frozenset[str], tuple[str, str]] = {
        conn.key(): (conn.a.name, conn.b.name) for conn in graph.connections
    }

    for turn_idx, moves in enumerate(plan, start=1):
        # Compute new positions after this turn.
        new_positions: dict[int, Loc] = dict(positions)
        seen_drones: set[int] = set()
        edge_uses: dict[frozenset[str], int] = {}

        for move in moves:
            drone_id = move.drone.id
            if drone_id in seen_drones:
                raise ValidationError(
                    f"turn {turn_idx}: drone D{drone_id} appears twice"
                )
            seen_drones.add(drone_id)

            label = move.location_label
            new_loc = _parse_label(label, graph, edges)
            prev_loc = positions.get(drone_id)
            if prev_loc is None:
                raise ValidationError(
                    f"turn {turn_idx}: unknown drone D{drone_id}"
                )
            _check_move(
                turn_idx, drone_id, prev_loc, new_loc, graph, edges, edge_uses
            )
            new_positions[drone_id] = new_loc

        # Check link capacities for this turn.
        for key, count in edge_uses.items():
            cap = link_cap[key]
            if count > cap:
                raise ValidationError(
                    f"turn {turn_idx}: link {edges[key]} used {count} > cap {cap}"
                )

        # Check zone capacities on the end-of-turn snapshot.
        zone_counts: dict[str, int] = {}
        for loc in new_positions.values():
            if isinstance(loc, ZoneLoc):
                zone_counts[loc.zone] = zone_counts.get(loc.zone, 0) + 1
        for name, count in zone_counts.items():
            zone = graph.zone(name)
            if count > zone.capacity:
                raise ValidationError(
                    f"turn {turn_idx}: zone {name} holds {count} > cap {zone.capacity}"
                )

        positions = new_positions

    # Every drone must be at end_hub.
    end_name = graph.end.name
    for drone_id, loc in positions.items():
        if not (isinstance(loc, ZoneLoc) and loc.zone == end_name):
            raise ValidationError(
                f"drone D{drone_id} not delivered — ended at {loc.label()}"
            )


def _parse_label(
    label: str,
    graph: Graph,
    edges: dict[frozenset[str], tuple[str, str]],
) -> Loc:
    """Interpret ``D<ID>-<label>`` payload as a zone or midconn location."""
    if "-" in label:
        source, target = label.split("-", 1)
        key = frozenset({source, target})
        if key not in edges:
            raise ValidationError(f"label {label!r} does not match any connection")
        return MidConnLoc(source=source, target=target)
    if not graph.has_zone(label):
        raise ValidationError(f"label {label!r} is not a known zone")
    return ZoneLoc(label)


def _check_move(
    turn: int,
    drone_id: int,
    prev: Loc,
    cur: Loc,
    graph: Graph,
    edges: dict[frozenset[str], tuple[str, str]],
    edge_uses: dict[frozenset[str], int],
) -> None:
    """Verify a single drone's transition and record edge usage."""
    if isinstance(prev, ZoneLoc) and isinstance(cur, ZoneLoc):
        if prev.zone == cur.zone:
            raise ValidationError(
                f"turn {turn}: D{drone_id} emitted a no-op move"
            )
        key = frozenset({prev.zone, cur.zone})
        if key not in edges:
            raise ValidationError(
                f"turn {turn}: D{drone_id} has no connection {prev.zone}-{cur.zone}"
            )
        target_zone = graph.zone(cur.zone)
        if not target_zone.is_accessible:
            raise ValidationError(
                f"turn {turn}: D{drone_id} tried to enter blocked zone {cur.zone}"
            )
        if target_zone.zone_type is ZoneType.RESTRICTED:
            raise ValidationError(
                f"turn {turn}: D{drone_id} moved to restricted zone {cur.zone} "
                "in one turn (must go via mid-connection)"
            )
        edge_uses[key] = edge_uses.get(key, 0) + 1
    elif isinstance(prev, ZoneLoc) and isinstance(cur, MidConnLoc):
        if cur.source != prev.zone:
            raise ValidationError(
                f"turn {turn}: D{drone_id} entered midconn from wrong source"
            )
        key = cur.edge_key
        if key not in edges:
            raise ValidationError(
                f"turn {turn}: D{drone_id} used non-existent connection {cur.label()}"
            )
        target_zone = graph.zone(cur.target)
        if target_zone.zone_type is not ZoneType.RESTRICTED:
            raise ValidationError(
                f"turn {turn}: D{drone_id} mid-transit to {cur.target}, "
                "which is not a restricted zone"
            )
        edge_uses[key] = edge_uses.get(key, 0) + 1
    elif isinstance(prev, MidConnLoc) and isinstance(cur, ZoneLoc):
        if cur.zone != prev.target:
            raise ValidationError(
                f"turn {turn}: D{drone_id} landed at {cur.zone} but was mid-transit "
                f"toward {prev.target}"
            )
        edge_uses[prev.edge_key] = edge_uses.get(prev.edge_key, 0) + 1
    else:
        raise ValidationError(
            f"turn {turn}: D{drone_id} invalid transition "
            f"{prev.label()} -> {cur.label()}"
        )

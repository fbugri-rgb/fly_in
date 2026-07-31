"""Smoke tests: the skeleton imports and basic invariants hold."""

from __future__ import annotations

from fly_in import Connection, Graph, Zone, ZoneType
from fly_in.zone import UNLIMITED_CAPACITY


def test_zone_defaults() -> None:
    z: Zone = Zone(name="a", x=0, y=0)
    assert z.zone_type is ZoneType.NORMAL
    assert z.movement_cost == 1
    assert z.is_accessible
    assert z.capacity == 1


def test_restricted_zone_cost() -> None:
    z: Zone = Zone(name="r", x=0, y=0, zone_type=ZoneType.RESTRICTED)
    assert z.movement_cost == 2


def test_start_hub_unlimited_capacity() -> None:
    z: Zone = Zone(name="s", x=0, y=0, is_start=True, max_drones=1)
    assert z.capacity == UNLIMITED_CAPACITY


def test_connection_other_endpoint() -> None:
    a: Zone = Zone(name="a", x=0, y=0)
    b: Zone = Zone(name="b", x=1, y=0)
    c: Connection = Connection(a=a, b=b)
    assert c.other(a) is b
    assert c.other(b) is a
    assert c.key() == frozenset({"a", "b"})


def test_graph_start_end() -> None:
    g: Graph = Graph()
    s: Zone = Zone(name="s", x=0, y=0, is_start=True)
    e: Zone = Zone(name="e", x=1, y=0, is_end=True)
    g.add_zone(s)
    g.add_zone(e)
    g.add_connection(Connection(a=s, b=e))
    assert g.start is s
    assert g.end is e
    assert len(g.neighbors(s)) == 1

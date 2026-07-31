"""PathFinder tests: cost model, priority tiebreak, k-paths, edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from fly_in.connection import Connection
from fly_in.exceptions import NoSolutionError
from fly_in.graph import Graph
from fly_in.parser import Parser
from fly_in.pathfinder import PathFinder
from fly_in.zone import Zone, ZoneType

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


def _mkgraph(zones: list[Zone], edges: list[tuple[str, str]]) -> Graph:
    g = Graph()
    for z in zones:
        g.add_zone(z)
    for a, b in edges:
        g.add_connection(Connection(a=g.zone(a), b=g.zone(b)))
    return g


def test_linear_path() -> None:
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("a", 1, 0),
        Zone("b", 2, 0),
        Zone("e", 3, 0, is_end=True),
    ]
    g = _mkgraph(zones, [("s", "a"), ("a", "b"), ("b", "e")])
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert [z.name for z in path] == ["s", "a", "b", "e"]


def test_fork_shortest_side_wins() -> None:
    # Short: s -> a -> e (2 hops). Long: s -> b -> c -> e (3 hops).
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("a", 1, 0),
        Zone("b", 1, 1),
        Zone("c", 2, 1),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones, [("s", "a"), ("a", "e"), ("s", "b"), ("b", "c"), ("c", "e")]
    )
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert [z.name for z in path] == ["s", "a", "e"]


def test_priority_wins_tie() -> None:
    # Two paths of equal length; the one via a priority zone is preferred.
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("normal_mid", 1, 0),
        Zone("prio_mid", 1, 1, zone_type=ZoneType.PRIORITY),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones,
        [("s", "normal_mid"), ("normal_mid", "e"), ("s", "prio_mid"), ("prio_mid", "e")],
    )
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert "prio_mid" in {z.name for z in path}


def test_priority_does_not_override_shorter_path() -> None:
    # Short (2 hops, normal) vs long (3 hops, all priority). Shorter still wins.
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("normal_mid", 1, 0),
        Zone("p1", 1, 1, zone_type=ZoneType.PRIORITY),
        Zone("p2", 2, 1, zone_type=ZoneType.PRIORITY),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones,
        [
            ("s", "normal_mid"),
            ("normal_mid", "e"),
            ("s", "p1"),
            ("p1", "p2"),
            ("p2", "e"),
        ],
    )
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert [z.name for z in path] == ["s", "normal_mid", "e"]


def test_restricted_zone_costs_two() -> None:
    # Direct through a restricted zone: 2 turn cost.
    # Alternative via two normal zones: 2 turn cost too. Tie should
    # resolve to whichever Dijkstra finds first; the important assertion
    # is that turn count matches expectation.
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("r", 1, 0, zone_type=ZoneType.RESTRICTED),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(zones, [("s", "r"), ("r", "e")])
    pf = PathFinder(g)
    path = pf.shortest_path(g.start, g.end)
    assert pf.path_turn_count(path) == 3  # r=2, e=1


def test_shortcut_beats_restricted_detour() -> None:
    # Normal 2-hop path (cost 2) is strictly cheaper than a restricted 2-hop
    # path (cost 3). Pathfinder must prefer the normal route.
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("n", 1, 0),
        Zone("r", 1, 1, zone_type=ZoneType.RESTRICTED),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones,
        [("s", "n"), ("n", "e"), ("s", "r"), ("r", "e")],
    )
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert [z.name for z in path] == ["s", "n", "e"]


def test_blocked_zone_skipped() -> None:
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("wall", 1, 0, zone_type=ZoneType.BLOCKED),
        Zone("open", 1, 1),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones, [("s", "wall"), ("wall", "e"), ("s", "open"), ("open", "e")]
    )
    path = PathFinder(g).shortest_path(g.start, g.end)
    assert "wall" not in {z.name for z in path}


def test_disconnected_graph_raises() -> None:
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("island", 5, 5),
        Zone("e", 10, 10, is_end=True),
    ]
    g = _mkgraph(zones, [("s", "island")])
    with pytest.raises(NoSolutionError):
        PathFinder(g).shortest_path(g.start, g.end)


def test_k_shortest_paths_returns_alternatives() -> None:
    # Two parallel paths of the same length — k=2 must return both.
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("upper", 1, 1),
        Zone("lower", 1, -1),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(
        zones,
        [("s", "upper"), ("upper", "e"), ("s", "lower"), ("lower", "e")],
    )
    paths = PathFinder(g).k_shortest_paths(g.start, g.end, k=2)
    assert len(paths) == 2
    used_middles = {path[1].name for path in paths}
    assert used_middles == {"upper", "lower"}


def test_k_shortest_paths_stops_when_exhausted() -> None:
    # Only one path exists; requesting k=3 returns just [that_path].
    zones = [
        Zone("s", 0, 0, is_start=True),
        Zone("mid", 1, 0),
        Zone("e", 2, 0, is_end=True),
    ]
    g = _mkgraph(zones, [("s", "mid"), ("mid", "e")])
    paths = PathFinder(g).k_shortest_paths(g.start, g.end, k=3)
    assert len(paths) == 1


def test_shortest_path_on_easy_linear_map() -> None:
    graph, _ = Parser().parse(str(MAPS_DIR / "easy" / "01_linear_path.txt"))
    path = PathFinder(graph).shortest_path(graph.start, graph.end)
    assert [z.name for z in path] == ["start", "waypoint1", "waypoint2", "goal"]


def test_shortest_path_prefers_fast_lane_on_priority_puzzle() -> None:
    graph, _ = Parser().parse(str(MAPS_DIR / "medium" / "03_priority_puzzle.txt"))
    path = PathFinder(graph).shortest_path(graph.start, graph.end)
    names = [z.name for z in path]
    # The fast lane goes via the two priority zones + merge_point.
    assert "fast_junction" in names
    assert "fast_path" in names
    assert "slow_path1" not in names

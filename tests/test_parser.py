"""Parser tests: valid maps + malformed inputs. See SPEC.md §2."""

from __future__ import annotations

from pathlib import Path

import pytest

from fly_in.exceptions import ParseError
from fly_in.parser import Parser
from fly_in.zone import ZoneType

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


def _write(tmp_path: Path, contents: str) -> str:
    p = tmp_path / "map.txt"
    p.write_text(contents, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------- happy paths


def test_parses_minimal_valid_map(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 2\n"
        "start_hub: s 0 0 [color=green]\n"
        "end_hub: e 1 0 [color=red]\n"
        "connection: s-e\n",
    )
    graph, nb = Parser().parse(path)
    assert nb == 2
    assert graph.start.name == "s"
    assert graph.end.name == "e"
    assert graph.start.color == "green"
    assert len(list(graph.connections)) == 1


def test_ignores_comments_and_blanks(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "# leading comment\n"
        "\n"
        "nb_drones: 1\n"
        "\n"
        "# another\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 1\n"
        "connection: s-e\n",
    )
    graph, nb = Parser().parse(path)
    assert nb == 1
    assert graph.start.color is None


def test_zone_metadata_all_fields(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "hub: r 1 1 [zone=restricted color=orange max_drones=3]\n"
        "end_hub: e 2 2\n"
        "connection: s-r\n"
        "connection: r-e\n",
    )
    graph, _ = Parser().parse(path)
    r = graph.zone("r")
    assert r.zone_type is ZoneType.RESTRICTED
    assert r.color == "orange"
    assert r.max_drones == 3
    assert r.movement_cost == 2


def test_connection_max_link_capacity(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 0\n"
        "connection: s-e [max_link_capacity=4]\n",
    )
    graph, _ = Parser().parse(path)
    conns = list(graph.connections)
    assert len(conns) == 1
    assert conns[0].max_link_capacity == 4


def test_max_drones_ignored_on_start_and_end(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 5\n"
        "start_hub: s 0 0 [max_drones=1]\n"
        "end_hub: e 1 0 [max_drones=2]\n"
        "connection: s-e\n",
    )
    graph, _ = Parser().parse(path)
    # start/end always report unlimited capacity regardless of tag.
    assert graph.start.capacity > 1000
    assert graph.end.capacity > 1000


@pytest.mark.parametrize(
    "relpath",
    [
        "easy/01_linear_path.txt",
        "easy/02_simple_fork.txt",
        "easy/03_basic_capacity.txt",
        "medium/01_dead_end_trap.txt",
        "medium/02_circular_loop.txt",
        "medium/03_priority_puzzle.txt",
        "hard/01_maze_nightmare.txt",
        "hard/02_capacity_hell.txt",
        "hard/03_ultimate_challenge.txt",
        "challenger/01_the_impossible_dream.txt",
    ],
)
def test_provided_maps_parse(relpath: str) -> None:
    """Every shipped map must parse without error."""
    path = MAPS_DIR / relpath
    graph, nb = Parser().parse(str(path))
    assert nb > 0
    assert graph.start is not None
    assert graph.end is not None


# ---------------------------------------------------------------- error paths


def test_missing_nb_drones(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "start_hub: s 0 0\nend_hub: e 1 0\nconnection: s-e\n",
    )
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "nb_drones" in exc.value.cause


def test_nb_drones_not_integer(tmp_path: Path) -> None:
    path = _write(tmp_path, "nb_drones: abc\n")
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert exc.value.line_no == 1


def test_nb_drones_zero(tmp_path: Path) -> None:
    path = _write(tmp_path, "nb_drones: 0\n")
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_missing_start_hub(tmp_path: Path) -> None:
    path = _write(tmp_path, "nb_drones: 1\nend_hub: e 1 0\n")
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "start_hub" in exc.value.cause


def test_missing_end_hub(tmp_path: Path) -> None:
    path = _write(tmp_path, "nb_drones: 1\nstart_hub: s 0 0\n")
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "end_hub" in exc.value.cause


def test_duplicate_start(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s1 0 0\n"
        "start_hub: s2 1 0\n"
        "end_hub: e 2 0\n"
        "connection: s1-e\n",
    )
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert exc.value.line_no == 3


def test_duplicate_connection_same_direction(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n"
        "connection: s-e\n",
    )
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "duplicate connection" in exc.value.cause


def test_duplicate_connection_reversed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n"
        "connection: e-s\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_connection_undefined_zone(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "end_hub: e 1 0\n"
        "connection: s-nope\n",
    )
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "undefined zone" in exc.value.cause


def test_unknown_zone_type(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0\n"
        "hub: m 1 0 [zone=weird]\n"
        "end_hub: e 2 0\n"
        "connection: s-m\n"
        "connection: m-e\n",
    )
    with pytest.raises(ParseError) as exc:
        Parser().parse(path)
    assert "zone type" in exc.value.cause


def test_unknown_metadata_key(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0 [weird=yes]\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_zone_name_with_dash_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\nstart_hub: bad-name 0 0\nend_hub: e 1 0\nconnection: bad-name-e\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_non_integer_coordinates(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\nstart_hub: s 0.5 0\nend_hub: e 1 0\nconnection: s-e\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_unknown_directive(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\nzone_of_death: x 0 0\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_zone_type_forbidden_on_start(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0 [zone=restricted]\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)


def test_malformed_metadata_brackets(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "nb_drones: 1\n"
        "start_hub: s 0 0 [color=green\n"
        "end_hub: e 1 0\n"
        "connection: s-e\n",
    )
    with pytest.raises(ParseError):
        Parser().parse(path)

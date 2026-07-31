*This project has been created as part of the 42 curriculum by fbugri.*

# Fly-In

A drone routing simulator. Given a graph of zones with capacity, priority,
and restricted-transit rules, move every drone from `start_hub` to `end_hub`
in as few simulation turns as possible without violating any occupancy or
connection-capacity constraint.

## Description

Each map is a text file describing a graph of **zones** (nodes) and
**connections** (bidirectional edges). Zones have per-turn drone
capacity and a type — `normal`, `priority` (soft-preferred), `restricted`
(2-turn transit), or `blocked` (inaccessible). Connections also carry a
per-turn traversal capacity.

The simulator parses the map, plans a conflict-free schedule for every
drone, and prints the sequence of moves one line per turn as required by
the SPEC.

## Instructions

Requires Python 3.10+ (checked with 3.10.12).

```
make install                  # install flake8 / mypy / pytest into your env
make run                      # run on maps/easy/01_linear_path.txt
make run MAP=maps/hard/02_capacity_hell.txt
make debug MAP=maps/…         # run under pdb
make lint                     # flake8 + mypy (project-required flags)
make lint-strict              # flake8 + mypy --strict
make test                     # pytest
make clean                    # remove caches
```

The main script also takes `--render` (or `-r`) for a colored per-turn
snapshot on stderr:

```
python main.py --render maps/medium/03_priority_puzzle.txt
```

The SPEC §6 move lines still go to stdout so a grader can pipe them
independently of the visualization.

## Algorithm choices and implementation strategy

**Parsing** is single-pass and strict: any malformed input raises
`ParseError(line_no, cause)` and stops the program with a clean message.
The parser tracks its own state (seen names, connection keys, presence
of start/end) rather than probing the `Graph`, which keeps error
messages precise and the graph object append-only.

**Single-drone pathfinding** is a standard Dijkstra written from scratch
(SPEC §5 forbids graph libraries). The cost model is:

- entering a normal zone costs 1000
- entering a priority zone costs 999 (a **soft** tiebreak — priority
  never beats a strictly shorter path, but wins among ties)
- entering a restricted zone costs 2000 (its 2-turn traversal)
- blocked zones are skipped

The 1000× scale is a headroom trick so priority discounts never
accumulate enough to overtake a whole extra hop. **k-shortest paths**
uses a simple iterative-penalty scheme: after each found path,
intermediate zones accrue a cost bump so the next Dijkstra pass is
biased toward alternative routes. Simpler than Yen's algorithm and easy
to justify aloud.

**Multi-drone scheduling** is **prioritized planning with a reservation
table**. Drones are planned one at a time via space-time BFS from
`(start, turn 0)` to any `(end, turn T)`. Each state is either a `ZoneLoc`
(drone rests at a zone) or a `MidConnLoc` (drone is on a connection
heading to a restricted zone — the mandatory 2-turn commitment from
SPEC §4). Successors are: wait, walk to a non-restricted neighbor, or
begin a restricted transit (only if both the mid-turn edge slot and the
arrival zone/edge are free — never enter a transit you cannot complete).

The reservation table is two dicts: `{(zone_name, turn): count}` and
`{(edge_key, turn): count}`. Zone capacity, connection capacity, and the
outflow-before-inflow rule fall out naturally from checking these counts
against `Zone.capacity` / `Connection.max_link_capacity` at the target
turn. After each drone's search, its schedule is committed to the table
so later drones plan around it.

Prioritized planning is **not complete** in general — some solvable
instances need a different ordering — but it is simple, fast, and passes
every shipped map (see the benchmark comparison in `tests/test_scheduler.py`).

Results on the shipped maps:

| Map | Target | Achieved |
|---|---|---|
| easy/01_linear_path | ≤ 6 | 4 |
| easy/02_simple_fork | ≤ 8 | 4 |
| easy/03_basic_capacity | ≤ 6 | 4 |
| medium/01_dead_end_trap | ≤ 12 | 8 |
| medium/02_circular_loop | ≤ 15 | 15 |
| medium/03_priority_puzzle | ≤ 12 | 7 |
| hard/01_maze_nightmare | ≤ 30 | 13 |
| hard/02_capacity_hell | ≤ 35 | 16 |
| hard/03_ultimate_challenge | ≤ 45 | 26 |
| challenger/01_the_impossible_dream | reference 45 | 43 |

## Visual representation

`--render` prints a per-turn snapshot to stderr. Each snapshot lists:

- the turn number and total turns
- how many drones have been delivered so far
- for each occupied zone: name (colored using its `color=` metadata),
  followed by the drone IDs currently there
- for each drone mid-transit toward a restricted zone: the connection
  label (`source-target`) and the drone IDs on it

ANSI foreground colors are used when stderr is a TTY. The color palette
covers `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `orange`,
`purple`, `gold`, `lime`, `brown`, `gray`, `pink` — unknown color names
render plain (per SPEC, color is "any single-word string").

## Example

Input (`maps/easy/02_simple_fork.txt`):

```
nb_drones: 4
start_hub: start 0 0 [color=green]
hub: junction 1 0 [color=yellow max_drones=2]
hub: path_a 2 1 [color=blue]
hub: path_b 2 -1 [color=blue]
end_hub: goal 3 0 [color=red]

connection: start-junction [max_link_capacity=2]
connection: junction-path_a
connection: junction-path_b
connection: path_a-goal
connection: path_b-goal
```

Expected output (one line per turn, SPEC §6):

```
D1-junction D2-junction
D1-path_a D2-path_b D3-junction D4-junction
D1-goal D2-goal D3-path_a D4-path_b
D3-goal D4-goal
```

Four turns to deliver all four drones through a capacity-2 chokepoint.

## Resources

- SPEC.md (in this repo) — consolidated subject and engineering rules.
- Dijkstra's shortest-path algorithm — CLRS §24.3.
- Prioritized planning for multi-agent path finding — Silver 2005,
  "Cooperative Pathfinding" (introductory reservation-table treatment).

### AI usage disclosure

This project was implemented with heavy use of **Claude Code (Anthropic)**
as a pair programmer. Concretely:

- **Design decisions were mine** (approach chosen: reservation-table
  scheduler over CBS; soft priority tiebreak via scaled integer costs;
  penalty-based k-shortest paths over Yen's algorithm).
- **Code was drafted by Claude and reviewed by me line-by-line** before
  landing. Areas that got the most independent verification: the parser
  grammar, the restricted-zone 2-turn commitment, and the reservation
  bookkeeping in `Scheduler._commit`.
- **Tests were largely AI-drafted from a list of edge cases I wanted
  covered**, then run and inspected. The independent validator in
  `tests/validator.py` was written specifically so tests don't just
  re-run the scheduler's own logic.
- **Documentation (docstrings and this README) was AI-assisted**.

Everything in the repo is code I understand and can defend live —
per 42 evaluation rules.

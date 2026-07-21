"""movement.py — THE core engine module.

Implements the **boustrophedon (serpentine) directed-grid traversal** described in
DESIGN.md §3 and validated against the ``example.md`` Level-1 trace.

Grid model
----------
``grid[r][c]`` with ``r`` a 0-indexed data row and ``c`` a 0-indexed column.
A cell **exists** iff ``grid[r][c] != "-"`` (the dash/null marker). Cell value
``"0"`` = empty standable; a positive-integer **string** = an item id.

Row direction (1-indexed rule-row ``Rn = r + 1``)
-------------------------------------------------
    Rn % 2 == 0  -> 'C' connector row  (rows 2, 4, 6, 8 ...)  -> DOWN ONLY
    Rn % 4 == 1  -> 'R' right          (rows 1, 5, 9 ...)     -> RIGHT or DOWN
    Rn % 4 == 3  -> 'L' left           (rows 3, 7, 11 ...)    -> LEFT or DOWN

This matches the data exactly: data row 0 (rule-row 1) = RIGHT, data row 1
(rule-row 2) = CONNECTOR, data row 2 (rule-row 3) = LEFT, data row 3
(rule-row 4) = CONNECTOR, data row 4 (rule-row 5) = RIGHT. See the worked
trace in the module doctest / ``test_movement.py``.

Directed edges (DAG — never up / never backward in-row)
-------------------------------------------------------
From an existing cell ``(r, c)`` the forward out-edges are:
  1. Horizontal step in the row's flow direction, IF that neighbour exists:
        'R' -> (r, c+1) ; 'L' -> (r, c-1) ; 'C' -> none.
  2. Vertical step DOWN to (r+1, c) IF it exists.
A cell may have 0, 1 or 2 out-edges. **Two** out-edges = a **branch**.

Dice / landing set
------------------
The dice result ``n`` = number of directed edges traversed (= cells advanced).
The starting cell is NOT counted. The landing set is the set of cells reachable
by *some* directed walk of exactly ``n`` edges:

    S_0 = { start }
    S_k = { v : exists u in S_{k-1} with an edge u -> v }

(Standard layered BFS; multiple branches may converge or diverge.) A cell can
belong to several S_k. The landing set for a roll ``n`` is ``S_n``.
  * |S_n| == 1 -> deterministic, auto-move.
  * |S_n|  > 1 -> variants, the player chooses.
  * |S_n| == 0 -> every walk hit the (unique) sink = exit -> CLAMP to exit
                  (level complete). See DESIGN.md §3.6.

Pickup semantics (DESIGN.md §3.6)
---------------------------------
Items are collected **only** on the cell the player actually LANDS on. Cells
merely passed through en route are NOT looted. (This is why the Level-1
late-descent walk passing the apple at data (4,2) at step 7 does NOT grant it —
the rigorous algorithm lands that variant on the EMPTY (4,3), not the apple.
See the documented one-cell slip in DESIGN.md §4.6.)

This module is PURE (no pygame, no I/O, fully unit-testable without a display).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

# A grid is the raw 2D list of strings from levels.json (LevelData.rows).
Grid = List[List[str]]
Cell = Tuple[int, int]

# Direction codes.
RIGHT = "R"
LEFT = "L"
CONNECTOR = "C"


# ---------------------------------------------------------------------------
# Core pure helpers
# ---------------------------------------------------------------------------
def row_direction(r: int) -> str:
    """Direction of data row ``r`` (0-indexed): 'R', 'L', or 'C' (connector).

    Uses the 1-indexed rule-row number ``Rn = r + 1``:
      Rn even      -> 'C' (connector / down-only)
      Rn % 4 == 1  -> 'R' (rows 1, 5, 9 ...)
      Rn % 4 == 3  -> 'L' (rows 3, 7, 11 ...)
    """
    rn = r + 1
    if rn % 2 == 0:
        return CONNECTOR
    return RIGHT if rn % 4 == 1 else LEFT


def exists(grid: Grid, r: int, c: int) -> bool:
    """True iff (r, c) is inside the grid AND holds a real cell (not the dash)."""
    return (
        0 <= r < len(grid)
        and 0 <= c < len(grid[r])
        and grid[r][c] != "-"
    )


def outgoing(grid: Grid, r: int, c: int) -> List[Cell]:
    """Forward out-edges from existing cell (r, c). Never up, never in-row back.

    Order: horizontal-flow neighbour first (if any), then the down neighbour.
    A list of length 0, 1, or 2.
    """
    res: List[Cell] = []
    d = row_direction(r)
    if d == RIGHT and exists(grid, r, c + 1):
        res.append((r, c + 1))
    elif d == LEFT and exists(grid, r, c - 1):
        res.append((r, c - 1))
    # CONNECTOR has no horizontal edge.
    if exists(grid, r + 1, c):  # DOWN is always allowed where a cell exists below.
        res.append((r + 1, c))
    return res


def landings(grid: Grid, start: Cell, n: int) -> Set[Cell]:
    """Set of cells reachable by EXACTLY ``n`` forward edges from ``start``.

    This is the ``S_n`` landing set for a dice roll of ``n``. Pure, deterministic,
    no randomness. If the frontier becomes empty before ``n`` steps (all walks hit
    the sink), returns the empty set (the caller clamps to the exit).
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    frontier: Set[Cell] = {start}
    for _ in range(n):
        nxt: Set[Cell] = set()
        for (r, c) in frontier:
            for v in outgoing(grid, r, c):
                nxt.add(v)
        if not nxt:  # all walks absorbed into the sink (exit) before n steps.
            break
        frontier = nxt
    return frontier


# ---------------------------------------------------------------------------
# Start / exit cells
# ---------------------------------------------------------------------------
def start_cell(grid: Grid) -> Cell:
    """The top-most, then left-most existing cell (player spawn). Usually (0, 0)."""
    for r in range(len(grid)):
        for c in range(len(grid[r])):
            if grid[r][c] != "-":
                return (r, c)
    raise ValueError("grid has no existing cell — cannot find start")


def exit_cell_of_grid(grid: Grid) -> Cell:
    """The bottom-most, then right-most existing cell (the level exit / sink)."""
    for r in range(len(grid) - 1, -1, -1):
        for c in range(len(grid[r]) - 1, -1, -1):
            if grid[r][c] != "-":
                return (r, c)
    raise ValueError("grid has no existing cell — cannot find exit")


# ---------------------------------------------------------------------------
# Graph wrapper (build once, query many times)
# ---------------------------------------------------------------------------
@dataclass
class Graph:
    """A directed acyclic grid-graph built from a level's rows.

    Attributes:
        grid: the raw 2D string grid.
        nodes: the set of all existing cells.
        adjacency: ``{cell: [forward neighbours]}``.
        start: player spawn cell.
        exit: the unique sink (level exit).
    """

    grid: Grid
    nodes: Set[Cell] = field(default_factory=set)
    adjacency: Dict[Cell, List[Cell]] = field(default_factory=dict)
    start: Cell = (0, 0)
    exit: Cell = (0, 0)

    # ---- queries ---------------------------------------------------------
    def outgoing(self, cell: Cell) -> List[Cell]:
        return self.adjacency.get(cell, [])

    def is_branch(self, cell: Cell) -> bool:
        """True iff this cell has 2 out-edges (continue-horizontal AND descend)."""
        return len(self.adjacency.get(cell, [])) == 2

    def reachable(self, start: Cell, n: int) -> Set[Cell]:
        """Landing set ``S_n`` from ``start``. Delegates to the pure ``landings``.

        Equivalent to ``landings(self.grid, start, n)`` but reads clearer at
        call sites and lets a future caching layer memoise per-graph.
        """
        return landings(self.grid, start, n)

    def branch_cells(self) -> List[Cell]:
        """All branch sources (2 out-edges) — useful for debugging / highlights."""
        return [c for c in self.nodes if self.is_branch(c)]


def build_graph(level) -> Graph:
    """Build the directed DAG for a level.

    ``level`` is anything exposing a ``rows`` attribute (e.g. ``LevelData`` or a
    plain dict with a ``rows`` key wrapped to expose ``.rows``). Returns a
    :class:`Graph` with precomputed adjacency, start and exit.
    """
    grid: Grid = level.rows
    nodes: Set[Cell] = set()
    adjacency: Dict[Cell, List[Cell]] = {}
    for r in range(len(grid)):
        for c in range(len(grid[r])):
            if grid[r][c] != "-":
                cell = (r, c)
                nodes.add(cell)
                adjacency[cell] = outgoing(grid, r, c)
    return Graph(
        grid=grid,
        nodes=nodes,
        adjacency=adjacency,
        start=start_cell(grid),
        exit=exit_cell_of_grid(grid),
    )


def exit_cell(level) -> Cell:
    """Convenience: the exit (bottom-right existing cell) for a level."""
    return exit_cell_of_grid(level.rows)


def start(level) -> Cell:
    """Convenience: the start (top-left existing cell) for a level."""
    return start_cell(level.rows)

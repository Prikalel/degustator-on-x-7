"""levels_data.py — load ``levels.json`` into typed level objects.

EXACT schema read from ``levels.json`` (top level = JSON array of level objects):

    {
        "name_ru":           str,                # Russian display name
        "name_en":           str,                # English display name
        "rows":              [[str, ...], ...],  # the grid
        "moves":             [ {max_value:int, power:int}, ... ],
        "start_parameters":  {power:int, hunger:int},
        "shop_after_level":  [ {item_id:int, shop_cost:int}, ... ]   # may be []
    }

Cell value conventions (confirmed from the real data + DESIGN.md §1.3):
    "0"            -> empty standable cell
    "-"  (dash)    -> NO cell / no passage (the "dash/null marker")
    "<positive int as str>" -> an item id from items.json placed on that cell

Every level's grid is a rectangle (all rows the same length in the data).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

import config

# Dash / null marker meaning "no cell here".
NO_CELL = "-"


@dataclass(frozen=True)
class Move:
    """One movement option.

    ``max_value`` = number of faces on the die (roll is in 1..max_value);
    ``power``     = power cost paid to choose this option for a turn.
    """

    max_value: int
    power: int

    def to_dict(self) -> dict:
        return {"max_value": self.max_value, "power": self.power}


@dataclass(frozen=True)
class StartParameters:
    """Power/hunger reset values applied at the START of a level.

    Coins are deliberately NOT here: only coins persist between levels.
    """

    power: int
    hunger: int

    def to_dict(self) -> dict:
        return {"power": self.power, "hunger": self.hunger}


@dataclass(frozen=True)
class ShopOffer:
    """One shop offering shown after clearing a level.

    ``item_id``   = which item (id into items.json) is for sale;
    ``shop_cost`` = the BUY price in coins (may differ from the item's
                    auto-sell ``coins`` value).
    """

    item_id: int
    shop_cost: int

    def to_dict(self) -> dict:
        return {"item_id": self.item_id, "shop_cost": self.shop_cost}


@dataclass
class LevelData:
    """A fully parsed level (raw schema + typed helpers)."""

    name_ru: str
    name_en: str
    rows: List[List[str]]
    moves: List[Move] = field(default_factory=list)
    start_parameters: StartParameters = field(
        default_factory=lambda: StartParameters(0, 0)
    )
    shop_after_level: List[ShopOffer] = field(default_factory=list)

    # ---- accessors -------------------------------------------------------
    @property
    def name(self) -> str:
        return self.name_en

    def display_name(self, lang: str = "en") -> str:
        return self.name_ru if lang == "ru" else self.name_en

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        # All rows same length in the data; use the first row's length.
        return len(self.rows[0]) if self.rows else 0

    def cell_exists(self, r: int, c: int) -> bool:
        """True iff grid position (r, c) holds a real cell (not the dash marker)."""
        return (
            0 <= r < len(self.rows)
            and 0 <= c < len(self.rows[r])
            and self.rows[r][c] != NO_CELL
        )

    def item_id_at(self, r: int, c: int) -> Optional[int]:
        """The item id placed at (r, c), or None if empty / no cell."""
        if not self.cell_exists(r, c):
            return None
        val = self.rows[r][c]
        if val == "0":
            return None
        return int(val)

    def start_parameters_dict(self) -> dict:
        return self.start_parameters.to_dict()

    def to_dict(self) -> dict:
        return {
            "name_ru": self.name_ru,
            "name_en": self.name_en,
            "rows": [list(row) for row in self.rows],
            "moves": [m.to_dict() for m in self.moves],
            "start_parameters": self.start_parameters.to_dict(),
            "shop_after_level": [o.to_dict() for o in self.shop_after_level],
        }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _parse_level(raw: dict) -> LevelData:
    for key in ("name_ru", "name_en", "rows", "moves", "start_parameters", "shop_after_level"):
        if key not in raw:
            raise ValueError(f"level object missing key {key!r}: {raw!r}")

    rows = [list(row) for row in raw["rows"]]
    if not rows:
        raise ValueError("level has empty rows")
    width = len(rows[0])
    for i, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(
                f"level {raw.get('name_en')!r} row {i} width {len(row)} != {width}"
            )

    moves = [Move(int(m["max_value"]), int(m["power"])) for m in raw["moves"]]
    sp = raw["start_parameters"]
    start_parameters = StartParameters(int(sp["power"]), int(sp["hunger"]))
    shop = [
        ShopOffer(int(o["item_id"]), int(o["shop_cost"]))
        for o in raw["shop_after_level"]
    ]

    return LevelData(
        name_ru=str(raw["name_ru"]),
        name_en=str(raw["name_en"]),
        rows=rows,
        moves=moves,
        start_parameters=start_parameters,
        shop_after_level=shop,
    )


def load_levels(path: str = config.LEVELS_PATH) -> List[LevelData]:
    """Load ``levels.json`` into a list of :class:`LevelData` (index = level order)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("levels.json top level must be a JSON array of level objects")
    return [_parse_level(level) for level in data]


# ---------------------------------------------------------------------------
# Module-level cache (load once, reuse).
# ---------------------------------------------------------------------------
_cache: Optional[List[LevelData]] = None


def get_levels() -> List[LevelData]:
    """Return the cached list of levels, loading on first call."""
    global _cache
    if _cache is None:
        _cache = load_levels()
    return _cache


def get_level(index: int) -> LevelData:
    """Return the level at ``index`` (0-based)."""
    levels = get_levels()
    if not (0 <= index < len(levels)):
        raise IndexError(f"level index {index} out of range (0..{len(levels) - 1})")
    return levels[index]


def num_levels() -> int:
    return len(get_levels())

"""levels_data.py — typed loaders for levels and the COMPANIES that group them.

The active data model is **companies**: one ``companies/<n>.json`` file per
campaign (see :class:`CompanyData` / :func:`load_companies` below). Each company
contains a list of level objects with this schema:

EXACT schema for a level object (the same one the legacy ``levels.json`` used):

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
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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


# ===========================================================================
# COMPANIES
# ===========================================================================
# A "company" is a self-contained campaign: a named set of levels the player
# picks from the company-select screen. Each company is ONE JSON file inside
# ``companies/`` whose filename stem is an integer = the company number / order:
#
#     companies/1.json   -> company number 1
#     companies/2.json   -> company number 2
#     ...
#
# Each company file schema:
#
#     {
#         "name_ru":  str,                # Russian company display name
#         "name_en":  str,                # English company display name
#         "levels":   [ <level object>, ... ]   # same schema as levels.json entries
#     }
@dataclass
class CompanyData:
    """A named campaign made of an ordered list of :class:`LevelData`."""

    number: int                  # company number (from the filename stem)
    name_ru: str
    name_en: str
    levels: List[LevelData] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.name_en

    def display_name(self, lang: str = "en") -> str:
        return self.name_ru if lang == "ru" else self.name_en

    @property
    def num_levels(self) -> int:
        return len(self.levels)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name_ru": self.name_ru,
            "name_en": self.name_en,
            "levels": [lvl.to_dict() for lvl in self.levels],
        }


def _company_number_from_name(filename: str) -> Optional[int]:
    """``"3.json"`` -> ``3``; non-integer stems -> ``None`` (skipped)."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    try:
        return int(stem)
    except ValueError:
        return None


def list_company_files(directory: str = config.COMPANIES_DIR) -> List[Tuple[int, str]]:
    """Return ``[(number, path), ...]`` for every ``<int>.json`` in ``directory``,
    sorted ascending by number. Returns ``[]`` if the directory is absent."""
    if not os.path.isdir(directory):
        return []
    out: List[Tuple[int, str]] = []
    for fname in os.listdir(directory):
        if not fname.endswith(".json"):
            continue
        num = _company_number_from_name(fname)
        if num is None:
            continue
        out.append((num, os.path.join(directory, fname)))
    out.sort(key=lambda pair: pair[0])
    return out


def _parse_company(path: str, number: int) -> CompanyData:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"company file {path!r} must be a JSON object")
    for key in ("name_ru", "name_en", "levels"):
        if key not in raw:
            raise ValueError(f"company file {path!r} missing key {key!r}")
    raw_levels = raw["levels"]
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ValueError(f"company file {path!r} must have a non-empty 'levels' array")
    levels = [_parse_level(lvl) for lvl in raw_levels]
    return CompanyData(
        number=number,
        name_ru=str(raw["name_ru"]),
        name_en=str(raw["name_en"]),
        levels=levels,
    )


def load_companies(directory: str = config.COMPANIES_DIR) -> List[CompanyData]:
    """Load every ``companies/<n>.json`` into a list sorted by company number."""
    files = list_company_files(directory)
    if not files:
        raise FileNotFoundError(
            f"no company files (<int>.json) found in {directory!r}"
        )
    return [_parse_company(path, num) for num, path in files]


# Module-level cache (load once, reuse).
_companies_cache: Optional[List[CompanyData]] = None


def get_companies() -> List[CompanyData]:
    """Return the cached list of companies, loading on first call."""
    global _companies_cache
    if _companies_cache is None:
        _companies_cache = load_companies()
    return _companies_cache


def get_company(number: int) -> CompanyData:
    """Return the company whose ``number`` matches, or raise ``KeyError``."""
    for c in get_companies():
        if c.number == number:
            return c
    raise KeyError(f"company number {number} not found")


def num_companies() -> int:
    return len(get_companies())

"""items.py — load ``items.json`` into typed :class:`Item` objects.

EXACT schema read from ``items.json`` (top level = JSON array of objects):

    {
        "id":       int,    # referenced by levels.json cell values & shop_after_level.item_id
        "name_ru":  str,    # Russian display name
        "name_en":  str,    # English display name
        "icon":     str,    # emoji glyph (decorative metadata; pygame/Pygbag render unreliably)
        "power":    int,    # power delta applied when EATEN  (all current values >= 0)
        "hunger":   int,    # hunger delta applied when EATEN
        "coins":    int     # AUTO-SELL value at level end (the "value" of the item)
    }

NOTE ON "buy price": items.json has **no** buy/shop price field. The shop *buy*
price lives in ``levels.json`` -> ``shop_after_level[].shop_cost`` (per-level,
per-offering). So :class:`Item` only carries the auto-sell ``coins`` value; the
buy price is attached to a shop offer, not to the item itself.

All items (exact, from the real file):
    id | name_en      | power | hunger | coins (sell)
    ----|--------------|------:|-------:|------------:
     1  | banana       |   1   |   1    |   1
     2  | apple        |   2   |   1    |   2
     3  | shrimp       |   2   |   0    |   2
     4  | hamburger    |   2   |   0    |   2
     5  | golden fish  |   0   |   0    |   4
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional

import config


# The set of keys we require in each item object (matches items.json exactly).
REQUIRED_KEYS = ("id", "name_ru", "name_en", "icon", "power", "hunger", "coins")


@dataclass(frozen=True)
class Item:
    """An immutable, hashable item (hashable so it can live in sets if needed)."""

    id: int
    name_ru: str
    name_en: str
    icon: str          # emoji metadata only; render name_en/name_ru instead
    power: int         # power delta applied when EATEN
    hunger: int        # hunger delta applied when EATEN
    coins: int         # auto-sell value at level end (NOT the shop buy price)

    # ---- display helpers -------------------------------------------------
    @property
    def name(self) -> str:
        """English name (default display language)."""
        return self.name_en

    def display_name(self, lang: str = "en") -> str:
        """Name for the given locale code (``en`` / ``ru``)."""
        return self.name_ru if lang == "ru" else self.name_en

    def summary(self) -> str:
        """Compact one-line stat summary used by inventory rows / tests."""
        return f"{self.name_en} (id={self.id}) P{self.power:+d} H{self.hunger:+d} sell={self.coins}"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _parse(raw: dict) -> Item:
    missing = [k for k in REQUIRED_KEYS if k not in raw]
    if missing:
        raise ValueError(f"items.json object missing keys {missing}: {raw!r}")
    return Item(
        id=int(raw["id"]),
        name_ru=str(raw["name_ru"]),
        name_en=str(raw["name_en"]),
        icon=str(raw["icon"]),
        power=int(raw["power"]),
        hunger=int(raw["hunger"]),
        coins=int(raw["coins"]),
    )


def load_items(path: str = config.ITEMS_PATH) -> Dict[int, Item]:
    """Load ``items.json`` into a ``{id: Item}`` mapping (lookup by id).

    ``path`` is relative to the project root / working dir, so this works on
    desktop and inside a Pygbag bundle.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("items.json top level must be a JSON array of item objects")
    items: Dict[int, Item] = {}
    for raw in data:
        item = _parse(raw)
        if item.id in items:
            raise ValueError(f"duplicate item id {item.id} in items.json")
        items[item.id] = item
    return items


def load_items_list(path: str = config.ITEMS_PATH) -> List[Item]:
    """Same load, but returned as a list ordered by id (handy for tests/debug)."""
    return [items for _, items in sorted(load_items(path).items())]


# ---------------------------------------------------------------------------
# Convenience: a module-level cache so callers can use ``get_item`` / ``items``
# without re-reading the file each time. Lazily populated on first access.
# ---------------------------------------------------------------------------
_cache: Optional[Dict[int, Item]] = None


def get_items() -> Dict[int, Item]:
    """Return the cached ``{id: Item}`` mapping, loading on first call."""
    global _cache
    if _cache is None:
        _cache = load_items()
    return _cache


def get_item(item_id: int) -> Item:
    """Lookup a single item by id (loads the file once, cached afterwards)."""
    return get_items()[int(item_id)]


def sell_value(item_ids: Iterable[int]) -> int:
    """Sum of auto-sell ``coins`` values for a collection of item ids."""
    table = get_items()
    return sum(table[int(i)].coins for i in item_ids)

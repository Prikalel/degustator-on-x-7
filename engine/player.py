"""player.py — Player state + the few pure mutations on it.

The player has three scalar parameters and an infinite-size inventory of item
references:

    power     : stamina, spent on moves (paid per chosen move option), restored by eating.
    hunger    : spent EXACTLY 1 per move, restored by eating.
    coins     : spent in the shop, earned by auto-selling the inventory at level end.
    inventory : list of :class:`items.Item` (looted on the LANDING cell; cleared at level end).

Persistence rule (DESIGN.md §1.1 / §5.3): **only ``coins`` persist between
levels.** ``power`` / ``hunger`` are reset to the level's ``start_parameters``
at the start of each level; the inventory is sold then refilled only from shop
purchases.

Death rule (instruction.md, DESIGN.md §3.6): game over if ``power < 0`` OR
``hunger < 0`` after a move. (Because a move option is only selectable while
``power >= cost``, power won't dip negative from a move; the binding failure
modes are hunger dropping below 0 and being unable to afford any option.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Union

from items import Item


@dataclass
class Player:
    """Mutable player state for the current run."""

    power: int = 0
    hunger: int = 0
    coins: int = 0
    inventory: List[Item] = field(default_factory=list)

    # ---- inventory helpers ----------------------------------------------
    def add_item(self, item: Item) -> None:
        """Loot an item into the (infinite-size) inventory."""
        self.inventory.append(item)

    def has(self, item: Item) -> bool:
        return item in self.inventory

    # ---- eating ----------------------------------------------------------
    def eat(self, item: Item) -> None:
        """Eat an inventory item: apply its power/hunger deltas, remove it.

        Raises ``ValueError`` if the item is not in the inventory.
        """
        if item not in self.inventory:
            raise ValueError(f"cannot eat {item!r}: not in inventory")
        self.power += item.power
        self.hunger += item.hunger
        self.inventory.remove(item)

    def eat_index(self, index: int) -> Item:
        """Eat the item at ``index`` in the inventory; return the eaten item."""
        item = self.inventory[index]
        self.eat(item)
        return item

    # ---- moving ----------------------------------------------------------
    def apply_move(self, move) -> None:
        """Pay the cost of a move: ``power -= move.power`` and ``hunger -= 1``.

        ``move`` is duck-typed: anything with a ``.power`` attribute (e.g.
        :class:`levels_data.Move`). The caller must gate selection on
        ``can_afford(move)``; this method does the deduction unconditionally.
        """
        self.power -= int(move.power)
        self.hunger -= 1

    def can_afford(self, move) -> bool:
        """True iff the player currently has enough power to choose ``move``."""
        return self.power >= int(move.power)

    def can_afford_any(self, moves) -> bool:
        """True iff at least one move option is currently affordable.

        If False and the player hasn't reached the exit, they are STUCK -> game over.
        """
        return any(self.can_afford(m) for m in moves)

    # ---- death -----------------------------------------------------------
    def is_dead(self) -> bool:
        """Game-over condition: power < 0 OR hunger < 0."""
        return self.power < 0 or self.hunger < 0

    # ---- level end: auto-sell -------------------------------------------
    def auto_sell(self, items_lookup: Optional[Union[dict, Callable[[int], int]]] = None) -> int:
        """Auto-sell the ENTIRE inventory at each item's ``coins`` value.

        Adds the total to ``self.coins``, clears the inventory, and returns the
        amount earned.

        ``items_lookup`` is optional: a ``{id: Item}`` mapping or a callable
        ``id -> sell_value``. When the inventory already holds full :class:`Item`
        objects (the normal case), each item's ``.coins`` is used directly and no
        lookup is needed.
        """
        total = 0
        for it in self.inventory:
            if isinstance(it, Item):
                total += it.coins
            elif items_lookup is not None:
                # ``it`` is an item id; resolve its sell value via the lookup.
                value = items_lookup[it] if isinstance(items_lookup, dict) else items_lookup(it)
                total += int(value)
            else:
                raise ValueError(
                    f"cannot auto-sell id {it!r}: inventory holds ids but no items_lookup given"
                )
        self.coins += total
        self.inventory.clear()
        return total

    # ---- level start / shop ---------------------------------------------
    def reset_power_hunger(self, power: int, hunger: int) -> None:
        """Reset power/hunger to a level's ``start_parameters`` (coins untouched)."""
        self.power = int(power)
        self.hunger = int(hunger)

    def spend(self, amount: int) -> bool:
        """Try to pay ``amount`` coins. Returns True on success, False if broke."""
        if self.coins >= amount:
            self.coins -= amount
            return True
        return False

    # ---- debug -----------------------------------------------------------
    def state_summary(self) -> str:
        inv = ", ".join(i.name_en for i in self.inventory) or "(empty)"
        return f"power={self.power} hunger={self.hunger} coins={self.coins} inv=[{inv}]"

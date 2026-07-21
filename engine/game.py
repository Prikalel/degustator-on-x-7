"""game.py — run orchestration logic (NO rendering, NO input blocking).

Owns the **state machine data** plus the pure helper methods that advance it.
All player-driven choices are surfaced as **explicit decision points** that the
caller (UI / test harness) resolves by calling a method — nothing blocks on
input, so this is fully headless-testable.

State machine (DESIGN.md §5.2), represented as string constants on :class:`State`::

    [*] MAIN_MENU
        -> LEVEL_INTRO (start_run / next level)
            -> EAT_PHASE           (player may eat any inventory items)
                -> MOVE_SELECT     (done_eating; pick a movement option)
                    -> DICE_ROLL   (option chosen & affordable; roll the die)
                        -> LANDING_CHOICE   (variants > 1 -> player picks)
                        -> EAT_PHASE        (single landing / resolved -> apply move)
            -> SHOP                (reached exit: auto-sell done)
                -> LEVEL_INTRO     (next level)  |  VICTORY (was last level)
        GAME_OVER                  (power<0 | hunger<0 | stuck)
        VICTORY                    (cleared the last level)

Per-turn cost model (instruction.md, DESIGN.md §3.6): each move pays the chosen
option's ``power`` cost AND exactly ``1`` hunger. A move option is selectable
only while ``player.power >= option.power``. Game over when ``power<0`` or
``hunger<0`` after a move, or when no option is affordable (stuck).

Pickup semantics: items are looted ONLY on the cell the player actually lands on
(on-land, not on-pass); the cell is then marked collected so re-traversal yields
nothing (movement.py).
"""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional, Sequence

import movement
from items import Item, get_items
from levels_data import LevelData, get_levels
from player import Player


class State:
    """All reachable states (string constants for readability in logs/tests)."""

    MAIN_MENU = "MAIN_MENU"
    LEVEL_INTRO = "LEVEL_INTRO"
    EAT_PHASE = "EAT_PHASE"          # can eat inventory items; done_eating() to proceed
    MOVE_SELECT = "MOVE_SELECT"      # pick a movement option
    DICE_ROLL = "DICE_ROLL"          # option chosen; roll_dice() to roll
    LANDING_CHOICE = "LANDING_CHOICE"  # variants > 1; resolve_landing_*() to pick
    SHOP = "SHOP"                    # after auto-sell; buy_shop_item() / finish_shop()
    GAME_OVER = "GAME_OVER"
    VICTORY = "VICTORY"

    # A level "ends" the instant the exit is reached; that transition is handled
    # inline (auto-sell -> SHOP), so LEVEL_END is not a lingering playable state.
    PLAYING_STATES = frozenset({EAT_PHASE, MOVE_SELECT, DICE_ROLL, LANDING_CHOICE})


class Game:
    """Headless game controller. The UI/test harness drives it method by method."""

    def __init__(
        self,
        levels: Optional[Sequence[LevelData]] = None,
        items_table: Optional[Dict[int, Item]] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.levels: List[LevelData] = list(levels) if levels is not None else get_levels()
        self.items_table: Dict[int, Item] = dict(items_table) if items_table is not None else get_items()
        self.rng = rng or random

        # Run state.
        self.state: str = State.MAIN_MENU
        self.level_index: int = -1
        self.player: Player = Player()
        self._carry: List[Item] = []        # items bought in shop -> next level's inventory

        # Current-level runtime (set by start_level).
        self.current_level: Optional[LevelData] = None
        self.graph: Optional[movement.Graph] = None
        self.player_pos: movement.Cell = (0, 0)
        self.collected: set = set()         # cells already looted this level

        # Per-turn decision scratch.
        self.pending_move_index: Optional[int] = None
        self.pending_move = None            # the chosen Move
        self.last_roll: Optional[int] = None
        self.landing_set: set = set()       # raw S_n set (frozenset of cells)
        self.landing_variants: List[movement.Cell] = []  # sorted list when > 1

        # Optional readable trace for debugging / tests.
        self.trace: List[str] = []

    # ------------------------------------------------------------------ utils
    def _log(self, msg: str) -> None:
        self.trace.append(msg)

    @property
    def num_levels(self) -> int:
        return len(self.levels)

    def is_last_level(self) -> bool:
        return self.level_index == self.num_levels - 1

    def is_playing(self) -> bool:
        return self.state in State.PLAYING_STATES

    def is_over(self) -> bool:
        return self.state in (State.GAME_OVER, State.VICTORY)

    # ------------------------------------------------------------------ run
    def start_run(self) -> None:
        """Begin a fresh run at level 1: coins reset to 0, carry list cleared."""
        self.player = Player()            # power/hunger set by start_level; coins 0
        self._carry = []
        self.trace = []
        self._log("RUN START")
        self.start_level(0)

    # -------------------------------------------------------------- level mgmt
    def start_level(self, index: int) -> LevelData:
        """Enter level ``index``: reset power/hunger, set inventory from carry,
        build the movement graph, place the player at the start cell."""
        if not (0 <= index < self.num_levels):
            raise IndexError(f"level index {index} out of range (0..{self.num_levels - 1})")
        self.level_index = index
        lvl = self.levels[index]
        self.current_level = lvl

        # Only coins persist; power/hunger reset from this level's start_parameters.
        self.player.reset_power_hunger(lvl.start_parameters.power, lvl.start_parameters.hunger)
        # Inventory refilled ONLY with shop purchases from the previous level.
        self.player.inventory = list(self._carry)
        self._carry = []

        # Movement graph + runtime state.
        self.graph = movement.build_graph(lvl)
        self.player_pos = self.graph.start
        self.collected = set()
        self.pending_move_index = None
        self.pending_move = None
        self.last_roll = None
        self.landing_set = set()
        self.landing_variants = []

        self.state = State.EAT_PHASE  # LEVEL_INTRO is implicit; ready for first turn.
        self._log(
            f"LEVEL {index + 1} ('{lvl.name_en}'): start {self.graph.start} exit {self.graph.exit} "
            f"| {self.player.state_summary()}"
        )
        return lvl

    @property
    def moves(self) -> List:
        """The current level's movement options."""
        return self.current_level.moves if self.current_level else []

    def exit_pos(self) -> movement.Cell:
        return self.graph.exit

    def is_at_exit(self) -> bool:
        return self.player_pos == self.graph.exit

    # ------------------------------------------------------------------ EAT
    def eat_item(self, index: int) -> Item:
        """Eat the inventory item at ``index`` (EAT_PHASE). Returns the eaten item."""
        if self.state != State.EAT_PHASE:
            raise RuntimeError(f"eat_item only valid in EAT_PHASE, not {self.state}")
        item = self.player.eat_index(index)
        self._log(f"  eat {item.name_en}: {self.player.state_summary()}")
        return item

    def done_eating(self) -> None:
        """Finish eating and move to MOVE_SELECT.

        If NO movement option is affordable (and eating is done), the player is
        STUCK -> GAME_OVER (DESIGN.md §3.6). Eating happens *before* this, so the
        affordability check correctly accounts for any power restored by eating.
        """
        if self.state != State.EAT_PHASE:
            raise RuntimeError(f"done_eating only valid in EAT_PHASE, not {self.state}")
        if self.player.is_dead():
            self.state = State.GAME_OVER
            self._log(f"GAME OVER: dead ({self.player.state_summary()})")
            return
        if not self.player.can_afford_any(self.moves):
            self.state = State.GAME_OVER
            self._log(f"GAME OVER: stuck (no affordable move) {self.player.state_summary()}")
            return
        self.state = State.MOVE_SELECT

    # --------------------------------------------------------- MOVE SELECT
    def affordable_moves(self) -> List[int]:
        """Indices of movement options the player can currently afford."""
        return [i for i, m in enumerate(self.moves) if self.player.can_afford(m)]

    def select_move(self, index: int) -> None:
        """Choose movement option ``index`` (gated on affordability) -> DICE_ROLL."""
        if self.state != State.MOVE_SELECT:
            raise RuntimeError(f"select_move only valid in MOVE_SELECT, not {self.state}")
        if not (0 <= index < len(self.moves)):
            raise IndexError(f"move index {index} out of range")
        move = self.moves[index]
        if not self.player.can_afford(move):
            raise RuntimeError(
                f"cannot afford move {index} (cost {move.power}, power {self.player.power})"
            )
        self.pending_move_index = index
        self.pending_move = move
        self.state = State.DICE_ROLL
        self._log(f"  select move d{move.max_value} (cost {move.power})")

    # ----------------------------------------------------------- DICE ROLL
    def roll_dice(self, value: Optional[int] = None) -> int:
        """Roll the die for the pending move and compute the landing set.

        ``value`` may be injected (for tests / deterministic replay); otherwise
        ``randint(1, move.max_value)`` is used. Resolves automatically when the
        landing set has 0 or 1 cells (clamp-to-exit / auto-move); when it has > 1
        the state becomes LANDING_CHOICE and ``self.landing_variants`` is set.
        Returns the rolled value.
        """
        if self.state != State.DICE_ROLL or self.pending_move is None:
            raise RuntimeError(f"roll_dice only valid in DICE_ROLL, not {self.state}")
        max_value = self.pending_move.max_value
        if value is None:
            value = self.rng.randint(1, max_value)
        else:
            if not (1 <= value <= max_value):
                raise ValueError(f"injected dice {value} out of range 1..{max_value}")
        self.last_roll = value
        self.landing_set = self.graph.reachable(self.player_pos, value)

        if len(self.landing_set) == 0:
            # Overshoot: every walk hit the unique sink -> clamp to exit.
            self._log(f"  roll {value}: overshoot -> clamp to EXIT")
            self._apply_resolution(self.graph.exit)
        elif len(self.landing_set) == 1:
            cell = next(iter(self.landing_set))
            self._log(f"  roll {value}: single landing {cell}")
            self._apply_resolution(cell)
        else:
            self.landing_variants = sorted(self.landing_set)
            self.state = State.LANDING_CHOICE
            self._log(f"  roll {value}: {len(self.landing_variants)} variants {self.landing_variants}")
        return value

    # ------------------------------------------------------- LANDING CHOICE
    def resolve_landing_index(self, variant_index: int) -> None:
        """Pick the ``variant_index``-th candidate cell (0-based) and apply the move."""
        if self.state != State.LANDING_CHOICE:
            raise RuntimeError(f"resolve_landing_* only valid in LANDING_CHOICE, not {self.state}")
        cell = self.landing_variants[variant_index]
        self._log(f"  choose variant {variant_index}: {cell}")
        self._apply_resolution(cell)

    def resolve_landing(self, cell: movement.Cell) -> None:
        """Pick a specific candidate ``cell`` and apply the move."""
        if self.state != State.LANDING_CHOICE:
            raise RuntimeError(f"resolve_landing_* only valid in LANDING_CHOICE, not {self.state}")
        if cell not in self.landing_set:
            raise ValueError(f"cell {cell} is not among the landing variants")
        self._log(f"  choose variant cell {cell}")
        self._apply_resolution(cell)

    # ------------------------------------------------- APPLY MOVE (common tail)
    def _apply_resolution(self, cell: movement.Cell) -> None:
        """The common tail of any resolved move: pay cost, move, loot, then check."""
        # Pay the chosen option's power cost AND exactly 1 hunger.
        self.player.apply_move(self.pending_move)
        self.player_pos = cell
        looted = self._loot(cell)

        # Reset per-turn scratch.
        self.pending_move_index = None
        self.pending_move = None
        self.landing_set = set()
        self.landing_variants = []

        self._log(
            f"  -> land {cell} (item={looted.name_en if looted else 'none'}): "
            f"{self.player.state_summary()}"
        )

        # Check terminal conditions in the right order.
        if self.player.is_dead():
            self.state = State.GAME_OVER
            self._log(f"GAME OVER: dead after move ({self.player.state_summary()})")
            return
        if cell == self.graph.exit:
            self._end_level()
            return
        # Survived, not at exit -> next turn (eat phase).
        self.state = State.EAT_PHASE

    def _loot(self, cell: movement.Cell) -> Optional[Item]:
        """Pick up the item on ``cell`` (on-land only). Marks the cell collected."""
        if cell in self.collected:
            return None
        r, c = cell
        item_id = self.current_level.item_id_at(r, c)
        if item_id is None:
            return None
        item = self.items_table[item_id]
        self.player.add_item(item)
        self.collected.add(cell)
        return item

    # ------------------------------------------------------------- LEVEL END
    def _end_level(self) -> None:
        """Reached the exit: auto-sell the inventory for coins, then open the shop."""
        earned = self.player.auto_sell()  # clears inventory, adds to coins
        self._log(f"LEVEL {self.level_index + 1} CLEARED: auto-sell +{earned} coins "
                  f"-> coins={self.player.coins}")
        self.state = State.SHOP

    # ------------------------------------------------------------------ SHOP
    def shop_offers(self):
        return self.current_level.shop_after_level

    def buy_shop_item(self, index: int) -> bool:
        """Buy shop offer ``index`` if affordable. The item carries to the next level.

        Returns True on success, False if the player cannot afford it (coins < cost).
        """
        if self.state != State.SHOP:
            raise RuntimeError(f"buy_shop_item only valid in SHOP, not {self.state}")
        offers = self.shop_offers()
        if not (0 <= index < len(offers)):
            raise IndexError(f"shop offer index {index} out of range")
        offer = offers[index]
        if not self.player.spend(offer.shop_cost):
            self._log(f"  shop: cannot afford {self.items_table[offer.item_id].name_en} "
                      f"(cost {offer.shop_cost}, coins {self.player.coins})")
            return False
        item = self.items_table[offer.item_id]
        self._carry.append(item)
        self._log(f"  shop: buy {item.name_en} for {offer.shop_cost} "
                  f"-> coins={self.player.coins}")
        return True

    def finish_shop(self) -> None:
        """Leave the shop: go to the next level, or VICTORY if this was the last."""
        if self.state != State.SHOP:
            raise RuntimeError(f"finish_shop only valid in SHOP, not {self.state}")
        if self.is_last_level():
            self.state = State.VICTORY
            self._log(f"VICTORY: finished all {self.num_levels} levels, "
                      f"final coins={self.player.coins}")
        else:
            self.start_level(self.level_index + 1)

    # ----------------------------------------------- convenience (headless)
    def run_turn(
        self,
        move_index: int,
        dice_value: Optional[int] = None,
        choose: Optional[Callable[[List[movement.Cell]], int]] = None,
    ) -> str:
        """Drive one full turn headlessly: eat-nothing -> select -> roll -> resolve.

        ``choose`` is a callback ``(variants) -> index`` invoked only when the roll
        produces > 1 landing (default: pick index 0). Useful for tests / replays;
        the granular methods remain available for interactive UIs.

        Returns the resulting state (e.g. EAT_PHASE / SHOP / GAME_OVER / VICTORY).
        """
        if self.state == State.EAT_PHASE:
            self.done_eating()
            if self.state == State.GAME_OVER:
                return self.state
        self.select_move(move_index)
        self.roll_dice(dice_value)
        if self.state == State.LANDING_CHOICE:
            idx = (choose or (lambda v: 0))(self.landing_variants)
            self.resolve_landing_index(idx)
        return self.state


__all__ = ["Game", "State"]

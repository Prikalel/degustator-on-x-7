"""main.py — async entry point + game loop for "Degustator on X-7".

Pygbag-compatible: ``async def main()`` with ``await asyncio.sleep(0)`` every
frame. The SAME file runs natively via ``python main.py`` (the
``if __name__ == "__main__"`` guard below) and inside a Pygbag browser bundle.

Responsibilities
----------------
* pygame init + display (SCALED + vsync when available).
* a single cooperative event loop: QUIT / KEYDOWN / MOUSEBUTTONDOWN / MOUSEWHEEL.
* per-state input dispatch onto the headless :class:`game.Game` methods
  (start_run / eat_item / done_eating / select_move / roll_dice /
  resolve_landing_index / buy_shop_item / finish_shop).
* dt-driven, NON-blocking animations: the dice settle animation and the token
  slide between cells. Never ``time.sleep`` / ``pygame.time.delay``.
* lazy ``pygame.mixer`` init on the first user gesture (browser autoplay policy)
  + best-effort background music & sfx (all errors swallowed).
* a minimal MAIN MENU (Start Run / Tutorial / EN-RU toggle) + Tutorial screen.

Hard constraints honoured (DESIGN.md §6.4): stdlib + pygame only, no
tkinter/PIL/threading, no blocking sleeps, all asset paths relative.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

# --- engine/ bootstrap --------------------------------------------------
# The game modules live in ./engine so the project root stays tidy while
# Pygbag's required entry point (main.py) remains at the root. Adding the
# package directory to sys.path means the modules keep their existing plain
# ``import config`` / ``from game import Game`` statements — nothing inside any
# module had to be rewritten. Works natively and inside the Pygbag browser
# bundle (the app dir is the working directory; __file__ resolves to main.py).
_ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine")
if _ENGINE_DIR not in sys.path:
    sys.path.insert(0, _ENGINE_DIR)

import pygame

import config
from game import Game, State
import render
from render import Anim, Renderer

# Animation tuning (seconds).
DICE_DUR = 0.85     # how long the die tumbles before settling
SLIDE_DUR = 0.32    # token slide between cells after a resolved move


class App:
    """Owns pygame, the Game controller, the Renderer, and UI animation state."""

    def __init__(self) -> None:
        pygame.init()
        # NOTE: do NOT use pygame.SCALED. Inside the Pygbag browser canvas,
        # SCALED delivers MOUSEBUTTONDOWN positions in the physical/canvas
        # space instead of the logical 800x600 surface, so every click
        # hit-test (rect.collidepoint) silently fails everywhere — while
        # keyboard input (which carries no position) still works. Plain mode
        # keeps mouse coordinates consistent on both desktop and web.
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        pygame.display.set_caption("Degustator on X-7")
        self.clock = pygame.time.Clock()

        self.game = Game()
        self.renderer = Renderer("en")
        self.anim = Anim()
        self.running = True

        # UI animation sub-phase: "idle" | "dice" | "slide".
        self.ui_phase = "idle"
        self.dice_t = 0.0
        self.dice_target: Optional[int] = None
        self.slide_t = 0.0
        self.slide_from = None
        self.slide_to = None

        # Level-intro detection.
        self._last_level = -1
        self._prev_state = State.MAIN_MENU
        self.last_earned = 0

        # Audio (lazy).
        self.mixer_ready = False
        self._music_started = False

    # ===================================================================
    # Audio (best-effort; lazy on first gesture for browser autoplay policy)
    # ===================================================================
    def _ensure_audio(self) -> None:
        if self.mixer_ready:
            return
        try:
            pygame.mixer.init()
            self.mixer_ready = True
        except Exception:
            self.mixer_ready = False
            return
        if not self._music_started:
            try:
                pygame.mixer.music.load(config.MUSIC_BG)
                pygame.mixer.music.set_volume(0.35)
                pygame.mixer.music.play(-1)
                self._music_started = True
            except Exception:
                pass

    def _sfx(self, path: str) -> None:
        if not self.mixer_ready:
            return
        try:
            snd = pygame.mixer.Sound(path)
            snd.set_volume(0.6)
            snd.play()
        except Exception:
            pass

    # ===================================================================
    # Event routing
    # ===================================================================
    def _on_event(self, ev: pygame.event.Event) -> None:
        # The first KEYDOWN / MOUSEBUTTONDOWN unlocks audio in browsers.
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self._ensure_audio()

        if ev.type == pygame.KEYDOWN:
            self._on_key(ev.key)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._on_click(self._to_logical(ev.pos))
        elif ev.type == pygame.MOUSEWHEEL:
            self._on_wheel(ev.y)

    def _to_logical(self, pos) -> tuple:
        """Map a mouse position into the logical (config.WIDTH x config.HEIGHT)
        surface space used by every renderer hit-test rect.

        In plain (non-SCALED) mode ``pygame.display.get_window_size()`` and the
        event position share the same coordinate system, so this is an identity
        when the window equals the logical size and otherwise rescales by the
        real ratio — robust for native desktop and the Pygbag browser canvas.
        """
        try:
            ww, wh = pygame.display.get_window_size()
        except Exception:
            return pos
        if not ww or not wh or (ww == config.WIDTH and wh == config.HEIGHT):
            return (int(pos[0]), int(pos[1]))
        return (int(round(pos[0] * config.WIDTH / ww)),
                int(round(pos[1] * config.HEIGHT / wh)))

    def _on_wheel(self, dy: int) -> None:
        if self.anim.tutorial:
            self.anim.tutorial_scroll = max(0, self.anim.tutorial_scroll - dy * 40)
        elif self.game.state == State.SHOP:
            self.anim.shop_scroll = max(0, self.anim.shop_scroll - dy * 40)
            self._clamp_shop_scroll()

    # ----------------------------------------------------- number-key helper
    @staticmethod
    def _digit(key: int) -> Optional[int]:
        """Map K_1..K_9 / K_KP1..K_KP9 -> 0-based index, else None."""
        if pygame.K_1 <= key <= pygame.K_9:
            return key - pygame.K_1
        if pygame.K_KP1 <= key <= pygame.K_KP9:
            return key - pygame.K_KP1
        return None

    # ===================================================================
    # Keyboard
    # ===================================================================
    def _on_key(self, key: int) -> None:
        g = self.game

        # While a move-slide is animating, swallow everything.
        if self.ui_phase == "slide":
            return
        # During the dice tumble only SPACE (skip) is accepted.
        if self.ui_phase == "dice":
            if key == pygame.K_SPACE:
                self.dice_t = DICE_DUR  # force commit on next update
            return

        # Dismiss the level-intro overlay (any key/click).
        if self.anim.intro and g.is_playing():
            self.anim.intro = False
            return

        # Tutorial overlay.
        if self.anim.tutorial:
            if key == pygame.K_ESCAPE:
                self.anim.tutorial = False
            elif key in (pygame.K_UP, pygame.K_PAGEUP):
                self.anim.tutorial_scroll = max(0, self.anim.tutorial_scroll - 40)
            elif key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                self.anim.tutorial_scroll += 40
            return

        st = g.state

        if st == State.MAIN_MENU:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._open_company_select()
            elif key == pygame.K_t:
                self._open_tutorial()
            elif key == pygame.K_l:
                self._toggle_lang()
            elif key == pygame.K_ESCAPE:
                self.running = False
            return

        if st == State.COMPANY_SELECT:
            if key == pygame.K_ESCAPE:
                self._to_menu()
            else:
                idx = self._digit(key)
                if idx is not None:
                    # digit 1 -> company #1, digit 2 -> company #2, ...
                    self._pick_company_by_number(idx + 1)
            return

        if st in (State.GAME_OVER, State.VICTORY):
            self._to_menu()
            return

        if st == State.SHOP:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._finish_shop()
            elif key == pygame.K_UP:
                self.anim.shop_scroll = max(0, self.anim.shop_scroll - 40)
                self._clamp_shop_scroll()
            elif key == pygame.K_DOWN:
                self.anim.shop_scroll += 40
                self._clamp_shop_scroll()
            else:
                idx = self._digit(key)
                if idx is not None:
                    self._buy(idx)
            return

        if st == State.EAT_PHASE:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._done_eating()
            else:
                idx = self._digit(key)
                if idx is not None:
                    self._eat(idx)
            return

        if st == State.MOVE_SELECT:
            idx = self._digit(key)
            if idx is not None:
                self._select_move(idx)
            return

        if st == State.DICE_ROLL:
            if key == pygame.K_SPACE:
                self.dice_t = DICE_DUR
            return

        if st == State.LANDING_CHOICE:
            idx = self._digit(key)
            if idx is not None:
                self._choose_landing(idx)
            return

    # ===================================================================
    # Mouse
    # ===================================================================
    def _on_click(self, pos) -> None:
        g = self.game
        if self.ui_phase != "idle":
            return

        if self.anim.intro and g.is_playing():
            self.anim.intro = False
            return
        if self.anim.tutorial:
            self.anim.tutorial = False
            return

        st = g.state

        if st == State.MAIN_MENU:
            for action, rect in self.renderer.menu_rects():
                if rect.collidepoint(pos):
                    if action == "play":
                        self._open_company_select()
                    elif action == "tutorial":
                        self._open_tutorial()
                    elif action == "lang":
                        self._toggle_lang()
                    return
            return

        if st == State.COMPANY_SELECT:
            rows, back, _ = self.renderer.company_select_rects(g)
            if back.collidepoint(pos):
                self._to_menu()
                return
            for c, rect in rows:
                if rect.collidepoint(pos):
                    self._start_company(c.number)
                    return
            return

        if st in (State.GAME_OVER, State.VICTORY):
            self._to_menu()
            return

        if st == State.SHOP:
            rows, cont, _, _ = self.renderer.shop_rects(g, self.anim.shop_scroll)
            if cont.collidepoint(pos):
                self._finish_shop()
                return
            for i, _off, row_rect, buy_rect, _ry in rows:
                if row_rect.collidepoint(pos) or buy_rect.collidepoint(pos):
                    self._buy(i)
                    return
            return

        if st == State.EAT_PHASE:
            for i, rect in self.renderer.inventory_row_rects(g):
                if rect.collidepoint(pos):
                    self._eat(i)
                    return
            if self.renderer.eat_done_rect().collidepoint(pos):
                self._done_eating()
            return

        if st == State.MOVE_SELECT:
            for i, rect, _aff, _m in self.renderer.move_button_rects(g):
                if rect.collidepoint(pos):
                    self._select_move(i)
                    return
            return

        if st == State.LANDING_CHOICE:
            for i, _cell, rect in self.renderer.landing_choice_rects(g):
                if rect.collidepoint(pos):
                    self._choose_landing(i)
                    return
            return

    # ===================================================================
    # High-level actions (drive the Game controller)
    # ===================================================================
    def _open_company_select(self) -> None:
        # "Play" -> open the campaign selection screen.
        self.game.open_company_select()
        self.anim.intro = False
        self.anim.tutorial = False
        self.ui_phase = "idle"

    def _pick_company_by_number(self, number: int) -> None:
        for c in self.game.companies:
            if c.number == number:
                self._start_company(c.number)
                return

    def _start_company(self, number: int) -> None:
        # Begin the chosen campaign immediately at its first level.
        self.game.start_company(number)
        self._last_level = -1          # force the level intro to (re)trigger
        self.anim.shop_scroll = 0
        self.anim.intro = False
        self.ui_phase = "idle"

    def _open_tutorial(self) -> None:
        self.anim.tutorial = True
        self.anim.tutorial_scroll = 0

    def _toggle_lang(self) -> None:
        new_lang = "ru" if self.renderer.lang == "en" else "en"
        self.renderer.set_lang(new_lang)

    def _eat(self, idx: int) -> None:
        if self.game.state != State.EAT_PHASE:
            return
        if 0 <= idx < len(self.game.player.inventory):
            self.game.eat_item(idx)
            self._sfx(config.SFX_NOM)

    def _done_eating(self) -> None:
        if self.game.state != State.EAT_PHASE:
            return
        self.game.done_eating()  # -> MOVE_SELECT  |  GAME_OVER (stuck)

    def _select_move(self, idx: int) -> None:
        if self.game.state != State.MOVE_SELECT:
            return
        moves = self.game.moves
        if 0 <= idx < len(moves) and self.game.player.can_afford(moves[idx]):
            self.game.select_move(idx)            # -> DICE_ROLL
            self._begin_dice(moves[idx])

    def _choose_landing(self, idx: int) -> None:
        if self.game.state != State.LANDING_CHOICE:
            return
        if 0 <= idx < len(self.game.landing_variants):
            prev = self.game.player_pos
            self.game.resolve_landing_index(idx)  # applies the move
            self._sfx(config.SFX_NOM)
            self._begin_slide(prev, self.game.player_pos)

    def _buy(self, idx: int) -> None:
        if self.game.state != State.SHOP:
            return
        offers = self.game.shop_offers()
        if 0 <= idx < len(offers):
            if self.game.buy_shop_item(idx):
                self._sfx(config.SFX_NOM)

    def _finish_shop(self) -> None:
        if self.game.state != State.SHOP:
            return
        self.game.finish_shop()  # -> next level (EAT_PHASE)  |  VICTORY
        self.anim.shop_scroll = 0

    def _to_menu(self) -> None:
        # Return to the main menu; the next "Start Run" creates a fresh run.
        self.game.state = State.MAIN_MENU
        self.anim.intro = False
        self.anim.tutorial = False
        self.ui_phase = "idle"
        self._last_level = -1

    # ===================================================================
    # Animation controllers (non-blocking, dt-driven)
    # ===================================================================
    def _begin_dice(self, move) -> None:
        self.dice_t = 0.0
        self.dice_target = self.game.rng.randint(1, move.max_value)
        self.anim.rolling = True
        self.anim.dice_target = self.dice_target
        self.anim.dice_face = self.dice_target
        self.ui_phase = "dice"

    def _commit_dice(self) -> None:
        """End the tumble: roll the (pre-picked) value and resolve."""
        self.anim.rolling = False
        value = self.dice_target or 1
        prev = self.game.player_pos
        self.game.roll_dice(value)          # may auto-resolve or -> LANDING_CHOICE
        self.anim.dice_face = value
        self.dice_target = None

        if self.game.state == State.LANDING_CHOICE:
            self.ui_phase = "idle"          # wait for the player to pick a variant
            return
        # Single / overshoot resolution already applied the move. Slide if moved.
        if self.game.player_pos != prev:
            self._begin_slide(prev, self.game.player_pos)
        else:
            self.ui_phase = "idle"

    def _begin_slide(self, frm, to) -> None:
        self.slide_from = frm
        self.slide_to = to
        self.slide_t = 0.0
        self.ui_phase = "slide"

    # ===================================================================
    # Per-frame update
    # ===================================================================
    def update(self, dt: float) -> None:
        self.anim.time += dt
        g = self.game

        # Level-intro overlay: triggers whenever a new level becomes active.
        if g.is_playing() and g.level_index != self._last_level:
            self._last_level = g.level_index
            self.anim.intro = True
            self.anim.shop_scroll = 0

        # Track transition INTO shop to capture the auto-sell earnings.
        if g.state == State.SHOP and self._prev_state != State.SHOP:
            self.last_earned = self._parse_last_earned()
            self.anim.shop_scroll = 0
        self._prev_state = g.state
        self.anim.shop_earned = self.last_earned

        # Dice tumble.
        if self.ui_phase == "dice" and g.state == State.DICE_ROLL:
            self.dice_t += dt
            mv = g.pending_move
            maxv = mv.max_value if mv is not None else 6
            # tumble: random face each frame
            self.anim.dice_face = g.rng.randint(1, maxv)
            if self.dice_t >= DICE_DUR:
                self._commit_dice()

        # Token slide.
        elif self.ui_phase == "slide":
            self.slide_t += dt
            t = min(1.0, self.slide_t / SLIDE_DUR)
            if g.current_level is not None and self.slide_from is not None:
                self.anim.player_pixel = self.renderer.lerp_pixel(
                    g.current_level, self.slide_from, self.slide_to, t
                )
            if t >= 1.0:
                self.ui_phase = "idle"
                self.anim.player_pixel = None
                self.slide_from = None
                self.slide_to = None
                if g.state == State.GAME_OVER:
                    self._sfx(config.SFX_DAMAGE)

        # Keep the shop list scroll in range.
        if g.state == State.SHOP:
            self._clamp_shop_scroll()

        # Full-screen overlays are suppressed while a slide/dice is mid-flight
        # so the player sees the token finish moving first.
        self.anim.overlays_ok = (self.ui_phase == "idle")

    def _clamp_shop_scroll(self) -> None:
        total = self.renderer.shop_list_height(self.game)
        view = self.renderer.shop_view_height()
        max_scroll = max(0, total - view)
        self.anim.shop_scroll = min(self.anim.shop_scroll, max_scroll)

    def _parse_last_earned(self) -> int:
        """Recover the auto-sell coin total from the Game trace (no API change)."""
        for line in reversed(self.game.trace):
            if "auto-sell +" in line and "coins" in line:
                try:
                    seg = line.split("auto-sell +", 1)[1].split(" coins", 1)[0]
                    return int(seg)
                except Exception:
                    break
        return 0

    # ===================================================================
    # Main loop
    # ===================================================================
    async def run(self) -> None:
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                else:
                    self._on_event(ev)

            self.update(dt)
            self.renderer.draw(self.screen, self.game, self.anim)
            pygame.display.flip()
            await asyncio.sleep(0)          # CRITICAL: yield to the browser

        pygame.quit()


async def main() -> None:
    """Pygbag entry point (also runs under ``asyncio.run`` natively)."""
    app = App()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())

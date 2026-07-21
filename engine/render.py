"""render.py — pure drawing helpers for "Degustator on X-7".

NO game-state mutation happens here. Every public draw method takes a
``pygame.Surface`` + the headless :class:`game.Game` (read-only) + a transient
:class:`Anim` (animation/overlay hints produced by the UI loop) and draws onto
the surface. Geometry helpers (``cell_rect``, ``move_button_rects`` ...) return
the same :class:`pygame.Rect` objects the draw code uses, so the input layer in
``main.py`` can hit-test mouse clicks against exactly what the player sees.

Layout (DESIGN.md §5.5)::

    +---------------------------------------------------+
    | HUD: POWER [bar]  HUNGER [bar]  COINS  LEVEL x/t  |   top  (HUD_HEIGHT)
    +-----------------------------------+---------------+
    |                                   |  INVENTORY    |
    |          BOARD (centered)         |  (right panel)|
    |                                   |               |
    +-----------------------------------+---------------+
    | ACTION BAR: move buttons / dice / eat prompt /    |   bottom
    +---------------------------------------------------+

Emoji policy (DESIGN.md §5.6): gameplay-critical text is plain ASCII / item
names; ``config.USE_EMOJI`` may switch on decorative emoji but every glyph has a
text fallback. The player token is a drawn circle with "P".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

import config
from config import COLORS
import movement
from movement import CONNECTOR, LEFT, RIGHT, row_direction
from game import State

# Type aliases.
Cell = Tuple[int, int]
Pixel = Tuple[int, int]


# ---------------------------------------------------------------------------
# Transient animation / overlay context (built by main.py, read-only here).
# ---------------------------------------------------------------------------
@dataclass
class Anim:
    """Per-frame transient values passed from the UI loop to the renderer."""

    time: float = 0.0                 # wall-clock seconds (for pulses)
    rolling: bool = False             # True while the dice animation runs
    dice_face: int = 1                # currently displayed die face
    dice_target: Optional[int] = None  # the face the die will settle on
    player_pixel: Optional[Pixel] = None  # override draw pos during a slide
    intro: bool = False               # show the level-intro overlay
    shop_scroll: int = 0              # pixel scroll offset for the shop list
    shop_earned: int = 0             # coins gained from auto-sell this level end
    overlays_ok: bool = True          # False suppresses full-screen overlays
                                      # (used to let the move-slide finish first)
    tutorial_scroll: int = 0          # pixel scroll offset for the tutorial
    tutorial: bool = False            # show the tutorial overlay


# ---------------------------------------------------------------------------
# Fonts: try a comma list of common fonts; fall back to pygame default.
# DejaVu Sans / Arial both cover Cyrillic for the RU locale.
# ---------------------------------------------------------------------------
class Fonts:
    """Lazily-built font cache (built once, reused every frame)."""

    _FAMILY = "arial,dejavusans,liberationsans,helvetica,sans"

    def __init__(self) -> None:
        family = config.FONT_PATH or self._FAMILY
        try:
            self.huge = pygame.font.Font(family, 60) if config.FONT_PATH else pygame.font.SysFont(family, 60, bold=True)
            self.title = pygame.font.Font(family, 30) if config.FONT_PATH else pygame.font.SysFont(family, 30, bold=True)
            self.big = pygame.font.Font(family, 40) if config.FONT_PATH else pygame.font.SysFont(family, 40, bold=True)
            self.med = pygame.font.Font(family, 20) if config.FONT_PATH else pygame.font.SysFont(family, 20, bold=True)
            self.small = pygame.font.Font(family, 16) if config.FONT_PATH else pygame.font.SysFont(family, 16)
            self.tiny = pygame.font.Font(family, 12) if config.FONT_PATH else pygame.font.SysFont(family, 12)
        except Exception:
            self.huge = pygame.font.Font(None, 60)
            self.title = pygame.font.Font(None, 30)
            self.big = pygame.font.Font(None, 40)
            self.med = pygame.font.Font(None, 20)
            self.small = pygame.font.Font(None, 16)
            self.tiny = pygame.font.Font(None, 12)


# ---------------------------------------------------------------------------
# Emoji icon rendering (pygame.freetype) with a robust missing-glyph fallback.
# ---------------------------------------------------------------------------
class Icons:
    """Render emoji glyphs via freetype; cache surfaces; detect missing glyphs.

    A real emoji glyph at font size ``S`` is roughly ``0.8..1.1 * S`` wide; a
    missing-glyph "tofu" box (when the font has no emoji code points) is tiny
    and uniform (~0.2..0.35 * S). We use that width ratio to decide whether the
    glyph rendered, returning ``None`` when it didn't so callers draw a
    primitive fallback (lightning bolt / coin / mouth / person / checkmark)
    instead of an empty box.

    Glyphs are monochrome (freetype cannot colour-composite CBDT/COLR emoji),
    tinted by ``fgcolor``; placed on top of an item's ``color`` fill they stay
    clearly readable. A bundled emoji font can be set via ``config.FONT_EMOJI_PATH``
    (e.g. the monochrome "NotoEmoji-Regular.ttf"); otherwise system emoji fonts
    are tried (Segoe UI Emoji on Windows).
    """

    _STACK = ("segoeuiemoji,segoeuisymbol,notocoloremoji,notoemoji,"
              "seguisym,symbola,applesymbols,dejavusans,arial")

    def __init__(self) -> None:
        self._font = None
        self._cache: dict = {}
        self._enabled = bool(getattr(config, "USE_EMOJI", True))
        if not self._enabled:
            return
        try:
            from pygame import freetype
            freetype.init()  # idempotent; safe if pygame.init() already ran
            path = getattr(config, "FONT_EMOJI_PATH", None)
            if path:
                try:
                    self._font = freetype.Font(path, 24)
                except Exception:
                    self._font = None
            if self._font is None:
                try:
                    self._font = freetype.SysFont(self._STACK, 24)
                except Exception:
                    self._font = None
        except Exception:
            self._font = None

    def available(self) -> bool:
        return self._enabled and self._font is not None

    def get(self, emoji: str, size: int, color) -> Optional[pygame.Surface]:
        """Return a cached rendered glyph surface, or ``None`` if unavailable."""
        if not self.available() or not emoji:
            return None
        size = max(8, int(size))
        key = (emoji, size, tuple(color))
        if key in self._cache:
            return self._cache[key]
        surf = self._render(emoji, size, color)
        self._cache[key] = surf  # cache the None result too
        return surf

    def _render(self, emoji: str, size: int, color) -> Optional[pygame.Surface]:
        from pygame import freetype
        f = self._font
        if f is None:
            return None
        try:
            f.size = size
            rect = f.get_rect(emoji)
        except Exception:
            return None
        if rect.width < size * 0.45:   # tofu / missing glyph
            return None
        try:
            out = f.render(emoji, fgcolor=tuple(int(c) for c in color))
            surf = out[0] if isinstance(out, tuple) else out
            return surf
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Best-effort image loader (swallows errors; Pygbag bundles these as data).
# ---------------------------------------------------------------------------
def load_image(path: str) -> Optional[pygame.Surface]:
    try:
        surf = pygame.image.load(path)
    except Exception:
        return None
    try:
        return surf.convert()
    except Exception:
        return surf


def load_image_alpha(path: str) -> Optional[pygame.Surface]:
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Per-item display colour now lives in items.json (Item.color) so newly added
# items automatically get their own recognisable colour. This is the fallback
# used only if an item somehow lacks a colour field.
# ---------------------------------------------------------------------------
ITEM_DEFAULT_COLOR = (180, 180, 200)


def item_color(item) -> Tuple[int, int, int]:
    """The fill colour for an item's cell / chip (reads ``item.color``)."""
    col = getattr(item, "color", None)
    if isinstance(col, tuple) and len(col) == 3:
        return col
    return ITEM_DEFAULT_COLOR


# Classic dice pip layouts on a 3x3 grid (row, col) in 0..2.
_PIPS = {
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
    4: [(0, 0), (0, 2), (2, 0), (2, 2)],
    5: [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)],
    6: [(0, 0), (0, 2), (1, 0), (1, 2), (2, 0), (2, 2)],
}


# ---------------------------------------------------------------------------
# Minimal bilingual string table (flat dotted keys; .format with kwargs).
# Strings live directly in code (no external locales/ files) so the build is
# self-contained and robust under Pygbag.
# ---------------------------------------------------------------------------
TRANSLATIONS = {
    "en": {
        "title": "Degustator on X-7",
        "subtitle": "A taster's roguelike — clear every level in one sitting",
        "play": "Play",
        "tutorial": "Tutorial",
        "company_select_title": "CHOOSE A COMPANY",
        "company_select_hint": "Pick a company (click or press 1-9) to start. A check mark means you already cleared it.",
        "company_levels": "{n} levels",
        "company_back": "Back",
        "tutorial_back": "ESC / click to go back",
        "lang_toggle": "Language: EN  (press L for RU)",
        "start_hint": "ENTER / click  Start Run",
        "lvl_intro_title": "Level {n} / {total}",
        "lvl_intro_start": "Press ENTER / click to start",
        "lvl_intro_params": "Start  POWER {p}   HUNGER {h}   COINS {c}",
        "lvl_intro_inv": "Carried items: {c}",
        "hud_power": "POWER",
        "hud_hunger": "HUNGER",
        "hud_coins": "COINS",
        "hud_level": "LEVEL {n}/{t}",
        "inv_title": "INVENTORY",
        "inv_empty": "- empty -",
        "inv_sell": "sell {c}",
        "eat_title": "EAT PHASE",
        "eat_hint": "Click an item (or 1-9) to eat. ENTER to continue.",
        "eat_done": "Done (Continue)",
        "move_title": "CHOOSE A MOVE",
        "move_hint": "Pays POWER cost + 1 hunger. Click or press 1-{n}.",
        "move_btn": "d{m}  cost {p}",
        "move_cant": "can't afford",
        "dice_rolling": "Rolling d{m}...",
        "dice_skip": "(SPACE to skip)",
        "dice_result": "Rolled: {n}",
        "landing_title": "CHOOSE YOUR LANDING",
        "landing_hint": "Click a highlighted cell or press 1-{n}.",
        "exit_label": "EXIT",
        "shop_title": "SHOP",
        "shop_earned": "Auto-sell earned: +{c} coins",
        "shop_coins": "Coins: {c}",
        "shop_buy": "Buy ({c})",
        "shop_cant": "need {c}",
        "shop_continue": "Continue",
        "shop_empty": "Nothing for sale - press Continue.",
        "go_title": "GAME OVER",
        "go_power": "You ran out of power.",
        "go_hunger": "You starved to death.",
        "go_stuck": "No move is affordable - you are stuck.",
        "go_reached": "You reached Level {n}.",
        "go_restart": "Press any key / click to return to the menu",
        "win_title": "CONGRATULATIONS!",
        "win_sub": "You beat the game!",
        "win_coins": "Final coins: {c}",
        "win_rating": "Rating: {r}",
        "win_return": "Press any key / click to return to the menu",
        "legend": "row flow:  > right   < left   v down   |   S start   * exit",
        "low_power": "LOW POWER!",
        "low_hunger": "STARVING!",
        "tutorial_default": (
            "Travel the serpentine board from START (top-left) to EXIT "
            "(bottom-right).\nEach move costs the chosen die's POWER and 1 HUNGER.\n"
            "Loot items by landing on their cell. Eat items to restore POWER/HUNGER.\n"
            "At level end your inventory auto-sells for COINS; spend them in the shop.\n"
            "If POWER or HUNGER drops below 0, or you cannot afford any move, you lose.\n"
            "Clear every level in one run to win."
        ),
    },
    "ru": {
        "title": "Дегустатор на X-7",
        "subtitle": "Рогалик-дегустатор — пройди все уровни за один забег",
        "play": "Играть",
        "tutorial": "Обучение",
        "company_select_title": "ВЫБЕРИТЕ КОМПАНИЮ",
        "company_select_hint": "Выберите компанию (клик или 1-9), чтобы начать. Галочка — уже пройдено.",
        "company_levels": "уровней: {n}",
        "company_back": "Назад",
        "tutorial_back": "ESC / клик — назад",
        "lang_toggle": "Язык: RU  (L — английский)",
        "start_hint": "ENTER / клик  Начать забег",
        "lvl_intro_title": "Уровень {n} / {total}",
        "lvl_intro_start": "Нажмите ENTER / клик, чтобы начать",
        "lvl_intro_params": "Старт  СИЛА {p}   ГОЛОД {h}   МОНЕТЫ {c}",
        "lvl_intro_inv": "Перенос предметов: {c}",
        "hud_power": "СИЛА",
        "hud_hunger": "ГОЛОД",
        "hud_coins": "МОНЕТЫ",
        "hud_level": "УРОВЕНЬ {n}/{t}",
        "inv_title": "ИНВЕНТАРЬ",
        "inv_empty": "- пусто -",
        "inv_sell": "продажа {c}",
        "eat_title": "ФАЗА ЕДЫ",
        "eat_hint": "Клик по предмету (или 1-9), чтобы съесть. ENTER — далее.",
        "eat_done": "Готово (Далее)",
        "move_title": "ВЫБЕРИТЕ ХОД",
        "move_hint": "Тратит СИЛУ + 1 ГОЛОД. Клик или 1-{n}.",
        "move_btn": "d{m}  цена {p}",
        "move_cant": "не хватает силы",
        "dice_rolling": "Бросок d{m}...",
        "dice_skip": "(SPACE — пропустить)",
        "dice_result": "Выпало: {n}",
        "landing_title": "ВЫБЕРИТЕ КЛЕТКУ",
        "landing_hint": "Клик по подсвеченной клетке или 1-{n}.",
        "exit_label": "ВЫХОД",
        "shop_title": "МАГАЗИН",
        "shop_earned": "Автопродажа: +{c} монет",
        "shop_coins": "Монеты: {c}",
        "shop_buy": "Купить ({c})",
        "shop_cant": "надо {c}",
        "shop_continue": "Далее",
        "shop_empty": "Нет товаров — нажмите Далее.",
        "go_title": "ИГРА ОКОНЧЕНА",
        "go_power": "Закончилась сила.",
        "go_hunger": "Вы умерли от голода.",
        "go_stuck": "Ни один ход не по карману — вы застряли.",
        "go_reached": "Вы дошли до уровня {n}.",
        "go_restart": "Любая клавиша / клик — в меню",
        "win_title": "ПОЗДРАВЛЯЕМ!",
        "win_sub": "Вы прошли игру!",
        "win_coins": "Итоговые монеты: {c}",
        "win_rating": "Рейтинг: {r}",
        "win_return": "Любая клавиша / клик — в меню",
        "legend": "поток строк:  > вправо   < влево   v вниз   |   S старт   * выход",
        "low_power": "МАЛО СИЛЫ!",
        "low_hunger": "ГОЛОД!",
        "tutorial_default": (
            "Идите по змеевидной доске от СТАРТА (верх-лево) до ВЫХОДА (низ-право).\n"
            "Каждый ход тратит СИЛУ кубика и 1 ГОЛОД.\n"
            "Подбирайте предметы, встав на их клетку. Ешьте их, чтобы восстановить СИЛУ/ГОЛОД.\n"
            "В конце уровня инвентарь автопродаётся за МОНЕТЫ; тратьте их в магазине.\n"
            "Если СИЛА или ГОЛОД ниже 0, или ход не по карману — вы проиграли.\n"
            "Пройдите все уровни за один забег, чтобы победить."
        ),
    },
}


def rating_for(coins: int) -> str:
    if coins >= 20:
        return "S"
    if coins >= 12:
        return "A"
    if coins >= 6:
        return "B"
    if coins >= 1:
        return "C"
    return "D"


# ===========================================================================
# Renderer
# ===========================================================================
class Renderer:
    """Holds fonts, locale strings, cached backgrounds; exposes draw + geometry."""

    def __init__(self, lang: str = "en") -> None:
        self.lang = lang
        self.fonts = Fonts()
        self.icons = Icons()
        self.strings = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        self.bg_menu = load_image(config.BG_MAIN_MENU)
        self.bg_game = load_image(config.BG_IN_GAME)
        self._tutorial_cache: dict = {}

        # Layout derived from config (see module docstring).
        pad = 8
        self.BOARD_X = pad
        self.BOARD_Y = config.HUD_HEIGHT + pad
        self.BOARD_W = config.WIDTH - config.INVENTORY_PANEL_WIDTH - 2 * pad
        self.BOARD_H = config.HEIGHT - config.HUD_HEIGHT - 92
        self.BOTTOM_Y = self.BOARD_Y + self.BOARD_H
        self.INV_X = config.WIDTH - config.INVENTORY_PANEL_WIDTH + pad
        self.INV_W = config.INVENTORY_PANEL_WIDTH - 2 * pad
        self.INV_Y = self.BOARD_Y
        self.INV_H = self.BOARD_H
        # cached scaled backgrounds (built lazily once a display exists)
        self._bg_cache: dict = {}

    # ------------------------------------------------------------------ i18n
    def set_lang(self, lang: str) -> None:
        self.lang = lang
        self.strings = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
        self._tutorial_cache = {}

    def _t(self, key: str, **kw) -> str:
        s = self.strings.get(key, key)
        try:
            return s.format(**kw)
        except Exception:
            return s

    # ------------------------------------------------------------- text utils
    def _text(self, surf: pygame.Surface, font: pygame.font.Font,
              text: str, center: Pixel, color) -> pygame.Rect:
        img = font.render(text, True, color)
        rect = img.get_rect(center=center)
        surf.blit(img, rect)
        return rect

    def _text_left(self, surf, font, text, topleft, color):
        img = font.render(text, True, color)
        surf.blit(img, img.get_rect(topleft=topleft))

    # ----------------------------------------------------------- icon helpers
    def _draw_icon(self, screen, emoji, center, size, color, kind=None):
        """Blit an emoji glyph centred on ``center``; on missing glyph, draw a
        primitive fallback selected by ``kind`` (bolt/mouth/coin/person/check)."""
        surf = self.icons.get(emoji, size, color)
        if surf is not None:
            screen.blit(surf, surf.get_rect(center=center))
            return True
        if kind == "bolt":
            self._fb_bolt(screen, center, size, color)
        elif kind == "mouth":
            self._fb_mouth(screen, center, size, color)
        elif kind == "coin":
            self._fb_coin(screen, center, size, color)
        elif kind == "person":
            self._fb_person(screen, center, size, color)
        elif kind == "check":
            self._fb_check(screen, center, size, color)
        return False

    def _draw_item_glyph(self, screen, item, rect, color) -> None:
        """Draw an item's emoji centred in ``rect``; fall back to its initial."""
        size = int(min(rect.width, rect.height) * 0.78)
        cx, cy = rect.center
        surf = self.icons.get(getattr(item, "icon", ""), size, (40, 30, 20))
        if surf is not None:
            screen.blit(surf, surf.get_rect(center=(cx, cy)))
            return
        name = item.display_name(self.lang) if hasattr(item, "display_name") else ""
        letter = (name[:1] or "?").upper()
        self._text(screen, self.fonts.tiny, letter, rect.center, COLORS["BLACK"])

    def _stat_chips(self, screen, x, y, power, hunger, coins,
                    icon_color=(40, 30, 20), text_color=None, icon_size=13) -> None:
        """Draw a compact ⚡power 😋hunger 💰coins stat run, left-aligned at (x,y)
        where ``y`` is the vertical centre. Used in inventory/shop rows."""
        if text_color is None:
            text_color = COLORS["BLACK"]
        cur = x
        for emoji, kind, val in [(config.ICON_POWER, "bolt", f"{int(power):+d}"),
                                 (config.ICON_HUNGER, "mouth", f"{int(hunger):+d}"),
                                 (config.ICON_COINS, "coin", str(int(coins)))]:
            surf = self.icons.get(emoji, icon_size, icon_color)
            if surf is not None:
                screen.blit(surf, surf.get_rect(midleft=(cur, y)))
                cur += surf.get_width() + 2
            else:
                self._draw_icon(screen, emoji, (cur + icon_size // 2, y),
                                icon_size, icon_color, kind)
                cur += icon_size + 2
            img = self.fonts.tiny.render(val, True, text_color)
            screen.blit(img, img.get_rect(midleft=(cur, y)))
            cur += img.get_width() + 4

    # --- drawn fallback icons (used only when no emoji font/glyph is present) -
    def _fb_bolt(self, screen, center, size, color) -> None:
        cx, cy = center
        s = size
        pts = [(cx - 0.15 * s, cy - 0.55 * s), (cx + 0.30 * s, cy - 0.05 * s),
               (cx + 0.05 * s, cy - 0.05 * s), (cx + 0.15 * s, cy + 0.55 * s),
               (cx - 0.30 * s, cy + 0.05 * s), (cx - 0.05 * s, cy + 0.05 * s)]
        pygame.draw.polygon(screen, color, pts)

    def _fb_coin(self, screen, center, size, color) -> None:
        r = int(size * 0.5)
        pygame.draw.circle(screen, color, center, r)
        dark = tuple(max(0, int(c * 0.6)) for c in color)
        pygame.draw.circle(screen, dark, center, r, max(2, r // 4))
        pygame.draw.circle(screen, dark, center, max(2, r // 3))

    def _fb_mouth(self, screen, center, size, color) -> None:
        cx, cy = center
        s = size
        mouth = pygame.Rect(int(cx - s * 0.45), int(cy - s * 0.22),
                            int(s * 0.9), int(s * 0.4))
        pygame.draw.ellipse(screen, color, mouth)
        tongue = pygame.Rect(int(cx - s * 0.12), int(cy + s * 0.02),
                             int(s * 0.32), int(s * 0.3))
        pygame.draw.ellipse(screen, (220, 70, 90), tongue)

    def _fb_person(self, screen, center, size, color) -> None:
        cx, cy = center
        s = size
        # head
        pygame.draw.circle(screen, color, (int(cx), int(cy - s * 0.18)),
                           max(3, int(s * 0.26)))
        # shoulders
        body = pygame.Rect(int(cx - s * 0.42), int(cy + s * 0.12),
                           int(s * 0.84), int(s * 0.42))
        pygame.draw.rect(screen, color, body, border_radius=max(3, int(s * 0.3)))

    def _fb_check(self, screen, center, size, color) -> None:
        cx, cy = center
        r = int(size * 0.5)
        pygame.draw.circle(screen, (40, 170, 70), center, r)
        pygame.draw.circle(screen, COLORS["BLACK"], center, r, 2)
        # checkmark as two thick segments
        p1 = (cx - r * 0.45, cy + r * 0.05)
        p2 = (cx - r * 0.10, cy + r * 0.40)
        p3 = (cx + r * 0.50, cy - r * 0.35)
        pygame.draw.line(screen, COLORS["WHITE"], p1, p2, max(2, r // 4))
        pygame.draw.line(screen, COLORS["WHITE"], p2, p3, max(2, r // 4))

    # ----------------------------------------------------------- board layout
    def board_layout(self, level) -> Tuple[int, int, int]:
        """Return ``(origin_x, origin_y, cell)`` for the current level grid."""
        cols = max(1, level.num_cols)
        rows = max(1, level.num_rows)
        cell = min(self.BOARD_W // cols, self.BOARD_H // rows, 62)
        return (
            self.BOARD_X + (self.BOARD_W - cell * cols) // 2,
            self.BOARD_Y + (self.BOARD_H - cell * rows) // 2,
            cell,
        )

    def cell_rect(self, level, r: int, c: int) -> pygame.Rect:
        ox, oy, cell = self.board_layout(level)
        inset = 2
        return pygame.Rect(
            ox + c * cell + inset, oy + r * cell + inset,
            cell - 2 * inset, cell - 2 * inset,
        )

    def cell_center(self, level, r: int, c: int) -> Pixel:
        ox, oy, cell = self.board_layout(level)
        return (ox + c * cell + cell // 2, oy + r * cell + cell // 2)

    def lerp_pixel(self, level, frm: Cell, to: Cell, t: float) -> Pixel:
        a = self.cell_center(level, *frm)
        b = self.cell_center(level, *to)
        t = max(0.0, min(1.0, t))
        return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t))

    # --------------------------------------------------------- click regions
    def move_button_rects(self, game) -> List[Tuple[int, pygame.Rect, bool, object]]:
        """``[(index, rect, affordable, move)]`` for MOVE_SELECT."""
        moves = game.moves
        n = max(1, len(moves))
        bw, bh, gap = 158, 52, 14
        total = n * bw + (n - 1) * gap
        x0 = (config.WIDTH - total) // 2
        y = config.HEIGHT - 66
        out = []
        for i, m in enumerate(moves):
            rect = pygame.Rect(x0 + i * (bw + gap), y, bw, bh)
            out.append((i, rect, game.player.can_afford(m), m))
        return out

    def inventory_row_rects(self, game) -> List[Tuple[int, pygame.Rect]]:
        inv = game.player.inventory
        x = self.INV_X + 6
        y0 = self.INV_Y + 30
        rh = 36
        w = self.INV_W - 12
        return [(i, pygame.Rect(x, y0 + i * rh, w, rh - 5)) for i in range(len(inv))]

    def eat_done_rect(self) -> pygame.Rect:
        return pygame.Rect(config.WIDTH - 200, config.HEIGHT - 64, 170, 50)

    def landing_choice_rects(self, game) -> List[Tuple[int, Cell, pygame.Rect]]:
        lvl = game.current_level
        return [
            (i, cell, self.cell_rect(lvl, *cell))
            for i, cell in enumerate(game.landing_variants)
        ]

    def menu_rects(self) -> List[Tuple[str, pygame.Rect]]:
        cx = config.WIDTH // 2
        return [
            ("play", pygame.Rect(cx - 120, 300, 240, 54)),
            ("tutorial", pygame.Rect(cx - 120, 366, 240, 54)),
            ("lang", pygame.Rect(cx - 70, 432, 140, 40)),
        ]

    def company_select_rects(self, game):
        """Return ``(rows, back_rect, row_h)`` where rows=[(company, rect)],
        sorted by company number. Used for drawing AND click/keyboard hit-tests."""
        companies = list(game.companies)
        list_w = 560
        row_h = 60
        gap = 12
        x0 = (config.WIDTH - list_w) // 2
        y0 = 150
        rows = []
        for i, c in enumerate(companies):
            ry = y0 + i * (row_h + gap)
            rows.append((c, pygame.Rect(x0, ry, list_w, row_h)))
        back = pygame.Rect(20, config.HEIGHT - 56, 120, 42)
        return rows, back, row_h

    # =====================================================================
    # COMPANY SELECT
    # =====================================================================
    def draw_company_select(self, screen, game, anim) -> None:
        self._blit_bg(screen, self.bg_menu)
        self._dim(screen, 120)
        self._text(screen, self.fonts.title, self._t("company_select_title"),
                   (config.WIDTH // 2, 70), COLORS["YELLOW"])
        # wrapped hint under the title
        hint = self._t("company_select_hint")
        hy = 108
        for line in self._wrap(self.fonts.small, hint, config.WIDTH - 120):
            self._text(screen, self.fonts.small, line,
                       (config.WIDTH // 2, hy), COLORS["GRAY"])
            hy += 18

        rows, back, row_h = self.company_select_rects(game)
        for c, rect in rows:
            done = game.is_company_completed(c.number)
            base = (38, 66, 56) if done else (44, 46, 64)
            pygame.draw.rect(screen, base, rect, border_radius=10)
            pygame.draw.rect(screen, COLORS["BLACK"], rect, 2, border_radius=10)
            # number badge
            self._text(screen, self.fonts.big, str(c.number),
                       (rect.left + 38, rect.centery), COLORS["YELLOW"])
            # name + level count
            self._text_left(screen, self.fonts.med, c.display_name(self.lang),
                            (rect.left + 78, rect.top + 10), COLORS["WHITE"])
            self._text_left(screen, self.fonts.small,
                            self._t("company_levels", n=c.num_levels),
                            (rect.left + 78, rect.top + 34), COLORS["GRAY"])
            # completed check (✅ emoji, drawn checkmark fallback)
            if done:
                self._draw_icon(screen, config.ICON_CHECK,
                                (rect.right - 30, rect.centery), 30,
                                (40, 170, 70), "check")

        # back button
        pygame.draw.rect(screen, COLORS["DARK_GRAY"], back, border_radius=8)
        pygame.draw.rect(screen, COLORS["BLACK"], back, 2, border_radius=8)
        self._text(screen, self.fonts.med, self._t("company_back"),
                   back.center, COLORS["WHITE"])

    def shop_rects(self, game, scroll: int):
        """Return ``(rows, continue_rect)`` where rows=[(i, offer, row_rect, buy_rect)]."""
        offers = game.shop_offers()
        list_x, list_w = 150, 500
        row_h = 74
        list_y0 = 168
        rows = []
        for i, off in enumerate(offers):
            ry = list_y0 + i * row_h - scroll
            row_rect = pygame.Rect(list_x, ry, list_w, row_h - 10)
            buy_rect = pygame.Rect(list_x + list_w - 140, ry + 12, 124, row_h - 34)
            rows.append((i, off, row_rect, buy_rect, ry))
        cont = pygame.Rect(config.WIDTH // 2 - 100, config.HEIGHT - 58, 200, 44)
        return rows, cont, row_h, list_y0

    def shop_list_height(self, game) -> int:
        return len(game.shop_offers()) * 74

    def shop_view_height(self) -> int:
        # Visible height of the scrollable shop list (matches the draw_shop clip).
        panel_bottom = 70 + (config.HEIGHT - 150)
        return panel_bottom - 168 - 60

    # =====================================================================
    # Top-level dispatch
    # =====================================================================
    def draw(self, screen: pygame.Surface, game, anim: Anim) -> None:
        if anim.tutorial and game.state == State.MAIN_MENU:
            self.draw_tutorial(screen, anim)
            return

        if game.state == State.MAIN_MENU:
            self.draw_menu(screen, anim)
            return

        if game.state == State.COMPANY_SELECT:
            self.draw_company_select(screen, game, anim)
            return

        # In-game backdrop: HUD + board + inventory + action bar.
        self.draw_game(screen, game, anim)

        if game.state == State.SHOP and anim.overlays_ok:
            self.draw_shop(screen, game, anim)
        if anim.intro and game.is_playing() and anim.overlays_ok:
            self.draw_level_intro(screen, game, anim)
        if game.state == State.GAME_OVER and anim.overlays_ok:
            self._dim(screen)
            self.draw_gameover(screen, game, anim)
        if game.state == State.VICTORY and anim.overlays_ok:
            self._dim(screen)
            self.draw_victory(screen, game, anim)

    # ----------------------------------------------------------- backgrounds
    def _blit_bg(self, screen: pygame.Surface, bg) -> None:
        if bg is not None:
            scaled = self._bg_cache.get(id(bg))
            if scaled is None:
                try:
                    scaled = pygame.transform.smoothscale(bg, (config.WIDTH, config.HEIGHT))
                    self._bg_cache[id(bg)] = scaled
                except Exception:
                    scaled = None
            if scaled is not None:
                screen.blit(scaled, (0, 0))
                return
        screen.fill((18, 20, 28))

    def _panel(self, screen, rect, color=(28, 30, 40), border=COLORS["DARK_GRAY"], radius=8):
        pygame.draw.rect(screen, color, rect, border_radius=radius)
        pygame.draw.rect(screen, border, rect, 1, border_radius=radius)

    def _dim(self, screen: pygame.Surface, alpha: int = 170) -> None:
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        screen.blit(overlay, (0, 0))

    # =====================================================================
    # MAIN MENU
    # =====================================================================
    def draw_menu(self, screen, anim) -> None:
        self._blit_bg(screen, self.bg_menu)
        # Title
        self._text(screen, self.fonts.huge, self._t("title"),
                   (config.WIDTH // 2, 130), COLORS["YELLOW"])
        # Subtitle (may contain a newline)
        sub = self._t("subtitle")
        for k, line in enumerate(sub.split("\n")):
            self._text(screen, self.fonts.small, line,
                       (config.WIDTH // 2, 190 + k * 22), COLORS["WHITE"])

        for action, rect in self.menu_rects():
            col = COLORS["LIGHT_GREEN"] if action == "play" else COLORS["LIGHT_PURPLE"]
            pygame.draw.rect(screen, col, rect, border_radius=10)
            pygame.draw.rect(screen, COLORS["BLACK"], rect, 3, border_radius=10)
            label = self._t("play") if action == "play" else (
                self._t("tutorial") if action == "tutorial" else self._t("lang_toggle"))
            self._text(screen, self.fonts.med, label, rect.center, COLORS["WHITE"])

        self._text(screen, self.fonts.small, self._t("start_hint"),
                   (config.WIDTH // 2, config.HEIGHT - 50), COLORS["GRAY"])

    # =====================================================================
    # GAME (HUD + board + inventory + action bar)
    # =====================================================================
    def draw_game(self, screen, game, anim) -> None:
        self._blit_bg(screen, self.bg_game)
        self.draw_hud(screen, game, anim)
        self.draw_board(screen, game, anim)
        self.draw_inventory(screen, game, anim)
        self.draw_action_bar(screen, game, anim)

    # --------------------------------------------------------------- HUD
    def draw_hud(self, screen, game, anim) -> None:
        p = game.player
        rect = pygame.Rect(0, 0, config.WIDTH, config.HUD_HEIGHT)
        self._panel(screen, rect, color=(24, 26, 36), border=(0, 0, 0))
        bar_max = 12  # visual reference width scale

        # POWER  (⚡ icon instead of the word "POWER"/"СИЛА")
        self._stat(screen, 16, config.ICON_POWER, "bolt", p.power, bar_max,
                   COLORS["LIGHT_GREEN"], COLORS["RED"], low=2)
        # HUNGER (😋 icon instead of "HUNGER"/"ГОЛОД")
        self._stat(screen, 270, config.ICON_HUNGER, "mouth", p.hunger, bar_max,
                   COLORS["ORANGE"], COLORS["RED"], low=2)
        # COINS  (💰 icon instead of "COINS"/"МОНЕТЫ")
        cx = 520
        self._draw_icon(screen, config.ICON_COINS, (cx, config.HUD_HEIGHT // 2 - 2),
                        22, COLORS["YELLOW"], "coin")
        self._text(screen, self.fonts.med, str(p.coins),
                   (cx + 32, config.HUD_HEIGHT // 2), COLORS["YELLOW"])
        # LEVEL (right-aligned)
        lvl_txt = self._t("hud_level", n=game.level_index + 1, t=game.num_levels)
        img = self.fonts.med.render(lvl_txt, True, COLORS["WHITE"])
        screen.blit(img, img.get_rect(midright=(config.WIDTH - 14, config.HUD_HEIGHT // 2)))

        # pulsing danger warning when power/hunger low or negative
        msg = None
        if p.power < 0:
            msg = self._t("go_power")
        elif p.hunger < 0:
            msg = self._t("go_hunger")
        elif p.power <= 2:
            msg = self._t("low_power")
        elif p.hunger <= 2:
            msg = self._t("low_hunger")
        if msg:
            pulse = 0.5 + 0.5 * math.sin(anim.time * 6)
            col = (int(220 * pulse + 35), 40, 40)
            img = self.fonts.med.render(msg, True, col)
            screen.blit(img, img.get_rect(midtop=(config.WIDTH // 2, 3)))

    def _stat(self, screen, x, icon, kind, value, bar_max, ok_color, bad_color, low=2) -> None:
        cy = config.HUD_HEIGHT // 2
        # stat icon (emoji via freetype, drawn bolt/mouth fallback) in ok_color
        self._draw_icon(screen, icon, (x + 18, cy - 2), 22, ok_color, kind)
        # numeric value
        col = bad_color if value < 0 else (COLORS["ORANGE"] if value <= low else COLORS["WHITE"])
        self._text(screen, self.fonts.med, str(value), (x + 120, cy), col)
        # bar
        bar_x, bar_y, bar_w, bar_h = x + 4, cy + 12, 168, 6
        pygame.draw.rect(screen, (50, 50, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill = max(0, min(bar_w, int(bar_w * max(0, value) / bar_max)))
        bcol = bad_color if value < 0 else (COLORS["ORANGE"] if value <= low else ok_color)
        if fill:
            pygame.draw.rect(screen, bcol, (bar_x, bar_y, fill, bar_h), border_radius=3)

    # --------------------------------------------------------------- BOARD
    def draw_board(self, screen, game, anim) -> None:
        lvl = game.current_level
        if lvl is None:
            return
        graph = game.graph
        ox, oy, cell = self.board_layout(lvl)
        # board frame
        frame = pygame.Rect(self.BOARD_X - 2, self.BOARD_Y - 2, self.BOARD_W + 4, self.BOARD_H + 4)
        pygame.draw.rect(screen, (0, 0, 0, 120), frame, border_radius=10)
        pygame.draw.rect(screen, COLORS["DARK_GRAY"], frame, 2, border_radius=10)

        start = graph.start
        exitc = graph.exit
        choice_cells = {cell_: i for i, cell_ in enumerate(game.landing_variants)} \
            if game.state == State.LANDING_CHOICE else {}

        for r in range(lvl.num_rows):
            d = row_direction(r)
            tint = (COLORS["RIGHT_ROW_TINT"] if d == RIGHT else
                    COLORS["LEFT_ROW_TINT"] if d == LEFT else COLORS["CONNECTOR_TINT"])
            for c in range(lvl.num_cols):
                if not lvl.cell_exists(r, c):
                    continue
                rect = self.cell_rect(lvl, r, c)
                is_start = (r, c) == start
                is_exit = (r, c) == exitc
                # base tile
                base = tint
                if is_exit:
                    base = (235, 220, 150)
                pygame.draw.rect(screen, base, rect, border_radius=6)
                pygame.draw.rect(screen, COLORS["BLACK"], rect, 1, border_radius=6)

                # item (if present & not yet looted)
                if (r, c) not in game.collected:
                    item_id = lvl.item_id_at(r, c)
                    if item_id is not None:
                        self._draw_item_on_cell(screen, rect, item_id, game, cell)

                # flow arrow
                self._draw_flow_arrow(screen, rect, d, cell)
                # branch indicator (2 out-edges -> a real choice point)
                if graph is not None and len(graph.outgoing((r, c))) == 2:
                    self._draw_branch_mark(screen, rect, cell)

                # start / exit badges
                if is_start:
                    pygame.draw.rect(screen, COLORS["LIGHT_GREEN"], rect, 3, border_radius=6)
                    self._text(screen, self.fonts.med, "S",
                               (rect.left + 11, rect.top + 12), COLORS["BLACK"])
                if is_exit:
                    pygame.draw.rect(screen, COLORS["YELLOW"], rect, 3, border_radius=6)
                    self._text(screen, self.fonts.tiny, self._t("exit_label"),
                               (rect.centerx, rect.bottom - 9), COLORS["BLACK"])
                    self._draw_star(screen, (rect.centerx, rect.centery - 6), 7, COLORS["ORANGE"])

                # landing-choice highlight
                if (r, c) in choice_cells:
                    idx = choice_cells[(r, c)]
                    pulse = 0.5 + 0.5 * math.sin(anim.time * 6)
                    col = (255, int(200 + 55 * pulse), int(40 + 80 * pulse))
                    pygame.draw.rect(screen, col, rect, 4, border_radius=6)
                    badge = pygame.Rect(rect.right - 20, rect.top - 4, 20, 20)
                    pygame.draw.circle(screen, COLORS["HIGHLIGHT"], badge.center, 11)
                    pygame.draw.circle(screen, COLORS["BLACK"], badge.center, 11, 2)
                    self._text(screen, self.fonts.small, str(idx + 1),
                               badge.center, COLORS["BLACK"])

        # player token
        self._draw_player_token(screen, lvl, game, anim)

    def _draw_item_on_cell(self, screen, rect, item_id, game, cell) -> None:
        item = game.items_table.get(int(item_id))
        if item is None:
            return
        col = item_color(item)
        chip = pygame.Rect(rect.left + 4, rect.top + 4, rect.width - 8, rect.height - 8)
        pygame.draw.rect(screen, col, chip, border_radius=5)
        pygame.draw.rect(screen, COLORS["BLACK"], chip, 1, border_radius=5)
        # item emoji (🍌 🍎 …) on its coloured chip; falls back to the initial
        self._draw_item_glyph(screen, item, chip, col)

    def _draw_flow_arrow(self, screen, rect, d, cell) -> None:
        # small chevron at the trailing edge of the cell showing row flow
        if d == RIGHT:
            self._triangle(screen, (rect.right - 6, rect.centery), 5, "right", (90, 90, 110))
        elif d == LEFT:
            self._triangle(screen, (rect.left + 6, rect.centery), 5, "left", (90, 90, 110))
        else:  # connector: down hint
            self._triangle(screen, (rect.centerx, rect.bottom - 5), 4, "down", (120, 110, 80))

    def _draw_branch_mark(self, screen, rect, cell) -> None:
        # a tiny downward chevron at top-right signalling "you may descend here"
        self._triangle(screen, (rect.right - 9, rect.top + 9), 4, "down", COLORS["DARK_PURPLE"])

    def _triangle(self, screen, center, size, direction, color) -> None:
        cx, cy = center
        s = size
        if direction == "right":
            pts = [(cx - s, cy - s), (cx - s, cy + s), (cx + s, cy)]
        elif direction == "left":
            pts = [(cx + s, cy - s), (cx + s, cy + s), (cx - s, cy)]
        else:  # down
            pts = [(cx - s, cy - s), (cx + s, cy - s), (cx, cy + s)]
        pygame.draw.polygon(screen, color, pts)

    def _draw_star(self, screen, center, radius, color) -> None:
        import math
        cx, cy = center
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = radius if i % 2 == 0 else radius * 0.45
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        pygame.draw.polygon(screen, color, pts)

    def _draw_player_token(self, screen, lvl, game, anim) -> None:
        if anim.player_pixel is not None:
            pos = anim.player_pixel
        else:
            pos = self.cell_center(lvl, *game.player_pos)
        radius = max(10, self.board_layout(lvl)[2] // 2 - 8)
        # shadow
        sh = pygame.Surface((radius * 3, radius * 3), pygame.SRCALPHA)
        pygame.draw.circle(sh, (0, 0, 0, 90), (radius * 3 // 2, radius * 3 // 2 + 3), radius)
        screen.blit(sh, sh.get_rect(center=(pos[0], pos[1] + 3)))
        pygame.draw.circle(screen, COLORS["PLAYER_COLOR"], pos, radius)
        pygame.draw.circle(screen, COLORS["WHITE"], pos, radius, 3)
        # player token icon (👤 emoji, drawn person fallback) instead of "P"
        self._draw_icon(screen, config.ICON_PLAYER, pos, int(radius * 1.5),
                        COLORS["WHITE"], "person")

    # ----------------------------------------------------- dice primitive
    def _draw_die(self, screen, topleft, size, face, color) -> None:
        rect = pygame.Rect(topleft[0], topleft[1], size, size)
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, COLORS["BLACK"], rect, 2, border_radius=8)
        if face in _PIPS:
            for (gy, gx) in _PIPS[face]:
                px = rect.left + int((gx + 1) * size / 4)
                py = rect.top + int((gy + 1) * size / 4)
                pygame.draw.circle(screen, COLORS["BLACK"], (px, py), max(2, size // 12))
        else:
            self._text(screen, self.fonts.big, str(face), rect.center, COLORS["BLACK"])

    # ----------------------------------------------------------- INVENTORY
    def draw_inventory(self, screen, game, anim) -> None:
        panel = pygame.Rect(self.INV_X - 4, self.INV_Y, self.INV_W + 8, self.INV_H)
        self._panel(screen, panel, color=(30, 26, 40), border=COLORS["DARK_PURPLE"])
        self._text(screen, self.fonts.med, self._t("inv_title"),
                   (panel.centerx, self.INV_Y + 14), COLORS["YELLOW"])
        inv = game.player.inventory
        if not inv:
            self._text(screen, self.fonts.small, self._t("inv_empty"),
                       (panel.centerx, self.INV_Y + 60), COLORS["GRAY"])
        else:
            for i, rect in self.inventory_row_rects(game):
                item = inv[i]
                pygame.draw.rect(screen, item_color(item), rect, border_radius=5)
                pygame.draw.rect(screen, COLORS["BLACK"], rect, 1, border_radius=5)
                # slot index + item emoji (identity) instead of the item name
                self._text_left(screen, self.fonts.tiny, f"{i + 1}.",
                                (rect.left + 5, rect.top + 3), COLORS["BLACK"])
                glyph_rect = pygame.Rect(rect.left + 22, rect.top + 2,
                                         rect.height - 4, rect.height - 4)
                self._draw_item_glyph(screen, item, glyph_rect, item.color)
                # icon stat run ⚡/😋/💰 instead of "P.. H.. $.."
                self._stat_chips(screen, rect.left + rect.height + 8, rect.centery,
                                 item.power, item.hunger, item.coins,
                                 icon_color=(40, 30, 20))
        # legend at the bottom of the inventory panel (split on " | " into lines)
        legend_parts = self._t("legend").split(" | ")
        for k, part in enumerate(legend_parts):
            self._text(screen, self.fonts.tiny, part,
                       (panel.centerx, panel.bottom - 14 - (len(legend_parts) - 1 - k) * 14),
                       COLORS["GRAY"])

    # ------------------------------------------------------- ACTION BAR
    def draw_action_bar(self, screen, game, anim) -> None:
        st = game.state
        if st not in State.PLAYING_STATES:
            return  # SHOP / GAME_OVER / VICTORY draw their own full-screen overlays
        bar = pygame.Rect(0, self.BOTTOM_Y, config.WIDTH, config.HEIGHT - self.BOTTOM_Y)
        self._panel(screen, bar, color=(22, 24, 32), border=(0, 0, 0))

        if st == State.MOVE_SELECT:
            self._text(screen, self.fonts.med, self._t("move_title"),
                       (config.WIDTH // 2, self.BOTTOM_Y + 14), COLORS["YELLOW"])
            n = len(game.moves)
            self._text(screen, self.fonts.tiny, self._t("move_hint", n=n),
                       (config.WIDTH // 2, self.BOTTOM_Y + 36), COLORS["GRAY"])
            for i, rect, aff, m in self.move_button_rects(game):
                base = COLORS["LIGHT_GREEN"] if aff else (90, 90, 100)
                pygame.draw.rect(screen, base, rect, border_radius=8)
                pygame.draw.rect(screen, COLORS["BLACK"], rect, 2, border_radius=8)
                label = f"{i + 1}: " + self._t("move_btn", m=m.max_value, p=m.power)
                tcol = COLORS["BLACK"] if aff else (200, 200, 205)
                self._text(screen, self.fonts.med, label, rect.center, tcol)
                if not aff:
                    self._text(screen, self.fonts.tiny, self._t("move_cant"),
                               (rect.centerx, rect.bottom - 9), (230, 180, 180))

        elif st == State.DICE_ROLL:
            face = anim.dice_face if anim.rolling else (game.last_roll or anim.dice_face)
            maxv = game.pending_move.max_value if game.pending_move else 6
            die_sz = 56
            self._draw_die(screen, (config.WIDTH // 2 - die_sz - 90, self.BOTTOM_Y + 12),
                           die_sz, face, COLORS["WHITE"])
            self._text(screen, self.fonts.med, self._t("dice_rolling", m=maxv),
                       (config.WIDTH // 2 + 30, self.BOTTOM_Y + 24), COLORS["WHITE"])
            self._text(screen, self.fonts.small, self._t("dice_skip"),
                       (config.WIDTH // 2 + 30, self.BOTTOM_Y + 50), COLORS["GRAY"])

        elif st == State.LANDING_CHOICE:
            self._text(screen, self.fonts.med, self._t("landing_title"),
                       (config.WIDTH // 2, self.BOTTOM_Y + 14), COLORS["HIGHLIGHT"])
            n = len(game.landing_variants)
            self._text(screen, self.fonts.small, self._t("landing_hint", n=n),
                       (config.WIDTH // 2, self.BOTTOM_Y + 38), COLORS["WHITE"])
            if game.last_roll:
                self._text(screen, self.fonts.small, self._t("dice_result", n=game.last_roll),
                           (config.WIDTH // 2, self.BOTTOM_Y + 58), COLORS["GRAY"])

        else:  # EAT_PHASE (or any other playing state): show eat prompt + Done
            self._text(screen, self.fonts.med, self._t("eat_title"),
                       (config.WIDTH // 2, self.BOTTOM_Y + 14), COLORS["LIGHT_GREEN"])
            self._text(screen, self.fonts.small, self._t("eat_hint"),
                       (config.WIDTH // 2, self.BOTTOM_Y + 38), COLORS["WHITE"])
            done = self.eat_done_rect()
            pygame.draw.rect(screen, COLORS["LIGHT_PURPLE"], done, border_radius=8)
            pygame.draw.rect(screen, COLORS["BLACK"], done, 2, border_radius=8)
            self._text(screen, self.fonts.med, self._t("eat_done"),
                       done.center, COLORS["WHITE"])

    # ============================================================ LEVEL INTRO
    def draw_level_intro(self, screen, game, anim) -> None:
        self._dim(screen, 150)
        lvl = game.current_level
        panel = pygame.Rect(config.WIDTH // 2 - 220, config.HEIGHT // 2 - 110, 440, 220)
        self._panel(screen, panel, color=(34, 30, 50), border=COLORS["LIGHT_PURPLE"], radius=12)
        self._text(screen, self.fonts.title,
                   self._t("lvl_intro_title", n=game.level_index + 1, total=game.num_levels),
                   (panel.centerx, panel.top + 34), COLORS["YELLOW"])
        if lvl is not None:
            self._text(screen, self.fonts.big, lvl.display_name(self.lang),
                       (panel.centerx, panel.top + 80), COLORS["WHITE"])
            sp = lvl.start_parameters
            self._text(screen, self.fonts.med,
                       self._t("lvl_intro_params", p=sp.power, h=sp.hunger, c=game.player.coins),
                       (panel.centerx, panel.top + 120), COLORS["LIGHT_GREEN"])
            self._text(screen, self.fonts.small,
                       self._t("lvl_intro_inv", c=len(game.player.inventory)),
                       (panel.centerx, panel.top + 148), COLORS["GRAY"])
        self._text(screen, self.fonts.med, self._t("lvl_intro_start"),
                   (panel.centerx, panel.bottom - 26), COLORS["HIGHLIGHT"])

    # ================================================================ SHOP
    def draw_shop(self, screen, game, anim) -> None:
        self._dim(screen, 180)
        panel = pygame.Rect(110, 70, config.WIDTH - 220, config.HEIGHT - 150)
        self._panel(screen, panel, color=(34, 36, 50), border=COLORS["YELLOW"], radius=12)
        self._text(screen, self.fonts.title, self._t("shop_title"),
                   (panel.centerx, panel.top + 26), COLORS["YELLOW"])
        self._text(screen, self.fonts.med, self._t("shop_coins", c=game.player.coins),
                   (panel.centerx, panel.top + 58), COLORS["LIGHT_GREEN"])
        self._text(screen, self.fonts.small, self._t("shop_earned", c=anim.shop_earned),
                   (panel.centerx, panel.top + 82), COLORS["YELLOW"])

        offers = game.shop_offers()
        rows, cont, row_h, list_y0 = self.shop_rects(game, anim.shop_scroll)
        # clip region for the list
        clip = pygame.Rect(panel.left + 30, list_y0 - 4,
                           panel.width - 60, panel.bottom - list_y0 - 60)
        prev_clip = screen.get_clip()
        screen.set_clip(clip)

        if not offers:
            self._text(screen, self.fonts.med, self._t("shop_empty"),
                       (panel.centerx, list_y0 + 30), COLORS["GRAY"])
        for i, off, row_rect, buy_rect, ry in rows:
            if ry > clip.bottom or ry + row_h < clip.top:
                continue
            item = game.items_table.get(off.item_id)
            affordable = game.player.coins >= off.shop_cost
            pygame.draw.rect(screen, (44, 46, 64), row_rect, border_radius=8)
            pygame.draw.rect(screen, COLORS["DARK_GRAY"], row_rect, 1, border_radius=8)
            if item is not None:
                chip = pygame.Rect(row_rect.left + 8, row_rect.top + 8, 42, row_rect.height - 16)
                pygame.draw.rect(screen, item_color(item), chip, border_radius=6)
                # item emoji (identity) instead of the name
                self._draw_item_glyph(screen, item, chip, item.color)
                # icon stat run ⚡/😋/💰 instead of "P.. H.. sell .."
                self._stat_chips(screen, row_rect.left + 60, row_rect.centery,
                                 item.power, item.hunger, item.coins,
                                 icon_color=(235, 235, 240), text_color=COLORS["WHITE"])
            # buy button
            bcol = COLORS["LIGHT_GREEN"] if affordable else (80, 80, 92)
            pygame.draw.rect(screen, bcol, buy_rect, border_radius=6)
            pygame.draw.rect(screen, COLORS["BLACK"], buy_rect, 1, border_radius=6)
            blabel = self._t("shop_buy", c=off.shop_cost) if affordable else self._t("shop_cant", c=off.shop_cost)
            self._text(screen, self.fonts.small, f"{i + 1}. " + blabel,
                       buy_rect.center, COLORS["BLACK"] if affordable else (220, 220, 225))

        screen.set_clip(prev_clip)

        # continue button
        pygame.draw.rect(screen, COLORS["LIGHT_PURPLE"], cont, border_radius=8)
        pygame.draw.rect(screen, COLORS["BLACK"], cont, 2, border_radius=8)
        self._text(screen, self.fonts.med, self._t("shop_continue"),
                   cont.center, COLORS["WHITE"])

    # ============================================================ GAME OVER
    def draw_gameover(self, screen, game, anim) -> None:
        p = game.player
        if p.power < 0:
            cause = self._t("go_power")
        elif p.hunger < 0:
            cause = self._t("go_hunger")
        else:
            cause = self._t("go_stuck")
        panel = pygame.Rect(config.WIDTH // 2 - 220, config.HEIGHT // 2 - 110, 440, 220)
        self._panel(screen, panel, color=(50, 24, 28), border=COLORS["RED"], radius=12)
        self._text(screen, self.fonts.big, self._t("go_title"),
                   (panel.centerx, panel.top + 42), COLORS["RED"])
        self._text(screen, self.fonts.med, cause,
                   (panel.centerx, panel.top + 92), COLORS["WHITE"])
        self._text(screen, self.fonts.small,
                   self._t("go_reached", n=game.level_index + 1),
                   (panel.centerx, panel.top + 124), COLORS["GRAY"])
        self._text(screen, self.fonts.small, f"{self._t('hud_coins')}: {p.coins}",
                   (panel.centerx, panel.top + 148), COLORS["YELLOW"])
        self._text(screen, self.fonts.med, self._t("go_restart"),
                   (panel.centerx, panel.bottom - 24), COLORS["HIGHLIGHT"])

    # ============================================================== VICTORY
    def draw_victory(self, screen, game, anim) -> None:
        p = game.player
        panel = pygame.Rect(config.WIDTH // 2 - 230, config.HEIGHT // 2 - 120, 460, 240)
        self._panel(screen, panel, color=(30, 44, 30), border=COLORS["LIGHT_GREEN"], radius=12)
        self._text(screen, self.fonts.big, self._t("win_title"),
                   (panel.centerx, panel.top + 42), COLORS["YELLOW"])
        self._text(screen, self.fonts.med, self._t("win_sub"),
                   (panel.centerx, panel.top + 84), COLORS["WHITE"])
        self._text(screen, self.fonts.title,
                   self._t("win_coins", c=p.coins),
                   (panel.centerx, panel.top + 128), COLORS["LIGHT_GREEN"])
        self._text(screen, self.fonts.big,
                   self._t("win_rating", r=rating_for(p.coins)),
                   (panel.centerx, panel.top + 172), COLORS["HIGHLIGHT"])
        self._text(screen, self.fonts.med, self._t("win_return"),
                   (panel.centerx, panel.bottom - 24), COLORS["WHITE"])

    # ============================================================= TUTORIAL
    def _tutorial_text(self) -> str:
        if self.lang in self._tutorial_cache:
            return self._tutorial_cache[self.lang]
        name = "tutorial_ru.txt" if self.lang == "ru" else "tutorial_en.txt"
        try:
            with open(name, "r", encoding="utf-8") as fh:
                txt = fh.read()
        except Exception:
            txt = self._t("tutorial_default")
        self._tutorial_cache[self.lang] = txt
        return txt

    def draw_tutorial(self, screen, anim) -> None:
        self._blit_bg(screen, self.bg_menu)
        self._dim(screen, 120)
        panel = pygame.Rect(60, 50, config.WIDTH - 120, config.HEIGHT - 120)
        self._panel(screen, panel, color=(28, 30, 42), border=COLORS["LIGHT_PURPLE"], radius=12)
        self._text(screen, self.fonts.title, self._t("tutorial"),
                   (panel.centerx, panel.top + 28), COLORS["YELLOW"])

        clip = pygame.Rect(panel.left + 20, panel.top + 56,
                           panel.width - 40, panel.height - 96)
        prev = screen.get_clip()
        screen.set_clip(clip)
        y = panel.top + 60 - anim.tutorial_scroll
        for line in self._tutorial_text().split("\n"):
            for wrapped in self._wrap(self.fonts.small, line, clip.width):
                img = self.fonts.small.render(wrapped, True, COLORS["WHITE"])
                screen.blit(img, (clip.left, y))
                y += 20
            y += 4
        screen.set_clip(prev)
        self._text(screen, self.fonts.small, self._t("tutorial_back"),
                   (panel.centerx, panel.bottom - 22), COLORS["GRAY"])

    def _wrap(self, font, text, max_w) -> List[str]:
        words = text.split(" ")
        lines, cur = [], ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if font.size(trial)[0] <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

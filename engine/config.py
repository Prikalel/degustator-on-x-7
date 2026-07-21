"""config.py — global constants for "Degustator on X-7".

Pure data only. Importing this module must have **no side effects** and must not
require pygame (so the pure-logic modules stay unit-testable without a display).
All asset / data paths are **relative** to the project root so they work both on
desktop and inside a Pygbag web bundle (the project dir is the working dir).
"""

# ---------------------------------------------------------------------------
# Window / timing
# ---------------------------------------------------------------------------
# Folded in from the old ``scripts/window.py`` (kept identical so the rewrite is
# a faithful continuation of the prototype's window size).
WIDTH, HEIGHT = 800, 600
FPS = 60

# ---------------------------------------------------------------------------
# Grid / layout
# ---------------------------------------------------------------------------
# The board cells are drawn inside the window; this is only a *default* cell
# size. The renderer (a later phase) computes the actual cell size from the
# available area, the number of columns ``C`` and rows ``R`` of the current
# level. Kept here as a tuning knob.
CELL_SIZE = 64
HUD_HEIGHT = 40
INVENTORY_PANEL_WIDTH = 160

# ---------------------------------------------------------------------------
# Colours — copied verbatim from the old ``scripts/colors.py`` (Pygbag-safe,
# pure RGB tuples) plus a few extra UI tints used by the new architecture.
# ---------------------------------------------------------------------------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
LIGHT_GREEN = (0, 255, 0)
DARK_PURPLE = (102, 0, 153)
LIGHT_PURPLE = (153, 50, 204)
YELLOW = (255, 255, 0)

# Extra UI colours (new architecture).
RED = (220, 40, 40)            # low power / danger / game-over
ORANGE = (240, 150, 30)        # low hunger
DARK_GRAY = (60, 60, 70)       # panels / disabled
LIGHT_GRAY = (235, 235, 240)   # cell fills
RIGHT_ROW_TINT = (230, 240, 255)   # subtle tint for RIGHT-flowing rows
LEFT_ROW_TINT = (255, 235, 230)    # subtle tint for LEFT-flowing rows
CONNECTOR_TINT = (245, 245, 220)   # subtle tint for connector (down-only) rows
PLAYER_COLOR = (40, 120, 220)      # the 👤 stand-in circle
HIGHLIGHT = (255, 215, 0)          # landing-choice candidate highlight

# A convenient mapping name -> tuple for the renderer (later phase).
COLORS = {
    "WHITE": WHITE,
    "BLACK": BLACK,
    "GRAY": GRAY,
    "LIGHT_GREEN": LIGHT_GREEN,
    "DARK_PURPLE": DARK_PURPLE,
    "LIGHT_PURPLE": LIGHT_PURPLE,
    "YELLOW": YELLOW,
    "RED": RED,
    "ORANGE": ORANGE,
    "DARK_GRAY": DARK_GRAY,
    "LIGHT_GRAY": LIGHT_GRAY,
    "RIGHT_ROW_TINT": RIGHT_ROW_TINT,
    "LEFT_ROW_TINT": LEFT_ROW_TINT,
    "CONNECTOR_TINT": CONNECTOR_TINT,
    "PLAYER_COLOR": PLAYER_COLOR,
    "HIGHLIGHT": HIGHLIGHT,
}

# ---------------------------------------------------------------------------
# Paths (all relative to the project root = working dir)
# ---------------------------------------------------------------------------
ASSETS_DIR = "assets"
IMAGES_DIR = "assets/images"
SOUNDS_DIR = "assets/sounds"

ITEMS_PATH = "items.json"
# Levels are now grouped into COMPANIES: one JSON file per company in
# ``companies/<n>.json`` (the numeric filename stem = company number / order).
# LEVELS_PATH is kept only for backward compatibility with old single-file data.
LEVELS_PATH = "levels.json"
COMPANIES_DIR = "companies"

# Persistence of finished companies (web: localStorage/IDBFS; desktop: this file).
SAVE_DIR = "save"
SAVE_PATH = "save/progress.json"

# Asset file names (joined with the dirs above by the renderer later).
BG_IN_GAME = "assets/images/in-game-background.png"
BG_MAIN_MENU = "assets/images/main-menu-background.jpg"
# Audio uses OGG: Pygbag / browsers do not support MP3.
MUSIC_BG = "assets/sounds/background-music.ogg"
SFX_DAMAGE = "assets/sounds/damage.ogg"
SFX_NOM = "assets/sounds/nom-nom-nom.ogg"       # eating an inventory item
SFX_COINS = "assets/sounds/coins-pour-out-2.ogg"  # successful shop purchase
SFX_DICE = "assets/sounds/dice-roll-sound-2.ogg"  # the dice tumble animation
SFX_LOOT = "assets/sounds/camping-tent-straightening.ogg"  # item looted into inventory

# ---------------------------------------------------------------------------
# Fonts / emoji policy
# ---------------------------------------------------------------------------
# Emoji glyphs are rendered via pygame.freetype from an emoji-capable font
# (Segoe UI Emoji on Windows, or the bundled ``FONT_EMOJI_PATH`` font). The
# renderer validates each glyph (a missing glyph renders as a tiny tofu box and
# is detected by its width) and falls back to a drawn primitive so the UI never
# looks broken. ``USE_EMOJI`` simply toggles whether the emoji path is tried at
# all; turn it off to force the drawn fallbacks everywhere.
USE_EMOJI = True
DEFAULT_FONT_SIZE = 20
FONT_PATH = None  # optional bundled .ttf for the regular UI font (Cyrillic-capable)
# Optional bundled emoji font (a regular outline OpenType/TTF font that contains
# the emoji code points, e.g. "NotoEmoji-Regular.ttf" — the *monochrome* Noto
# Emoji, NOT "Noto Color Emoji" which freetype cannot colour-composite). When
# None the renderer falls back to system emoji fonts (Segoe UI Emoji on Windows).
FONT_EMOJI_PATH = "assets/NotoEmoji-Regular.ttf"

# Canonical gameplay icons (emoji glyphs) — used instead of locale-specific
# letters/words so the UI needs no translation. Each has a drawn fallback in
# render.py for environments without an emoji font.
ICON_PLAYER = "\U0001F464"   # 👤 player token   (was the letter "P")
ICON_HUNGER = "\U0001F60B"   # 😋 hunger         (was "H" / "Г")
ICON_COINS  = "\U0001F4B0"   # 💰 money          (was "деньги"/"COINS")
ICON_POWER  = "\u26A1"       # ⚡ power          (was "СИЛА"/"POWER")
ICON_CHECK  = "\u2705"       # ✅ completed-company badge

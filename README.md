# Building & Running "Degustator on X-7"

A pygame roguelike (serpentine board, dice movement, power/hunger/coins, items,
shop) that runs **natively on the desktop** and is packaged **for the web with
[Pygbag](https://pygbag.readthedocs.io/)** from the exact same `main.py`.

The core engine (`movement.py`, `game.py`, `player.py`, `items.py`,
`levels_data.py`, `config.py`, `persistence.py`) is data-driven from
`companies/*.json` / `items.json` and has no pygame dependency. `render.py` +
`main.py` are the rendering/UI/game loop layer built on top of it.

---

## 1. Run natively (desktop)

Requirements: **Python 3.10+** and **pygame** (or pygame-ce).

```bash
pip install pygame          # or: pip install pygame-ce
python main.py
```

A 800x600 window opens at the main menu. **Play** (or `Enter`) opens the
**company (campaign) selection** screen; pick one to start it at its first
level. Companies you have already cleared show a ✅ badge.

### Controls

| Screen | Keyboard | Mouse |
|---|---|---|
| Main menu | `Enter`/`Space` = Play, `T` = Tutorial, `L` = toggle EN/RU, `Esc` = quit | click the buttons |
| Company select | `1`..`9` = start that company, `Esc` = back | click a company / Back |
| Tutorial | `Esc` = back, `Up`/`Down` = scroll | wheel = scroll, click = back |
| Eat phase | `1`..`9` = eat inventory slot, `Enter` = continue | click an inventory row / **Done** |
| Move select | `1`..`n` = pick a die (greyed out if unaffordable) | click a die button |
| Dice roll | `Space` = skip the tumble animation | — |
| Landing choice | `1`..`k` = pick a highlighted cell | click a highlighted cell |
| Shop | `1`..`n` = buy, `Enter` = continue, `Up`/`Down` = scroll | wheel/click Buy, click Continue |
| Game over / Victory | any key = back to menu | click = back to menu |

---

## 2. Build for the web with Pygbag

Pygbag compiles the project to WebAssembly and bundles the whole project
directory into a virtual filesystem, so `open("levels.json")`,
`pygame.image.load("assets/images/...")`, etc. all work unchanged in the
browser.

### Install

```bash
pip install pygame-ce pygbag      # pygame-ce is recommended for the web
```

> Stock `pygame` also works; `pygame-ce` is preferred because its SDL/wasm
> build is better tuned for browsers.

### Develop (build + local serve)

From the project root (`degustator-on-x-7/`):

```bash
pygbag .
```

This builds the app and serves it at **http://localhost:8000** — open it in a
browser. Keep the command running while developing; rebuilds are picked up on
refresh.

### Produce a static build

```bash
pygbag --build .
```

Output is written under **`build/web/`** (an *appdir* containing `index.html`,
the bundled assets, and the compiled wasm/apk). Host the contents of that
folder on any static web server (GitHub Pages, Netlify, nginx, …).

### Useful flags

```bash
pygbag --title "Degustator on X-7" --ume_block 0 .
#  --title         sets the page <title>
#  --ume_block 0   do not block on module load (smoother boot)
#  --appdir PATH   force a fixed output directory
#  --build         produce a build instead of serving
```

Run `pygbag --help` for the full list.

---

## 3. Pygbag constraints (already honoured by this code)

These are the hard rules for a green web build — the code is written to comply:

1. **`async def main()`** is the entry point and the loop does
   `await asyncio.sleep(0)` every frame (see `main.py`). ✅
2. **No blocking sleeps.** Animations (dice tumble, token slide) are advanced
   by `dt` from `clock.tick(FPS)`; there is no `time.sleep` / `pygame.time.delay`
   in the loop. ✅
3. **No `tkinter`, no `PIL/Pillow`, no `doti18n`, no `threading`.** pygame +
   Python stdlib only. Localization is a small in-code table + optional
   `locales/*.json` read with stdlib `json`. ✅
4. **All asset/data paths are relative** to the project root, so Pygbag can
   bundle them: `levels.json`, `items.json`, `assets/...`, `locales/...`,
   `tutorial_*.txt`. ✅
5. **Lazy `pygame.mixer.init()`** on the first user gesture (browsers block
   audio until a key/click). Background music + sfx fail silently if missing. ✅
   **Audio must be OGG (`*.ogg`)** — browsers/Pygbag do **not** decode MP3
   (load raises `RuntimeError`). The repo ships OGG under `assets/sounds/` and
   the `.ogg` paths live in `config.py` (`MUSIC_BG`, `SFX_DAMAGE`, `SFX_NOM`).
   See [`README_BUILD.md`](README_BUILD.md).
6. **Emoji with a drawn fallback.** Stat labels (⚡ power, 😋 hunger, 💰 coins),
   the player token (👤), item chips (🍌 🍎 …) and the completed-company badge (✅)
   render as emoji via `pygame.freetype` (Segoe UI Emoji on Windows; bundle one
   for the web by setting `config.FONT_EMOJI_PATH`). Each glyph is validated and
   a missing "tofu" glyph falls back to a drawn primitive (bolt / mouth / coin /
   person / checkmark), so the UI never looks broken. `config.USE_EMOJI` toggles
   the emoji path (default on). ✅

---

## 4. Project layout (Pygbag-relevant)

```
degustator-on-x-7/
├── main.py                # Pygbag async entry (also `python main.py`)
├── engine/
│   ├── render.py          # drawing + emoji Icons + geometry/hit-test rects
│   ├── game.py            # headless run/company controller + state machine
│   ├── movement.py        # pure serpentine-DAG traversal engine
│   ├── player.py          # Player state
│   ├── items.py           # items.json loader (incl. per-item colour)
│   ├── levels_data.py     # LevelData + CompanyData loaders
│   ├── persistence.py     # finished-companies store (file + localStorage)
│   └── config.py          # window/colour/path/icon constants
├── companies/             # one <n>.json per campaign (n = company number)
│   ├── 1.json             # e.g. Tutorial
│   └── 2.json             # e.g. Desert
├── items.json             # item data (id, name_ru/en, icon, color, power, hunger, coins)
├── tutorial_en.txt / tutorial_ru.txt
├── tools/
│   ├── enable_web_save.py  # post-build patcher: persist progress across reloads
│   └── enable_web_music.py # post-build patcher: web-only looping BGM element
├── save/                  # runtime progress file (gitignored; created on play)
└── assets/{images,sounds}/...
```

The legacy `scripts/` package (the old tkinter/PIL prototype) is **not imported**
by the new code and is ignored by the build.

---

## 5. Companies & progress

Levels are grouped into **companies** (campaigns): one file per company in
`companies/<n>.json`, where the numeric filename stem is the company number and
display order. Each company file:

```json
{ "name_ru": "...", "name_en": "...",
  "levels": [ { "name_ru": "...", "name_en": "...", "rows": [[...]],
                "moves": [{"max_value":6,"power":1}],
                "start_parameters": {"power":3,"hunger":10},
                "shop_after_level": [{"item_id":4,"shop_cost":3}] } ] }
```

From the main menu, **Play** opens the company-select list (numbered, with
names); cleared companies show a ✅. Pick one (click or `1`–`9`) to start it.
Reaching VICTORY in a company records it as completed.

**Persistence.** Completed-company numbers are stored by `engine/persistence.py`:
on desktop this is `save/progress.json` (a real file). In a Pygbag web build the
working dir is in-memory and wiped on reload, so run the bundled patcher after
building to mirror that file to the browser `localStorage`:

```bash
pygbag --build .
python tools/enable_web_save.py build/web/index.html   # idempotent
python tools/enable_web_music.py build/web/index.html  # idempotent
```

The CI workflow (`.github/workflows/pygbag.yml`) already runs both patchers
before deploying to `gh-pages`, so the published build keeps progress across
reloads automatically. Each injected script is defensive: if it can't reach the
Emscripten FS it does nothing and the game still runs.

**Background music.** `pygame.mixer.music.play(-1)` is fine on desktop, but in a
Pygbag build it sits on the Web Audio API: when the tab is backgrounded the
`AudioContext` is suspended and on foreground resumed, which leaves pygbag's
loop with several overlapping copies of the track (the "music stacks on itself"
bug, worse every time you tab away). `main.py` therefore skips mixer music on
the web (`sys.platform == "emscripten"`) and `enable_web_music.py` injects a
plain `<audio loop>` element that owns the BGM instead — browsers pause/resume a
media element as a single instance, so it never duplicates. SFX still use the
mixer. (Desktop is unaffected.)

---

## 6. Verify locally before building

```bash
# 1) syntax check every engine module
python -c "import ast;[ast.parse(open(f,encoding='utf-8').read()) for f in ['main.py','engine/config.py','engine/items.py','engine/levels_data.py','engine/persistence.py','engine/movement.py','engine/player.py','engine/game.py','engine/render.py']]"
```

Then `pygbag .` and open http://localhost:8000.

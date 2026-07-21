# Building & Running "Degustator on X-7"

A pygame roguelike (serpentine board, dice movement, power/hunger/coins, items,
shop) that runs **natively on the desktop** and is packaged **for the web with
[Pygbag](https://pygbag.readthedocs.io/)** from the exact same `main.py`.

The core engine (`movement.py`, `game.py`, `player.py`, `items.py`,
`levels_data.py`, `config.py`) is data-driven from `levels.json` / `items.json`
and has no pygame dependency. `render.py` + `main.py` are the rendering/UI/game
loop layer built on top of it.

---

## 1. Run natively (desktop)

Requirements: **Python 3.10+** and **pygame** (or pygame-ce).

```bash
pip install pygame          # or: pip install pygame-ce
python main.py
```

A 800x600 window opens at the main menu. **Start Run** (or `Enter`) begins a
fresh run at Level 1.

### Controls

| Screen | Keyboard | Mouse |
|---|---|---|
| Main menu | `Enter`/`Space` = Start Run, `T` = Tutorial, `L` = toggle EN/RU, `Esc` = quit | click the buttons |
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
6. **No emoji dependency.** The player token, dice, HUD bars, arrows, stars and
   item chips are all drawn primitives or plain text (`config.USE_EMOJI`
   defaults off). ✅

---

## 4. Project layout (Pygbag-relevant)

```
degustator-on-x-7/
├── main.py              # Pygbag async entry (also `python main.py`)
├── render.py            # pure drawing helpers + geometry/hit-test rects
├── game.py              # headless run controller / state machine
├── movement.py          # pure serpentine-DAG traversal engine
├── player.py            # Player state
├── items.py             # items.json loader
├── levels_data.py       # levels.json loader
├── config.py            # window/colour/path constants
├── levels.json          # level data
├── items.json           # item data
├── tutorial_en.txt / tutorial_ru.txt
├── locales/{en,ru}.json
└── assets/{images,sounds,animations}/...
```

The legacy `scripts/` package (the old tkinter/PIL prototype) is **not imported**
by the new code and is ignored by the build.

---

## 5. Verify locally before building

```bash
# 1) syntax check every module
python -c "import ast;[ast.parse(open(f,encoding='utf-8').read()) for f in ['main.py','render.py','config.py','items.py','levels_data.py','movement.py','player.py','game.py']]"

# 2) core-engine regression (must stay green)
python test_movement.py
```

Then `pygbag .` and open http://localhost:8000.

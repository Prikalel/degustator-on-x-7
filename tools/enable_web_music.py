#!/usr/bin/env python3
"""enable_web_music.py — fix the "background music stacks on itself" web bug.

WHAT / WHY
----------
On the desktop, ``main.py`` plays the looping BGM through
``pygame.mixer.music.play(-1)`` and that is the end of the story.

In a **Pygbag** browser build that same call sits on top of the Web Audio API.
When the browser tab is backgrounded the ``AudioContext`` is **suspended**, and
on foreground it is **resumed**; pygbag's looping music then ends up with several
overlapping copies of the track — the melody literally "layers on itself", and
it gets worse every time you tab away and back. (Confirmed: ``play()`` is called
exactly once from Python; the duplication happens below pygame, on resume.)

THE FIX
-------
Stop using ``pygame.mixer.music`` for the BGM inside the browser and instead let
a plain ``<audio loop>`` HTML element own it. Browsers pause/resume a media
element as a **single instance** across tab switches, so it never duplicates and
never produces the audible "corrupt" restarts that a naive stop+play recovery
caused. ``main.py`` already skips ``pygame.mixer.music.play()`` when
``sys.platform == "emscripten"``; this script supplies the element that takes
over, reading the OGG straight out of pygbag's in-memory FS (MEMFS) — the very
same bytes ``pygame.mixer.music.load`` would have read — and feeding them to the
``<audio>`` element as a Blob URL. SFX keep using ``pygame.mixer`` as before.

USAGE
-----
Build the web app as usual, then run this once on the generated index.html::

    pygbag --build .
    python tools/enable_web_save.py            # (if you also want save persistence)
    python tools/enable_web_music.py           # <-- this one
    # or:  python tools/enable_web_music.py path/to/index.html

It is idempotent (re-running is a no-op) and degrades gracefully: if the
Emscripten FS object is not found at runtime, the injected script simply does
nothing (no BGM) and the game otherwise runs normally.

NOTE: only needed for the WEB build. The desktop ``python main.py`` path needs
nothing — its BGM is handled by ``pygame.mixer.music`` directly.
"""
from __future__ import annotations

import glob
import os
import sys

MARKER = "degustator-bgm-sync"

# An <audio loop> element + a tiny controller. It reads the OGG from MEMFS
# (feature-detecting the Emscripten FS several ways, like enable_web_save),
# turns the bytes into a Blob URL, and plays on the first user gesture so it
# respects the browser autoplay policy. Volume mirrors the desktop value (0.35).
SNIPPET = """
<audio id="degustator-bgm" loop preload="auto"></audio>
<script id="degustator-bgm-sync">
(function(){
  var PATH="assets/sounds/background-music.ogg", VOL=0.35;
  var el=document.getElementById("degustator-bgm");
  if(!el){return;}
  function getFS(){
    try{return (window.Module&&window.Module.FS)||window.FS||(window.pygame&&window.pygame.FS)||(window._module&&window._module.FS);}
    catch(e){return null;}
  }
  var srcReady=false;
  function tryLoadSrc(){
    if(srcReady){return true;}
    var FS=getFS();
    if(!FS||!FS.readFile){return false;}
    var bytes;
    try{bytes=FS.readFile(PATH);}catch(e){return false;}   // MEMFS not mounted yet
    try{
      var blob=new Blob([bytes],{type:"audio/ogg"});
      el.src=URL.createObjectURL(blob);
      el.volume=VOL;
      srcReady=true;
      return true;
    }catch(e){return false;}
  }
  // The MEMFS data archive is mounted asynchronously; keep polling until the
  // OGG is readable, then we have a stable src for the element.
  var iv=setInterval(function(){ if(tryLoadSrc()){clearInterval(iv);} }, 300);
  // Browsers block autoplay until a user gesture, so start playback on the first
  // pointer/keyboard interaction (mirrors the lazy audio init in main.py).
  function playIfReady(){
    if(tryLoadSrc()){
      var p=el.play();
      if(p&&p.catch){p.catch(function(){});}
    }
  }
  window.addEventListener("pointerdown", playIfReady);
  window.addEventListener("keydown", playIfReady);
})();
</script>
"""


def find_index(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    # Common Pygbag build outputs.
    candidates = ["build/web/index.html"]
    candidates += sorted(glob.glob("build/**/index.html", recursive=True))
    candidates += sorted(glob.glob("**/index.html", recursive=True))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def patch(path: str) -> bool:
    with open(path, "r", encoding="utf-8") as fh:
        html = fh.read()
    if MARKER in html:
        print(f"[enable_web_music] already patched: {path}")
        return False
    if "</body>" in html:
        html = html.replace("</body>", SNIPPET + "\n</body>", 1)
    elif "</html>" in html:
        html = html.replace("</html>", SNIPPET + "\n</html>", 1)
    else:
        html = html + "\n" + SNIPPET
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[enable_web_music] patched: {path}")
    return True


def main(argv):
    explicit = argv[1] if len(argv) > 1 else None
    path = find_index(explicit)
    if not path:
        print("[enable_web_music] ERROR: no index.html found. Run `pygbag --build .` "
              "first, or pass the path: python tools/enable_web_music.py path/index.html")
        return 1
    patch(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

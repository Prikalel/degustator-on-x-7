#!/usr/bin/env python3
"""enable_web_save.py — make company-completion progress survive a page reload.

WHAT / WHY
----------
The game records finished companies through ``engine/persistence.py`` which
writes a tiny JSON file (``save/progress.json``) using plain ``open()``. On the
**desktop** that is a real file, so it persists for free.

In a **Pygbag** browser build the working directory lives in Emscripten's
in-memory FS (MEMFS), which is wiped on every reload — so by default the web
build "forgets" your progress. This script injects a small, defensive
``<script>`` into the built ``index.html`` that keeps that MEMFS file in sync
with the browser's ``localStorage`` (which DOES persist). After running it,
clearing a company and reloading the page keeps the ✅ badge.

USAGE
-----
Build the web app as usual, then run this once on the generated index.html::

    pygbag --build .
    python tools/enable_web_save.py            # patches build/web/index.html
    # or:  python tools/enable_web_save.py path/to/index.html

It is idempotent (re-running is a no-op) and never breaks the build: if it
cannot find the Emscripten FS object at runtime, the sync script simply does
nothing and the game runs normally (just without cross-reload persistence).

NOTE: only needed for the WEB build. The desktop ``python main.py`` path needs
nothing — ``save/progress.json`` is written to the project directory directly.
"""
from __future__ import annotations

import glob
import os
import sys

MARKER = "degustator-save-sync"

# The injected script keeps save/progress.json (MEMFS) <-> localStorage in sync.
# It feature-detects the Emscripten FS several ways and degrades gracefully.
SCRIPT = """<script id="degustator-save-sync">
(function(){
  var KEY="degustator_x7_completed_v1", PATH="save/progress.json";
  function getFS(){try{return (window.Module&&window.Module.FS)||window.FS||(window.pygame&&window.pygame.FS)||(window._module&&window._module.FS);}catch(e){return null;}}
  function lsGet(){try{var v=localStorage.getItem(KEY);return (v==null)?null:v;}catch(e){return null;}}
  function lsSet(s){try{localStorage.setItem(KEY,s);}catch(e){}}
  function memRead(){var FS=getFS();if(!FS||!FS.readFile)return null;try{var d=FS.readFile(PATH,{encoding:"utf8"});return (typeof d==="string")?d:new TextDecoder().decode(d);}catch(e){return null;}}
  function memWrite(s){var FS=getFS();if(!FS||!FS.writeFile)return false;try{try{FS.mkdir("save");}catch(e){}FS.writeFile(PATH,s);return true;}catch(e){return false;}}
  var seeded=false;
  function step(){
    if(!seeded){var v=lsGet();if(v!=null&&memWrite(v)){seeded=true;}}
    var m=memRead();
    if(m!=null){if(lsGet()!==m){lsSet(m);}}
    else{var v=lsGet();if(v!=null){memWrite(v);}}
  }
  if(document.readyState==="complete"||document.readyState==="interactive"){step();}
  setInterval(step,500);
})();
</script>"""


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
        print(f"[enable_web_save] already patched: {path}")
        return False
    if "</body>" in html:
        html = html.replace("</body>", SCRIPT + "\n</body>", 1)
    elif "</html>" in html:
        html = html.replace("</html>", SCRIPT + "\n</html>", 1)
    else:
        html = html + "\n" + SCRIPT
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[enable_web_save] patched: {path}")
    return True


def main(argv):
    explicit = argv[1] if len(argv) > 1 else None
    path = find_index(explicit)
    if not path:
        print("[enable_web_save] ERROR: no index.html found. Run `pygbag --build .` "
              "first, or pass the path: python tools/enable_web_save.py path/index.html")
        return 1
    patch(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

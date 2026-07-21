"""persistence.py — remember which companies the player has already cleared.

A "completed company" is recorded the moment the player reaches VICTORY in it.
The store is best-effort and never raises into the game loop:

  * **Web (Pygbag):** tries the browser ``localStorage`` via the optional ``js``
    bridge (Pyodide-style; available when the runtime exposes it). If that is
    unavailable it falls through to the file path below.
  * **File (always):** a tiny JSON file at ``config.SAVE_PATH``
    (``save/progress.json``). On desktop this is a normal file (persists). On
    the web it lives in the Emscripten virtual FS and persists across reloads
    **only** when the build mounts an IndexedDB-backed FS there — see the
    bundled ``app_template.html`` and README build notes.

Everything is guarded: a missing/unwritable store simply degrades to in-memory
storage for the current session. Nothing here ever blocks or throws to callers.
"""

from __future__ import annotations

import json
import os
from typing import Iterable, Optional, Set

import config

# localStorage key (used only on runtimes that expose a `js` bridge).
_LS_KEY = "degustator_x7_completed_v1"

# In-memory source of truth for the current process (loaded once, then mutated).
_cache: Optional[Set[int]] = None


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------
def is_web() -> bool:
    """True when running inside an Emscripten / browser runtime (Pygbag)."""
    import sys
    if sys.platform == "emscripten":
        return True
    try:
        import platform
        return platform.system() == "Emscripten"
    except Exception:
        return False


def _try_js():
    """Return a small localStorage shim if a ``js`` bridge is available, else None."""
    try:
        import js  # type: ignore  # noqa: F401  (Pyodide; absent under Pygbag)
        ls = js.window.localStorage
    except Exception:
        return None

    class _LS:
        @staticmethod
        def get() -> Optional[str]:
            try:
                v = ls.getItem(_LS_KEY)
                return str(v) if v is not None else None
            except Exception:
                return None

        @staticmethod
        def set(raw: str) -> None:
            try:
                ls.setItem(_LS_KEY, raw)
            except Exception:
                pass

    return _LS()


# ---------------------------------------------------------------------------
# File backend
# ---------------------------------------------------------------------------
def _read_file() -> Optional[str]:
    try:
        with open(config.SAVE_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _write_file(raw: str) -> None:
    try:
        os.makedirs(config.SAVE_DIR, exist_ok=True)
        with open(config.SAVE_PATH, "w", encoding="utf-8") as fh:
            fh.write(raw)
    except Exception:
        pass  # read-only FS / no quota — degrade silently to in-memory.


def _decode(raw: Optional[str]) -> Set[int]:
    if not raw:
        return set()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            vals = data.get("completed", [])
        else:
            vals = data
        return {int(v) for v in vals}
    except Exception:
        return set()


def _encode(ids: Iterable[int]) -> str:
    return json.dumps({"completed": sorted({int(i) for i in ids})})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_completed() -> Set[int]:
    """Load the completed-company set (cached after first call).

    Prefers the ``js`` localStorage bridge; falls back to the JSON file.
    """
    global _cache
    if _cache is not None:
        return _cache

    ids: Set[int] = set()
    ls = _try_js()
    if ls is not None:
        ids |= _decode(ls.get())
    ids |= _decode(_read_file())
    _cache = ids
    return ids


def save_completed(ids: Iterable[int]) -> None:
    """Persist the given completed-company set to every available backend."""
    global _cache
    norm = {int(i) for i in ids}
    _cache = norm
    raw = _encode(norm)
    _write_file(raw)
    ls = _try_js()
    if ls is not None:
        ls.set(raw)


def mark_completed(company_number: int) -> None:
    """Record a company as cleared and persist immediately (idempotent)."""
    ids = load_completed()
    if company_number in ids:
        return
    ids.add(int(company_number))
    save_completed(ids)


def is_completed(company_number: int) -> bool:
    return int(company_number) in load_completed()


def reset_progress() -> None:
    """Clear all recorded progress (used by a debug/reset hook, if ever needed)."""
    save_completed(set())

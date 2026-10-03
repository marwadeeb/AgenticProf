"""Generic JavaScript assets and the wrapper that is applied identically in the page and the checker."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
WRAP_PRE = "var MODEL = (function (V, P2P) {\n"
WRAP_POST = (
    "\n;return {"
    "compute: typeof compute === 'function' ? compute : null, "
    "view: typeof view === 'function' ? view : null, "
    "readout: typeof readout === 'function' ? readout : null, "
    "insight: typeof insight === 'function' ? insight : null, "
    "tests: (typeof TESTS !== 'undefined' && Array.isArray(TESTS)) ? TESTS : [], invariants: (typeof INVARIANTS !== 'undefined' && Array.isArray(INVARIANTS)) ? INVARIANTS : []"
    "};\n})(V, P2P);\n"
)
CODE_LINE_OFFSET = WRAP_PRE.count("\n")


@lru_cache(maxsize=None)
def asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def wrap_model(code: str) -> str:
    return WRAP_PRE + (code or "") + WRAP_POST

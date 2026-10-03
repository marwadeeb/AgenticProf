"""Deterministic, zero-token checks: static code/page checks and executable checks of the generated
JavaScript (run in QuickJS in a subprocess with a timeout)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import jsbundle

JSCHECK = Path(__file__).resolve().parent / "jscheck.py"

_FORBIDDEN = [
    (re.compile(r"\bfetch\s*\("), "CODE calls fetch(); the page must work offline."),
    (re.compile(r"\bXMLHttpRequest\b|\bWebSocket\b"), "CODE opens a network connection; the page must work offline."),
    (re.compile(r"^\s*(import|export)\s", re.M), "CODE uses import/export; write plain top-level functions."),
    (re.compile(r"\brequire\s*\("), "CODE calls require(); no modules are available."),
    (re.compile(r"\bdocument\s*\.|\bwindow\s*\."), "CODE touches document/window; compute/view must be pure and return values or SVG strings."),
    (re.compile(r"\b(localStorage|sessionStorage|indexedDB)\b"), "CODE uses browser storage."),
    (re.compile(r"(?:src|href)\s*=\s*[\"']?\s*(?:https?:)?//", re.I), "CODE references a remote resource (src/href to a URL)."),
]
_FRAME = re.compile(r"at ([^\s()]+) \(([^()]*?):(\d+)(?::\d+)?\)")
_BARE = re.compile(r"\bat (<[^>\s]+>|[\w.\-]+):(\d+)(?::\d+)?")


def engine_available() -> bool:
    try:
        return importlib.util.find_spec("quickjs") is not None
    except (ImportError, ValueError):
        return False


def explain_js_error(msg: str, code: str) -> str:
    """Map QuickJS stack frames to CODE line numbers and quote the first offending line."""
    lines = (code or "").split("\n")
    first = []

    def model_line(n: int) -> int:
        cl = n - jsbundle.CODE_LINE_OFFSET
        if 1 <= cl <= len(lines) and not first:
            first.append(cl)
        return cl

    def frame(m):
        fn = m.group(1)
        if fn.startswith("v_"):
            return "inside helper V." + fn[2:] + "()"
        if fn.startswith("p2p_") or fn.startswith("__h") or fn == "<eval>":
            return ""
        return "at " + fn + " (CODE line " + str(model_line(int(m.group(3)))) + ")"

    out = _FRAME.sub(frame, msg or "")
    out = _BARE.sub(lambda m: "at CODE line " + str(model_line(int(m.group(2)))), out)
    out = re.sub(r"\s+", " ", out).strip()
    if first:
        out += " | CODE line " + str(first[0]) + ": " + lines[first[0] - 1].strip()[:160]
    return out[:800]


def static_code_checks(code: str):
    fails, warns = [], []
    if not (code or "").strip():
        return ["CODE is empty: define compute, view, readout, insight and TESTS."], warns
    for rx, msg in _FORBIDDEN:
        if rx.search(code):
            fails.append(msg)
    if re.search(r"\bMath\.random\s*\(", code):
        warns.append("CODE uses Math.random(); results should be deterministic.")
    if len(code) > 60000:
        warns.append("CODE is very long; keep it compact.")
    return fails, warns


def _empty_result():
    return {"engine": None, "failures": [], "warnings": [], "fatal": False, "tests": [], "active": [],
            "inert": [], "visual_active": None, "cases": 0, "duration_s": 0.0}


def run_js_checks(spec: dict, code: str, timeout: float = 60.0) -> dict:
    res = _empty_result()
    payload = {
        "lib": jsbundle.asset("vlib.js"),
        "harness": jsbundle.asset("harness.js"),
        "wrapped": jsbundle.wrap_model(code),
        "time_limit": max(2, int(timeout) - 5),
        "cfg": {"controls": spec.get("controls", []),
                "presets": [e.get("preset", {}) for e in spec.get("explorations", [])]},
    }
    t = time.monotonic()
    fd, path = tempfile.mkstemp(prefix="p2p_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        try:
            proc = subprocess.run([sys.executable, str(JSCHECK), path], capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            res.update(engine="quickjs", fatal=True, duration_s=round(time.monotonic() - t, 2))
            res["failures"].append("Executing CODE exceeded %.0f s (likely an unbounded loop); keep loops bounded and small." % timeout)
            return res
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    res["duration_s"] = round(time.monotonic() - t, 2)
    out = proc.stdout.decode("utf-8", "replace").strip()
    rep = None
    if out:
        try:
            rep = json.loads(out)
        except json.JSONDecodeError:
            try:
                rep = json.loads(out.splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                rep = None
    if not isinstance(rep, dict):
        res.update(engine="quickjs", fatal=True)
        err = proc.stderr.decode("utf-8", "replace").strip()[-300:]
        res["failures"].append(("The JavaScript checker crashed (exit code %s); possible runaway recursion or memory use. %s"
                                % (proc.returncode, err)).strip())
        return res
    return _interpret(rep, code, res)


def _interpret(rep: dict, code: str, res: dict) -> dict:
    res["engine"] = rep.get("engine")
    if not res["engine"]:
        res["warnings"].append("Executable JS checks skipped (" + str(rep.get("error", "engine unavailable"))
                               + "); static checks only. The page still re-runs TESTS in the browser.")
        return res
    if rep.get("load_error"):
        res["failures"].append("CODE fails to load: " + explain_js_error(rep["load_error"], code))
        res["fatal"] = True
        return res
    if rep.get("run_error"):
        res["failures"].append("Running CODE failed: " + explain_js_error(rep["run_error"], code))
        res["fatal"] = True
        return res
    res["failures"] += [explain_js_error(e, code) for e in rep.get("errors", [])]
    res["warnings"] += [explain_js_error(w, code) for w in rep.get("warnings", [])]
    if rep.get("suppressed"):
        res["warnings"].append("%d further similar issues suppressed." % rep["suppressed"])
    res["fatal"] = bool(rep.get("fatal"))
    res["cases"] = rep.get("cases", 0)
    for t in rep.get("tests", []):
        item = {"name": str(t.get("name")), "pass": bool(t.get("pass"))}
        if t.get("error"):
            item["error"] = explain_js_error(t["error"], code)
        res["tests"].append(item)
        if not item["pass"]:
            res["failures"].append('TEST "' + item["name"] + '" failed'
                                   + (": " + item["error"] if item.get("error") else " (check returned false)."))
    if not res["tests"]:
        res["failures"].append("No TESTS were defined; add 3-6 executable checks (const TESTS = [...]).")
    elif len(res["tests"]) < 3:
        res["warnings"].append("Only %d TESTS defined; 3-6 are expected." % len(res["tests"]))
    res["invariants"] = rep.get("invariants", 0)
    if not res["invariants"]:
        res["warnings"].append("No INVARIANTS defined; add 1-3 properties that hold for every input (shown live on the page).")
    res["active"], res["inert"] = rep.get("active", []), rep.get("inert", [])
    res["visual_active"] = bool(rep.get("visualActive"))
    if not res["fatal"]:
        if len(res["active"]) < 2:
            res["failures"].append("Only %d control(s) change the visual or readouts (active: %s; no effect: %s). At least two controls must visibly change the output."
                                   % (len(res["active"]), ", ".join(res["active"]) or "none", ", ".join(res["inert"]) or "none"))
        elif res["inert"]:
            res["warnings"].append("Controls with no visible effect: " + ", ".join(res["inert"]) + ".")
        if not res["visual_active"]:
            res["failures"].append("The SVG visual never changes when a control changes; make view() depend on the inputs and computed result.")
    svg = rep.get("svgDefault") or ""
    if svg:
        try:
            ET.fromstring(svg)
        except ET.ParseError as exc:
            res["warnings"].append("Default SVG is not well-formed XML (" + str(exc) + ").")
        if len(svg) > 300000:
            res["warnings"].append("Default SVG is very large; simplify the drawing.")
    return res


def static_html_checks(html: str):
    fails, warns = [], []
    patterns = [
        (r"<(?:script|link|img|iframe|source|video|audio|embed|object)\b[^>]*\b(?:src|href|data)\s*=\s*[\"']?\s*(?:https?:)?//",
         "page loads a remote resource"),
        (r"url\(\s*[\"']?\s*(?:https?:)?//", "CSS references a remote url()"),
        (r"@import\b", "CSS @import found"),
        (r"sk-or-[A-Za-z0-9]", "possible API key in page"),
    ]
    for rx, msg in patterns:
        if re.search(rx, html, re.I):
            fails.append(msg)
    for needed in ('id="p2p-controls"', 'id="p2p-visual"', 'id="p2p-readout"', 'data-explore="0"',
                   'data-explore="1"', 'id="p2p-tests"', 'id="source"'):
        if needed not in html:
            fails.append("page is missing " + needed)
    if "{{" in html and re.search(r"\{\{[A-Z_]+\}\}", html):
        warns.append("unreplaced template placeholder")
    return fails, warns

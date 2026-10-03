"""Validate and normalise the model's SPEC so the template can rely on its structure.

normalize_spec(raw, case) -> (spec | None, problems, notes)
  problems: must be fixed (they trigger a repair round)
  notes:    auto-fixed or minor issues (logged; passed along if a repair happens anyway)"""
from __future__ import annotations

import math
import re

SPEC_KEYS = ("plan", "title", "paper", "idea", "why", "equation", "symbols", "controls",
             "visual_caption", "explorations", "caveats", "misconception", "grounding")
CAVEAT_KINDS = ("Assumption", "Limitation", "Common misunderstanding")
CONTROL_TYPES = ("slider", "number", "select", "toggle", "vector", "matrix")
TYPE_ALIASES = {
    "range": "slider", "int": "number", "integer": "number", "float": "number", "input": "number",
    "numeric": "number", "checkbox": "toggle", "bool": "toggle", "boolean": "toggle", "switch": "toggle",
    "dropdown": "select", "choice": "select", "radio": "select", "enum": "select",
    "array": "vector", "list": "vector", "grid": "matrix", "table": "matrix",
}
UNSAFE_IDS = frozenset(("__proto__", "constructor", "prototype", "hasOwnProperty", "toString", "valueOf"))
ID_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,39}$")
MAX_DIM = 16
MAX_CONTROLS = 8
TRUE_WORDS = (True, 1, "true", "True", "on", "1", "yes")


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, str):
        try:
            v = float(x.strip())
        except ValueError:
            return None
        return v if math.isfinite(v) else None
    return None


def _clean(v):
    if v is None:
        return None
    v = float(v)
    return int(v) if v.is_integer() and abs(v) < 1e15 else v


def _text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, (list, tuple)):
        return " ".join(t for t in (_text(i) for i in x) if t)
    if isinstance(x, dict):
        return "; ".join(str(k) + ": " + _text(v) for k, v in x.items())
    return str(x).strip()


def _list(x) -> list:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return [t for t in (_text(i) for i in x) if t]
    t = _text(x)
    return [t] if t else []


def _nice_step(span):
    if not span or span <= 0:
        return 1
    raw = span / 100.0
    p = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * p * 1.000001:
            return _clean(float("%.12g" % (m * p)))
    return 1


def _dim(x, fallback):
    if isinstance(x, str) and x.strip() and _num(x) is None:
        return x.strip()
    n = _num(x)
    n = fallback if n is None else n
    return max(1, min(MAX_DIM, int(round(n))))


def _range(c, values, cid, notes):
    lo, hi, st = _num(c.get("min")), _num(c.get("max")), _num(c.get("step"))
    flat = values or [0.0]
    if lo is None or hi is None:
        vmin, vmax = min(flat), max(flat)
        span = (vmax - vmin) or max(1.0, abs(vmax))
        if lo is None:
            lo = 0.0 if vmin >= 0 else vmin - span
        if hi is None:
            hi = vmax + span
        notes.append('Control "%s" had no min/max; using [%g, %g].' % (cid, lo, hi))
    if lo >= hi:
        notes.append('Control "%s": min >= max; widened.' % cid)
        hi = lo + 1.0
    if st is None or st <= 0:
        st = _nice_step(hi - lo)
    return lo, hi, st


def _fill(c, lo, hi):
    f = _num(c.get("fill"))
    if f is not None:
        return f
    return 0.0 if lo <= 0 <= hi else lo


def _control(c, idx, problems, notes):
    if not isinstance(c, dict):
        problems.append("SPEC.controls[%d] is not an object." % idx)
        return None
    raw_type = str(c.get("type", "")).strip().lower()
    t = TYPE_ALIASES.get(raw_type, raw_type)
    cid = str(c.get("id", "")).strip()
    if not ID_RE.match(cid) or cid in UNSAFE_IDS:
        problems.append('SPEC.controls[%d] has invalid id "%s" (use a short JavaScript identifier).' % (idx, cid))
        return None
    if t not in CONTROL_TYPES:
        problems.append('SPEC.controls: "%s" has unsupported type "%s" (use one of %s).' % (cid, raw_type, ", ".join(CONTROL_TYPES)))
        return None
    o = {"type": t, "id": cid, "label": _text(c.get("label")) or cid}
    if _text(c.get("help")):
        o["help"] = _text(c.get("help"))
    if t in ("slider", "number"):
        lo, hi, st, v = _num(c.get("min")), _num(c.get("max")), _num(c.get("step")), _num(c.get("value"))
        if lo is None or hi is None:
            problems.append('SPEC.controls: %s "%s" needs numeric "min" and "max".' % (t, cid))
            return None
        if lo >= hi:
            problems.append('SPEC.controls: "%s" needs min < max.' % cid)
            return None
        if st is None or st <= 0:
            st = _nice_step(hi - lo)
        if v is None:
            v = lo
        if v < lo or v > hi:
            notes.append('Control "%s": default %g clamped into [%g, %g].' % (cid, v, lo, hi))
            v = min(max(v, lo), hi)
        o.update(min=_clean(lo), max=_clean(hi), step=_clean(st), value=_clean(v))
    elif t == "toggle":
        o["value"] = c.get("value") in TRUE_WORDS
    elif t == "select":
        opts = []
        for op in c.get("options") or []:
            if isinstance(op, dict) and "value" in op and not isinstance(op["value"], (dict, list)):
                opts.append({"value": op["value"], "label": _text(op.get("label")) or str(op["value"])})
            elif isinstance(op, (str, int, float)) and not isinstance(op, bool):
                opts.append({"value": op, "label": str(op)})
        keys = [str(x["value"]) for x in opts]
        if len(opts) < 2 or len(set(keys)) != len(keys):
            problems.append('SPEC.controls: select "%s" needs at least 2 options with distinct values.' % cid)
            return None
        v = c.get("value")
        o["options"] = opts
        o["value"] = opts[keys.index(str(v))]["value"] if str(v) in keys else opts[0]["value"]
    elif t == "vector":
        val = c.get("value", c.get("values"))
        if not isinstance(val, list):
            problems.append('SPEC.controls: vector "%s" needs "value" as a list of numbers.' % cid)
            return None
        nums = [_num(x) for x in val]
        if any(x is None for x in nums):
            notes.append('Vector "%s": non-numeric entries replaced by 0.' % cid)
            nums = [0.0 if x is None else x for x in nums]
        lo, hi, st = _range(c, nums, cid, notes)
        fill = _fill(c, lo, hi)
        length = _dim(c.get("length"), len(nums) or 1)
        if isinstance(length, int):
            if nums and len(nums) != length:
                notes.append('Vector "%s": value resized to length %d.' % (cid, length))
            nums = (nums + [fill] * length)[:length]
        elif not nums:
            nums = [fill]
        o.update(length=length, min=_clean(lo), max=_clean(hi), step=_clean(st), fill=_clean(fill),
                 value=[_clean(x) for x in nums[:MAX_DIM]])
        if _list(c.get("labels")):
            o["labels"] = _list(c.get("labels"))
    else:
        val = c.get("value", c.get("values"))
        if not isinstance(val, list) or not val or not all(isinstance(r, list) for r in val):
            problems.append('SPEC.controls: matrix "%s" needs "value" as a list of rows (lists of numbers).' % cid)
            return None
        rows_v = [[(_num(x) if _num(x) is not None else 0.0) for x in r] for r in val]
        lo, hi, st = _range(c, [x for r in rows_v for x in r], cid, notes)
        fill = _fill(c, lo, hi)
        ncols = max((len(r) for r in rows_v), default=1) or 1
        rows, cols = _dim(c.get("rows"), len(rows_v)), _dim(c.get("cols"), ncols)
        nr = rows if isinstance(rows, int) else min(len(rows_v), MAX_DIM)
        nc = cols if isinstance(cols, int) else min(ncols, MAX_DIM)
        rows_v = [(r + [fill] * nc)[:nc] for r in (rows_v + [[] for _ in range(nr)])[:nr]]
        o.update(rows=rows, cols=cols, min=_clean(lo), max=_clean(hi), step=_clean(st), fill=_clean(fill),
                 value=[[_clean(x) for x in r] for r in rows_v])
        if _list(c.get("row_labels")):
            o["row_labels"] = _list(c.get("row_labels"))
        if _list(c.get("col_labels")):
            o["col_labels"] = _list(c.get("col_labels"))
    return o


def _link_dims(controls, problems, notes):
    byid = {c["id"]: c for c in controls}
    for c in controls:
        if c["type"] not in ("vector", "matrix"):
            continue
        for key in (("length",) if c["type"] == "vector" else ("rows", "cols")):
            ref = c.get(key)
            if not isinstance(ref, str):
                continue
            r = byid.get(ref)
            ok = (r is not None and r["type"] in ("slider", "number") and float(r["step"]).is_integer()
                  and float(r["min"]).is_integer() and r["min"] >= 1)
            if not ok:
                problems.append('SPEC.controls: "%s".%s = "%s" must name an integer slider with min >= 1 and an integer step.'
                                % (c["id"], key, ref))
                c[key] = len(c["value"]) if key in ("length", "rows") else len(c["value"][0])
                continue
            if r["max"] > MAX_DIM:
                notes.append('Slider "%s": max reduced to %d.' % (ref, MAX_DIM))
                r["max"] = MAX_DIM
                r["value"] = min(r["value"], MAX_DIM)
            n = max(1, int(round(r["value"])))
            fill = c["fill"]
            if c["type"] == "vector":
                c["value"] = (c["value"] + [fill] * n)[:n]
            elif key == "rows":
                k = len(c["value"][0]) if c["value"] else 1
                c["value"] = (c["value"] + [[fill] * k for _ in range(n)])[:n]
            else:
                c["value"] = [(row + [fill] * n)[:n] for row in c["value"]]


def _preset(pre, byid, n, notes):
    out = {}
    if not isinstance(pre, dict):
        return out
    for k, v in pre.items():
        c = byid.get(k)
        if c is None:
            notes.append('Exploration %d: preset key "%s" is not a control id (ignored).' % (n, k))
            continue
        t = c["type"]
        if t in ("slider", "number"):
            x = _num(v)
            if x is None:
                notes.append('Exploration %d: preset "%s" is not a number (ignored).' % (n, k))
                continue
            if x < c["min"] or x > c["max"]:
                notes.append('Exploration %d: preset "%s" clamped into range.' % (n, k))
                x = min(max(x, c["min"]), c["max"])
            out[k] = _clean(x)
        elif t == "toggle":
            out[k] = v in TRUE_WORDS
        elif t == "select":
            keys = [str(o["value"]) for o in c["options"]]
            if str(v) in keys:
                out[k] = c["options"][keys.index(str(v))]["value"]
            else:
                notes.append('Exploration %d: preset "%s" is not one of the options (ignored).' % (n, k))
        elif t == "vector" and isinstance(v, list):
            out[k] = [(_clean(_num(x)) if _num(x) is not None else 0) for x in v][:MAX_DIM]
        elif t == "matrix" and isinstance(v, list) and v and all(isinstance(r, list) for r in v):
            out[k] = [[(_clean(_num(x)) if _num(x) is not None else 0) for x in r][:MAX_DIM] for r in v][:MAX_DIM]
        else:
            notes.append('Exploration %d: preset "%s" has the wrong shape (ignored).' % (n, k))
    return out


def _symbols(syms):
    out = []
    if isinstance(syms, dict):
        syms = [{"sym": k, "meaning": v} for k, v in syms.items()]
    for it in syms if isinstance(syms, list) else []:
        if isinstance(it, dict):
            sym = it.get("sym") or it.get("symbol") or it.get("name")
            mean = it.get("meaning") or it.get("description") or it.get("desc")
        elif isinstance(it, (list, tuple)) and len(it) >= 2:
            sym, mean = it[0], it[1]
        else:
            continue
        if _text(sym) and _text(mean):
            out.append({"sym": _text(sym), "meaning": _text(mean)})
    return out[:20]


def normalize_spec(raw, case):
    problems, notes = [], []
    if not isinstance(raw, dict):
        return None, ["SPEC is not a JSON object."], []
    case = case or {}
    s = {"plan": _text(raw.get("plan"))}
    s["title"] = _text(raw.get("title")) or _text(case.get("title")) or "Interactive explainer"
    paper = raw.get("paper") if isinstance(raw.get("paper"), dict) else {}
    s["paper"] = {k: _text(paper.get(k)) for k in ("title", "authors", "year", "section")}
    s["paper"]["url"] = _text(case.get("source_url")) or _text(paper.get("url"))
    if not s["paper"]["section"]:
        notes.append("SPEC.paper.section is empty; cite the section/equation explained.")
    for k in ("idea", "why", "equation", "visual_caption"):
        s[k] = _text(raw.get(k))
    if not s["idea"]:
        problems.append("SPEC.idea is empty.")
    if not s["equation"]:
        notes.append("SPEC.equation is empty.")
    s["symbols"] = _symbols(raw.get("symbols"))
    if not s["symbols"]:
        notes.append("SPEC.symbols is empty; define the main symbols.")
    controls = []
    for i, c in enumerate(raw.get("controls") if isinstance(raw.get("controls"), list) else []):
        o = _control(c, i, problems, notes)
        if o is not None:
            controls.append(o)
    ids = [c["id"] for c in controls]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        problems.append("SPEC.controls: duplicate ids " + ", ".join(dup) + ".")
        seen = set()
        controls = [c for c in controls if not (c["id"] in seen or seen.add(c["id"]))]
    if len(controls) > MAX_CONTROLS:
        notes.append("SPEC.controls: only the first %d controls are kept." % MAX_CONTROLS)
        controls = controls[:MAX_CONTROLS]
    _link_dims(controls, problems, notes)
    if len(controls) < 2:
        problems.append("SPEC.controls: at least 2 working controls are required (got %d)." % len(controls))
    s["controls"] = controls
    byid = {c["id"]: c for c in controls}
    ex_out = []
    for e in raw.get("explorations") if isinstance(raw.get("explorations"), list) else []:
        if not isinstance(e, dict):
            continue
        n = len(ex_out) + 1
        item = {k: _text(e.get(k)) for k in ("title", "change", "observe", "why", "then")}
        missing = [k for k in ("change", "observe", "why") if not item[k]]
        if missing:
            problems.append("SPEC.explorations[%d] is missing: %s." % (n, ", ".join(missing)))
        item["title"] = item["title"] or "Exploration %d" % n
        item["preset"] = _preset(e.get("preset"), byid, n, notes)
        ex_out.append(item)
        if len(ex_out) == 2:
            break
    if len(ex_out) < 2:
        problems.append("SPEC.explorations: exactly 2 are required (got %d)." % len(ex_out))
    s["explorations"] = ex_out
    # Caveats: the brief requires at least one limitation, assumption or misunderstanding; we ask for one of
    # each. Older single-item "misconception" output is still accepted.
    cav = []
    raw_cav = raw.get("caveats")
    if isinstance(raw_cav, dict):
        raw_cav = [{"kind": k, "text": v} for k, v in raw_cav.items()]
    for c in raw_cav if isinstance(raw_cav, list) else []:
        if isinstance(c, str):
            c = {"kind": "Limitation", "text": c}
        if isinstance(c, dict) and _text(c.get("text")):
            cav.append({"kind": (_text(c.get("kind")) or "Limitation")[:60], "text": _text(c.get("text"))})
    m = raw.get("misconception", raw.get("limitation"))
    if isinstance(m, str):
        m = {"kind": "Limitation", "text": m}
    if isinstance(m, dict) and _text(m.get("text")) and not any(_text(m.get("text")) == c["text"] for c in cav):
        cav.append({"kind": (_text(m.get("kind")) or "Limitation")[:60], "text": _text(m.get("text"))})
    s["caveats"] = cav[:4]
    s["misconception"] = cav[0] if cav else {"kind": "Limitation", "text": ""}
    if not cav:
        problems.append("SPEC.caveats is empty (give an Assumption, a Limitation and a Common misunderstanding).")
    elif len(cav) < 2:
        notes.append("SPEC.caveats has only one item; give an Assumption, a Limitation and a Common misunderstanding.")
    g = raw.get("grounding") if isinstance(raw.get("grounding"), dict) else {}
    fs = _list(g.get("from_source") or g.get("from_excerpt") or g.get("supported") or g.get("source"))
    ours = _list(g.get("ours") or g.get("our") or g.get("simplifications") or g.get("own"))
    s["grounding"] = {"from_source": fs[:12], "ours": ours[:12]}
    if not fs:
        problems.append("SPEC.grounding.from_source is empty.")
    if not ours:
        notes.append("SPEC.grounding.ours is empty; list the toy examples and simplifications.")
    return s, problems, notes

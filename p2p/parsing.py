"""Robust parsing of model output: marker sections, code fences, think-tags, lenient JSON."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .mathml import fix_latex_escapes

SPEC, CODE, END, PATCH = "===SPEC===", "===CODE===", "===END===", "===SPEC_PATCH==="
_THINK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)


@dataclass
class Parsed:
    spec_text: str | None
    code: str | None
    complete: bool
    patch_text: str | None = None


def _strip_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        nl = s.find("\n")
        s = s[nl + 1:] if nl >= 0 else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    elif s.endswith("```"):
        s = s[:-3]
    return s.strip()


def _fenced(text: str):
    return re.findall(r"```([A-Za-z]*)[^\n]*\n(.*?)```", text, re.S)


def split_response(text: str) -> Parsed:
    text = _THINK.sub("", text or "")
    ci = text.rfind(CODE)
    if ci >= 0:
        si = text.rfind(SPEC, 0, ci)
        spec_text = _strip_fences(text[si + len(SPEC):ci]) if si >= 0 else None
        rest = text[ci + len(CODE):]
        ei = rest.find(END)
        code = _strip_fences(rest[:ei] if ei >= 0 else rest)
        return Parsed(spec_text, code or None, ei >= 0)
    blocks = _fenced(text)
    spec_text = next((b for lang, b in blocks if lang.lower() == "json"), None)
    codes = [b for lang, b in blocks if lang.lower() in ("js", "javascript")]
    if spec_text is None:
        si = text.find(SPEC)
        if si >= 0:
            spec_text = _strip_fences(text[si + len(SPEC):])
    return Parsed(spec_text, max(codes, key=len) if codes else None, False)


def split_repair(text: str) -> Parsed:
    text = _THINK.sub("", text or "")
    pi, ci = text.find(PATCH), text.rfind(CODE)
    patch = None
    if pi >= 0:
        patch = _strip_fences(text[pi + len(PATCH):(ci if ci > pi else len(text))])
    code, complete = None, False
    if ci >= 0:
        rest = text[ci + len(CODE):]
        ei = rest.find(END)
        code = _strip_fences(rest[:ei] if ei >= 0 else rest)
        complete = ei >= 0
    else:
        codes = [b for lang, b in _fenced(text) if lang.lower() in ("js", "javascript")]
        code = max(codes, key=len) if codes else None
    return Parsed(None, code or None, complete, patch)


def split_spec_only(text: str) -> str:
    text = _THINK.sub("", text or "")
    si = text.rfind(SPEC)
    if si < 0:
        return _strip_fences(text)
    rest = text[si + len(SPEC):]
    ei = rest.find(END)
    return _strip_fences(rest[:ei] if ei >= 0 else rest)


def _strip_comments(s: str) -> str:
    out, i, n, ins = [], 0, len(s), False
    while i < n:
        c = s[i]
        if ins:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                ins = False
            i += 1
            continue
        if c == '"':
            ins = True
            out.append(c)
            i += 1
            continue
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _variants(s: str):
    yield s
    t = re.sub(r",(\s*[}\]])", r"\1", _strip_comments(s))
    yield t
    t2 = re.sub(r'\\(?![\\"/bfnrtu])', r"\\\\", t)
    yield t2
    yield re.sub(r"\bNone\b", "null", re.sub(r"\bFalse\b", "false", re.sub(r"\bTrue\b", "true", t2)))


def load_json_object(s):
    """Return (dict, None) or (None, error message)."""
    if s is None:
        return None, "missing"
    s = _strip_fences(s)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return None, "no JSON object found"
    s = fix_latex_escapes(s[i:j + 1])
    first_err = None
    for cand in _variants(s):
        try:
            obj = json.loads(cand, strict=False)
        except json.JSONDecodeError as e:
            first_err = first_err or (e.msg + " at line " + str(e.lineno) + " column " + str(e.colno))
            continue
        if isinstance(obj, dict):
            return obj, None
    return None, first_err or "not a JSON object"

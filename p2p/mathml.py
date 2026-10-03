"""LaTeX -> MathML at generation time, so equations render in textbook form natively in the browser
(Chromium supports MathML Core): no JavaScript, no CDN, no fonts. Output is whitelisted; anything
unexpected falls back to escaped text so a bad formula can never break or inject into the page."""
from __future__ import annotations

import html
import re

try:
    from latex2mathml.converter import convert as _convert
except ImportError:  # dependency missing: equations fall back to readable text
    _convert = None

_MATHML_TAGS = {"math", "mrow", "mi", "mn", "mo", "ms", "mtext", "mspace", "msub", "msup", "msubsup", "mfrac",
                "msqrt", "mroot", "mover", "munder", "munderover", "mtable", "mtr", "mtd", "mstyle", "mpadded",
                "mphantom", "menclose", "semantics", "annotation", "merror", "mmultiscripts", "mprescripts", "none"}
_TAG = re.compile(r"</?([a-zA-Z][\w:-]*)")
_INLINE = re.compile(r"(?<![\\$])\$(?!\s)([^$\n]{1,300}?)(?<![\s\\])\$(?!\d)")


def _safe(mathml: str) -> bool:
    return all(t.lower() in _MATHML_TAGS for t in _TAG.findall(mathml)) and "\\" not in re.sub(r"<[^>]*>", "", mathml)


def tex(latex: str, display: bool = False):
    """MathML for one LaTeX expression, or None if it cannot be converted cleanly."""
    if _convert is None or not latex or not latex.strip():
        return None
    src = latex.strip().replace("<", r"\lt ").replace(">", r"\gt ")
    try:
        out = _convert(src, display="block" if display else "inline")
    except Exception:
        return None
    return out if _safe(out) else None


def equation_html(latex: str) -> str:
    """Display equations: one per line (or split on \\\\); each line falls back to monospace TeX."""
    lines = [ln for ln in re.split(r"\n|\\\\", latex or "") if ln.strip()]
    out = []
    for ln in lines:
        m = tex(ln, display=True)
        out.append(m if m else '<code class="tex">' + html.escape(ln.strip()) + "</code>")
    return "".join('<div class="eq-line">' + x + "</div>" for x in out)


_ASCII_TOKEN = re.compile(r"(?<![\w$\\/])((?:[A-Za-z0-9α-ωΑ-Ωπ√(][\w().,+\-*/=|·×−'α-ωΑ-Ωπ√]*)?"
                          r"(?:\^[\w({]|_[A-Za-z0-9({]|sqrt\()[\w().,+\-*/=^_{}|·×−'α-ωΑ-Ωπ√]*)")
_FUNCS = ("sin", "cos", "tan", "log", "exp", "ln", "max", "min", "softmax", "tanh")


def _group(s: str, i: int):
    """s[i] == '(' : return (inside, index after the matching ')') or None."""
    depth = 0
    for j in range(i, len(s)):
        depth += s[j] == "("
        depth -= s[j] == ")"
        if depth == 0:
            return s[i + 1:j], j + 1
    return None


def _ascii_to_tex(t: str):
    """'pos/10000^(2i/d_model)' -> 'pos/10000^{2i/d_{model}}'. Returns None if it does not look like maths."""
    out, i, n = [], 0, len(t)
    while i < n:
        c = t[i]
        if t.startswith("sqrt(", i):
            g = _group(t, i + 4)
            if not g:
                return None
            out.append(r"\sqrt{" + (_ascii_to_tex(g[0]) or g[0]) + "}")
            i = g[1]
            continue
        if c in "^_":
            if i + 1 < n and t[i + 1] == "(":
                g = _group(t, i + 1)
                if not g:
                    return None
                out.append(c + "{" + (_ascii_to_tex(g[0]) or g[0]) + "}")
                i = g[1]
                continue
            m = re.match(r"\{[^{}]*\}|[A-Za-z0-9α-ω]{1,6}", t[i + 1:])
            if not m:
                return None
            body = m.group(0).strip("{}")
            out.append(c + "{" + (r"\text{" + body + "}" if c == "_" and len(body) > 2 and body.isalpha() else body) + "}")
            i += 1 + len(m.group(0))
            continue
        fm = re.match(r"(" + "|".join(_FUNCS) + r")(?=\()", t[i:])
        if fm and (i == 0 or not t[i - 1].isalpha()):
            out.append("\\" + fm.group(1) + " " if fm.group(1) not in ("softmax",) else r"\mathrm{softmax}")
            i += len(fm.group(1))
            continue
        out.append({"*": r"\cdot ", "·": r"\cdot ", "×": r"\times ", "−": "-"}.get(c, c))
        i += 1
    return "".join(out)


# "n = 4", "p ≤ 0.5", "d_k = 64": a single-letter variable (optional short subscript), a relation, a number.
_REL = re.compile(r"(?<![\w$\\/.])([A-Za-zα-ωΑ-Ω](?:_\{?[A-Za-z0-9]{1,6}\}?)?)\s*(=|≤|≥|<|>|≈|≠)\s*([−-]?\d+(?:\.\d+)?)(?![\w.]*\w)")
_REL_TEX = {"≤": r"\le ", "≥": r"\ge ", "≈": r"\approx ", "≠": r"\ne ", "<": "<", ">": ">", "=": "="}


def _ascii_math(seg: str, rich) -> str:
    """Prose without $...$: convert clearly mathematical tokens (^, short _subscripts, sqrt, 'n = 4') to MathML."""
    spans = []
    for m in _REL.finditer(seg):
        if m.group(1) in ("a", "A", "I"):  # articles / pronoun, not variables
            continue
        src = (_ascii_to_tex(m.group(1)) or m.group(1)) + " " + _REL_TEX[m.group(2)] + " " + m.group(3).replace("−", "-")
        mm = tex(src)
        if mm:
            spans.append((m.start(), m.end(), mm))
    out, pos = [], 0
    for m in _ASCII_TOKEN.finditer(seg):
        if any(s <= m.start() < e for s, e, _ in spans):
            continue
        tok = m.group(1)
        # leave trailing sentence punctuation and unbalanced closing brackets outside the formula
        core = tok.rstrip(".,;:")
        while core.endswith(")") and core.count(")") > core.count("("):
            core = core[:-1]
        word = re.search(r"\S*$", seg[:m.start()]).group(0) + core
        if len(core) < 3 or "://" in word or "www." in word or core.count("_") > 3:
            continue
        # subscripts only on short symbols (d_k, d_model, x_i), never on words (version_2, file_name)
        if "^" not in core and "sqrt(" not in core and any(len(b) > 2 for b in re.findall(r"([A-Za-zα-ω]+)_", core)):
            continue
        tex_src = _ascii_to_tex(core)
        mm = tex(tex_src) if tex_src else None
        if mm:
            spans.append((m.start(), m.start() + len(core), mm))
    for s, e, mm in sorted(spans):
        if s < pos:
            continue
        out.append(rich(seg[pos:s]))
        out.append('<span class="im">' + mm + "</span>")
        pos = e
    out.append(rich(seg[pos:]))
    return "".join(out)


def inline(text: str, rich) -> str:
    """Apply `rich` to prose and convert $...$ segments (and clear plain-text maths) to inline MathML."""
    s = "" if text is None else str(text)
    out, pos = [], 0
    plain_rich = lambda seg: _ascii_math(seg, rich) if (re.search(r"\^|_[A-Za-z0-9({]|sqrt\(", seg) or _REL.search(seg)) and "<" not in seg else rich(seg)
    for m in _INLINE.finditer(s):
        out.append(plain_rich(s[pos:m.start()]))
        mm = tex(m.group(1))
        # Chromium ignores overflow on <math> itself: a wrapper lets a long formula scroll instead of widening the page.
        out.append('<span class="im">' + mm + "</span>" if mm else '<code class="tex">' + html.escape(m.group(1)) + "</code>")
        pos = m.end()
    out.append(plain_rich(s[pos:]))
    return "".join(out)


# LaTeX commands whose first letter is also a JSON escape (\b \f \n \r \t \u): a model that writes "\frac"
# instead of "\\frac" would otherwise get a form feed + "rac" from a perfectly valid JSON parse.
_LATEX_JSON_CLASH = re.compile(
    r"(?:frac|text\w*|times|theta|tau|tanh?|top|tilde|triangle\w*|tfrac|to|nabla|neq?|nu|ni|not\w*|neg|nonumber|"
    r"beta|bar|bf|binom|bold\w*|big\w*|bmod|bot|rho|right\w*|rangle|rm|rfloor|rceil|underline|underbrace|up\w*|"
    r"forall|flat|frak)$")


def fix_latex_escapes(s: str) -> str:
    """Double single backslashes that start a LaTeX command inside JSON strings; leave real escapes alone."""
    out, i, n, ins = [], 0, len(s), False
    while i < n:
        c = s[i]
        if not ins:
            ins = c == '"'
            out.append(c)
            i += 1
            continue
        if c == '"':
            ins = False
            out.append(c)
            i += 1
            continue
        if c != "\\" or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        nxt = s[i + 1]
        if nxt in '\\"/':
            out.append(s[i:i + 2])
            i += 2
            continue
        m = re.match(r"[a-zA-Z]+", s[i + 1:])
        word = m.group(0) if m else ""
        if word[:1] in "bfnrtu" and _LATEX_JSON_CLASH.match(word) and not re.match(r"u[0-9a-fA-F]{4}", s[i + 1:i + 6]):
            out.append("\\\\")
        else:
            out.append("\\")
        i += 1
    return "".join(out)

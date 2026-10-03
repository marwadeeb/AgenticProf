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


def inline(text: str, rich) -> str:
    """Apply `rich` to prose and convert $...$ segments to inline MathML."""
    s = "" if text is None else str(text)
    out, pos = [], 0
    for m in _INLINE.finditer(s):
        out.append(rich(s[pos:m.start()]))
        mm = tex(m.group(1))
        # Chromium ignores overflow on <math> itself: a wrapper lets a long formula scroll instead of widening the page.
        out.append('<span class="im">' + mm + "</span>" if mm else '<code class="tex">' + html.escape(m.group(1)) + "</code>")
        pos = m.end()
    out.append(rich(s[pos:]))
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

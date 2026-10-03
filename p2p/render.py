"""Render SPEC + CODE into one self-contained HTML page with the generic template."""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
from urllib.parse import urlparse

from . import jsbundle, mathml

_ALLOWED = "sub|sup|i|b|em|strong|code|br"
_ESC_TAG = re.compile(r"&lt;(/?)(" + _ALLOWED + r")\s*/?&gt;", re.I)
_TAG = re.compile(r"<(/?)(" + _ALLOWED + r")>")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _balance(s: str) -> str:
    out, stack, pos = [], [], 0
    for m in _TAG.finditer(s):
        out.append(s[pos:m.start()])
        pos = m.end()
        closing, tag = m.group(1) == "/", m.group(2)
        if tag == "br":
            if not closing:
                out.append("<br>")
            continue
        if not closing:
            stack.append(tag)
            out.append("<" + tag + ">")
        elif tag in stack:
            while stack:
                t = stack.pop()
                out.append("</" + t + ">")
                if t == tag:
                    break
    out.append(s[pos:])
    out.extend("</" + t + ">" for t in reversed(stack))
    return "".join(out)


def rich(text) -> str:
    """Escape everything except a small whitelist of inline tags (sub, sup, i, b, em, strong, code, br)."""
    s = _CTRL.sub("", "" if text is None else str(text))
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", s)
    e = html.escape(s, quote=True)
    e = _ESC_TAG.sub(lambda m: "<" + m.group(1) + m.group(2).lower() + ">", e)
    return _balance(e)


def richm(text) -> str:
    """rich() for prose, with $...$ LaTeX segments rendered as inline MathML."""
    return mathml.inline(text, rich)


def _equation(eq: str) -> str:
    # Older-style Unicode/HTML equations (<sub>, <sup>) are shown as before; LaTeX becomes display MathML.
    if re.search(r"</?(sub|sup|i|b)>", eq or "", re.I):
        return '<div class="eq-line">' + rich(eq) + "</div>"
    return mathml.equation_html(eq)


def _symbol(sym: str) -> str:
    if re.search(r"</?(sub|sup|i|b)>", sym or "", re.I):
        return rich(sym)
    m = mathml.tex(sym)
    return '<span class="im">' + m + "</span>" if m else rich(sym)


def _title_html(title) -> str:
    """Marker-highlight the last two real words of the title (skipping a trailing "(Eq. 1)"-style suffix)."""
    t = rich(title)
    m = re.match(r"^(.*?)(\s*[(\[][^()\[\]]*[)\]]\s*)?$", t)
    head, tail = (m.group(1), m.group(2) or "") if m else (t, "")
    words = head.split(" ")
    if len(words) < 2 or "<" in head:
        return t
    small = {"a", "an", "and", "the", "of", "in", "on", "to", "for", "with", "by", "vs", "vs."}
    k = 2 if len(words) > 2 and words[-2].lower() not in small else 1
    return " ".join(words[:-k]) + ' <span class="hl">' + " ".join(words[-k:]) + "</span>" + tail


def plain(text) -> str:
    s = re.sub(r"<[^>]*>", "", "" if text is None else str(text))
    return html.escape(_CTRL.sub("", s).strip(), quote=True)


def _safe_url(u):
    u = (u or "").strip()
    try:
        p = urlparse(u)
    except ValueError:
        return None
    return u if p.scheme in ("http", "https") and p.netloc else None


def _script_json(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False)
    return (s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _script_code(src: str) -> str:
    return re.sub(r"</(script)", r"<\\/\1", src, flags=re.I).replace("<!--", "<\\!--")


def _li(items) -> str:
    return "".join("<li>" + rich(x) + "</li>" for x in items)


def _citation(spec, case) -> str:
    paper = spec.get("paper", {})
    bits = []
    if paper.get("title"):
        bits.append('<span class="pt">' + rich(paper["title"]) + "</span>")
    ay = ", ".join(x for x in (paper.get("authors"), paper.get("year")) if x)
    if ay:
        bits.append(rich(ay))
    if paper.get("section"):
        bits.append(richm(paper["section"]))
    url = _safe_url(paper.get("url") or case.get("source_url"))
    if url:
        short = re.sub(r"^https?://", "", url)
        short = short if len(short) <= 60 else short[:57] + "..."
        bits.append('<a href="' + html.escape(url, quote=True) + '" rel="noopener noreferrer">' + html.escape(short) + "</a>")
    return " &middot; ".join(bits)


def _idea(spec) -> str:
    paper = spec.get("paper", {})
    left = ['<p class="lede">' + richm(spec.get("idea")) + "</p>"]
    if spec.get("why"):
        left.append('<div class="why"><b>Why it matters.</b> ' + richm(spec["why"]) + "</div>")
    right = []
    if spec.get("equation"):
        src = ('<div class="eq-src">' + richm(paper["section"]) + "</div>") if paper.get("section") else ""
        right.append('<div class="eq" role="math">' + _equation(spec["equation"]) + src + "</div>")
    syms = spec.get("symbols") or []
    if syms:
        rows = "".join('<tr><td class="s">' + _symbol(s["sym"]) + "</td><td>" + richm(s["meaning"]) + "</td></tr>" for s in syms)
        right.append('<h3>What each symbol means</h3><table class="sym"><tbody>' + rows + "</tbody></table>")
    return ('<div class="idea-grid reveal"><div>' + "".join(left) + "</div><div>" + "".join(right) + "</div></div>")


def _explorations(spec) -> str:
    out = []
    for i, e in enumerate(spec.get("explorations", [])[:2]):
        n = str(i + 1)
        out.append(
            '<article class="explore reveal" id="exploration-' + n + '"><div><span class="tag">Exploration ' + n + "</span></div>"
            "<h3>" + richm(e.get("title")) + "</h3>"
            '<dl class="steps"><dt class="k-do">Do</dt><dd>' + richm(e.get("change")) + "</dd>"
            '<div class="reveal-q"><dt class="k-pred">Guess</dt><dd>What do you expect, and why? <button type="button" class="btn small ghost" id="reveal-' + n + '" data-reveal="' + n + '">Reveal</button></dd></div>'
            '<div class="reveal-a" id="answer-' + n + '"><dt class="k-obs">See</dt><dd>' + richm(e.get("observe")) + "</dd>"
            '<dt class="k-why">Why</dt><dd>' + richm(e.get("why")) + "</dd></div></dl>"
            '<div><button type="button" class="btn" id="explore-' + n + '" data-explore="' + str(i) + '">Load the starting state &rarr;</button></div></article>')
    return "".join(out)


def _grounding(spec) -> str:
    g = spec.get("grounding", {})
    lim = lambda xs: "".join("<li>" + richm(x) + "</li>" for x in xs)
    return ('<div class="ground reveal"><div class="gcol src"><h3>Supported by the source excerpt</h3><ul>'
            + lim(g.get("from_source") or ["(none listed)"]) + '</ul></div><div class="gcol ours"><h3>Our examples, '
            'simplifications and background</h3><ul>' + lim(g.get("ours") or ["(none listed)"]) + "</ul></div></div>"
            '<p class="disclaimer"><b>Scope.</b> Every number in the playground is computed live from small, illustrative '
            "inputs chosen for teaching. The page demonstrates the mechanism described in the excerpt; it does not "
            "reproduce the paper&#x27;s experiments or reported results. The paper itself was not fetched during "
            "generation: statements attributed to it rest on the supplied excerpt.</p>")


def _excerpt_html(case) -> str:
    from .prompts import excerpt_text
    ex = (excerpt_text(case or {}) or "").strip()
    if len(ex) < 200:
        return ""
    paras = "".join("<p>" + html.escape(p.strip()) + "</p>" for p in re.split(r"\n\s*\n", ex) if p.strip())
    return ('<details class="excerpt" id="source-excerpt"><summary>Read the source excerpt this page was generated from ('
            + str(len(ex.split())) + " words)</summary>" + paras + "</details>")


def _check_note(info) -> str:
    info = info or {}
    tests = info.get("tests") or []
    if info.get("engine") and tests:
        passed = sum(1 for t in tests if t.get("pass"))
        return ("They were executed by the generator before this page was written (%d/%d passed) and are re-run below, "
                "live in your browser." % (passed, len(tests)))
    return "They are run below, live in your browser."


def render_page(spec: dict, code: str, model: str, case: dict, checks_info=None) -> str:
    tpl = jsbundle.asset("template.html")
    mis = spec.get("misconception", {})
    kind = mis.get("kind") or "Limitation"
    aud = str(case.get("audience") or "").strip()
    runtime_spec = {"controls": spec.get("controls", []),
                    "explorations": [{"title": e.get("title", ""), "preset": e.get("preset", {})}
                                     for e in spec.get("explorations", [])]}
    values = {
        "TITLE_TEXT": plain(spec.get("title")),
        "TITLE": _title_html(spec.get("title")),
        "SECTION_SHORT": plain((spec.get("paper") or {}).get("section"))[:80] or "Research paper",
        "CITATION": _citation(spec, case),
        "AUDIENCE": ('<div class="aud">Written for ' + rich(aud[:1].lower() + aud[1:] if aud[:2].istitle() else aud) + "</div>") if aud else "",
        "IDEA": _idea(spec),
        "CAPTION": richm(spec.get("visual_caption") or "Change the controls and watch the visual and the values update."),
        "CAPTION_ATTR": plain(re.sub(r"\$([^$]*)\$", r"\1", spec.get("visual_caption") or "Interactive visual"))[:300],
        "EXPLORATIONS": _explorations(spec),
        "MISC_KIND": plain(kind),
        "MISC": '<span class="k">' + plain(kind) + "</span><p>" + richm(mis.get("text")) + "</p>",
        "GROUNDING": _grounding(spec) + _excerpt_html(case),
        "CHECK_NOTE": _check_note(checks_info),
        "FOOTER": ("Generated by Paper-to-Playground with <code>" + html.escape(model or "") + "</code> on "
                   + _dt.date.today().isoformat() + ". Self-contained page: works offline, makes no network requests."),
        "LIB": jsbundle.asset("vlib.js"),
        "SPEC_JSON": _script_json(runtime_spec),
        "MODEL_CODE": _script_code(jsbundle.wrap_model(code)),
        "RUNTIME": jsbundle.asset("runtime.js"),
    }
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), ""), tpl)


def render_fallback(case: dict, reason: str) -> str:
    focus = rich((case or {}).get("focus") or "")
    url = _safe_url((case or {}).get("source_url"))
    link = ('<p>Source: <a href="' + html.escape(url, quote=True) + '">' + html.escape(url) + "</a></p>") if url else ""
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width, initial-scale=1\"><title>Explainer could not be generated</title><style>"
            "body{font:16px/1.6 system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#0f172a}"
            ".box{border:1px solid #fecaca;background:#fef2f2;border-radius:12px;padding:16px 20px}</style></head><body>"
            "<h1>Explainer could not be generated</h1><div class=\"box\"><p><b>Reason:</b> " + html.escape(reason or "unknown")
            + "</p></div><h2>Requested focus</h2><p>" + focus + "</p>" + link
            + "<p>See trace.jsonl in the same folder for details.</p></body></html>")

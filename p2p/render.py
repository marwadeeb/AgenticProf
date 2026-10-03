"""Render SPEC + CODE into one self-contained HTML page with the generic template."""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
from urllib.parse import urlparse

from . import jsbundle

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
        bits.append(rich(paper["section"]))
    url = _safe_url(paper.get("url") or case.get("source_url"))
    if url:
        short = re.sub(r"^https?://", "", url)
        short = short if len(short) <= 60 else short[:57] + "..."
        bits.append('<a href="' + html.escape(url, quote=True) + '" rel="noopener noreferrer">' + html.escape(short) + "</a>")
    return " &middot; ".join(bits)


def _idea(spec) -> str:
    paper = spec.get("paper", {})
    h = ['<p class="lede">' + rich(spec.get("idea")) + "</p>"]
    if spec.get("why"):
        h.append('<div class="why"><b>Why it matters.</b> ' + rich(spec["why"]) + "</div>")
    if spec.get("equation"):
        h.append('<div class="eq" role="math">' + rich(spec["equation"]) + "</div>")
        if paper.get("section"):
            h.append('<div class="eq-src">From the source: ' + rich(paper["section"]) + "</div>")
    syms = spec.get("symbols") or []
    if syms:
        rows = "".join('<tr><td class="s">' + rich(s["sym"]) + "</td><td>" + rich(s["meaning"]) + "</td></tr>" for s in syms)
        h.append('<h3>Symbols</h3><table class="sym"><thead><tr><th>Symbol</th><th>Meaning</th></tr></thead><tbody>'
                 + rows + "</tbody></table>")
    return "".join(h)


def _explorations(spec) -> str:
    out = []
    for i, e in enumerate(spec.get("explorations", [])[:2]):
        out.append(
            '<article class="explore"><div><span class="tag">Exploration ' + str(i + 1) + "</span></div>"
            "<h3>" + rich(e.get("title")) + "</h3>"
            '<dl class="steps"><dt>Change</dt><dd>' + rich(e.get("change")) + "</dd>"
            '<div class="reveal-q"><dt>Predict</dt><dd>Before looking, decide what you expect to happen and why. <button type="button" class="btn small ghost" id="reveal-' + str(i + 1) + '" data-reveal="' + str(i + 1) + '">Reveal</button></dd></div><div class="reveal-a" id="answer-' + str(i + 1) + '"><dt>Observe</dt><dd>' + rich(e.get("observe")) + "</dd>"
            "<dt>Why</dt><dd>" + rich(e.get("why")) + "</dd></div></dl>"
            '<div><button type="button" class="btn" id="explore-' + str(i + 1) + '" data-explore="' + str(i) + '">Load the starting state</button></div></article>')
    return "".join(out)


def _grounding(spec) -> str:
    g = spec.get("grounding", {})
    return ('<div class="ground"><div class="gcol src"><h3>Supported by the source excerpt</h3><ul>'
            + _li(g.get("from_source") or ["(none listed)"]) + '</ul></div><div class="gcol ours"><h3>Our examples, '
            'simplifications and background</h3><ul>' + _li(g.get("ours") or ["(none listed)"]) + "</ul></div></div>"
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
        "TITLE": rich(spec.get("title")),
        "CITATION": _citation(spec, case),
        "AUDIENCE": ('<div class="aud">Written for: ' + rich(aud) + "</div>") if aud else "",
        "IDEA": _idea(spec),
        "CAPTION": rich(spec.get("visual_caption") or "Change the controls and watch the visual and the values update."),
        "CAPTION_ATTR": plain(spec.get("visual_caption") or "Interactive visual")[:300],
        "EXPLORATIONS": _explorations(spec),
        "MISC_KIND": plain(kind),
        "MISC": '<span class="k">' + plain(kind) + "</span><p>" + rich(mis.get("text")) + "</p>",
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

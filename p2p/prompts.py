"""Prompt builders. One compact generation prompt; compact repair prompts (no excerpt unless a
scientific test failed); a tiny JSON-syntax repair prompt."""
from __future__ import annotations

import json
import re

from .spec import SPEC_KEYS

V_REFERENCE = """V helpers (each returns an SVG string; a = optional attribute object such as {color, fill, stroke, sw (stroke width), dash, opacity, size (font size), anchor, weight}):
 V.svg(w, h, ...parts)   V.g(a, ...parts)   V.translate(x, y, ...parts)
 V.rect(x, y, w, h, a)   V.circle(cx, cy, r, a)   V.line(x1, y1, x2, y2, a)   V.arrow(x1, y1, x2, y2, a)
 V.path(d, a)   V.polyline([[x, y], ...], a)   V.polygon([[x, y], ...], a)   V.text(x, y, str, a)  ("\\n" in str starts a new line)
 V.box(x, y, w, h, label, a)   V.node(cx, cy, r, label, a)   V.legend(x, y, [{label, color}])
 V.axes({x, y, w, h, xmin, xmax, ymin, ymax, xlabel, ylabel, title, xticks, yticks}) -> {svg, sx, sy}; sx/sy map data to pixels
 V.lineChart({x, y, w, h, series: [{xs, ys, label, color, dash, markers}], points: [{x, y, label, color}], vlines: [{x, label}], hlines: [{y, label}], xmin, xmax, ymin, ymax, xlabel, ylabel, title})
 V.barChart({x, y, w, h, labels, values | series: [{values, label, color}], colors, ymin, ymax, ylabel, title, digits, highlight})
 V.heatmap({x, y, w, h, matrix, rowLabels, colLabels, title, min, max, diverging, digits, highlight: [[i, j]]})
 V.fmt(x, digits = 3) -> string   V.linspace(a, b, n)   V.range(n)   V.scale(d0, d1, r0, r1) -> function
 V.heat(v, min, max), V.div(v, absMax) -> colour; colours: V.c.ink, V.c.muted, V.c.grid, V.c.blue, V.c.orange, V.c.green, V.c.red, V.c.purple, V.c.teal, V.c.series[i]
 Pixels have y pointing down. Chart x/y/w/h is the plot area: leave about 60 px left, 45 px below and 30 px above it for labels. Keep text >= 11 px and avoid overlaps. Use V.c colours, never hex codes, so the reader's colour-blind / greyscale setting applies."""

SYSTEM_PROMPT = """You turn a research-paper excerpt and a learning brief into one offline, interactive explainer. A fixed HTML template renders your SPEC (JSON) and runs your CODE (JavaScript); you never write HTML or CSS.

Reply with exactly this and nothing else:
===SPEC===
{ one JSON object }
===CODE===
plain JavaScript
===END===

SPEC fields (all required):
{"plan": "<= 50 words: the mechanism, the exact equation(s) implemented, what the visual shows, what TESTS verify",
 "title": "short page title",
 "paper": {"title": "", "authors": "", "year": "", "section": "section and equation numbers explained"},
 "idea": "2-4 sentences: the core idea in plain words",
 "why": "1-2 sentences: why it matters",
 "equation": "LaTeX of the key equation(s), faithful to the source, one per line, e.g. \\mathrm{softmax}\\left(\\frac{QK^{\\top}}{\\sqrt{d_k}}\\right)",
 "symbols": [{"sym": "LaTeX, e.g. d_k", "meaning": ""}],
 "controls": [2-6 controls, see below],
 "visual_caption": "how to read the visual: what each panel, axis, colour and mark means",
 "explorations": [exactly 2: {"title": "", "preset": {"<control id>": value}, "change": "what to change", "observe": "what to watch (name the panel or readout)", "why": "the mechanism-level reason"}],
 "misconception": {"kind": "Limitation" | "Assumption" | "Common misunderstanding", "text": ""},
 "grounding": {"from_source": ["claims the excerpt supports, each tagged with its section/equation"], "ours": ["our toy numbers, simplifications, visual choices and any background not in the excerpt"]}}
JSON rules: double quotes, no comments, no trailing commas. Maths is rendered in textbook form from LaTeX: "equation" and symbols[].sym are LaTeX without $; in every other SPEC text field (idea, why, explorations, misconception, grounding, captions) write EVERY formula, symbol and expression inline as $...$ LaTeX (e.g. "scale by $1/\\sqrt{d_k}$", "$PE_{(pos,2i)} = \\sin(pos/10000^{2i/d_{model}})$"); never plain-text maths such as 10000^(2i/d_model) or sqrt(d_k). Inside JSON every LaTeX backslash is doubled (\\frac, \\sqrt). Tags <b> <i> <br> are allowed in text. In CODE strings (labels, readout, insight, SVG text) use Unicode maths instead (√ Σ · × ≤ ≈ α β θ, d_k as dₖ), never LaTeX.

Controls (id: short JavaScript identifier; its value reaches CODE as p.<id>; optional "help": one short sentence):
 {"type":"slider","id":"t","label":"Temperature T","min":0.1,"max":5,"step":0.1,"value":1}   ("number" takes the same fields)
 {"type":"select","id":"mode","label":"","options":[{"value":"a","label":""}],"value":"a"}
 {"type":"toggle","id":"scaled","label":"","value":true}
 {"type":"vector","id":"w","label":"","length":4,"min":0,"max":10,"step":0.1,"value":[1,2,3,4],"labels":["w₁","w₂","w₃","w₄"],"fill":1}   -> p.w is an array of numbers
 {"type":"matrix","id":"Q","label":"","rows":2,"cols":3,"min":-5,"max":5,"step":0.5,"value":[[1,0,2],[0,1,1]],"row_labels":["q₁","q₂"],"col_labels":["1","2","3"]}   -> p.Q is an array of rows
 "length", "rows" or "cols" may instead be the id of an integer slider (min >= 1); entries are then truncated or padded with "fill". Keep sizes <= 8. Presets and TESTS params use only control ids, list only what they change (everything else keeps its default) and give whole vectors/matrices of the right size.

CODE: ES2020, deterministic, pure (no DOM, window, document, fetch, import, Math.random). Define at top level:
 function compute(p) - returns an object r holding every number the page shows. All maths lives here, implemented directly from the source equation. Every valid input (range ends, zeros, ties, every size) must give finite displayed values: guard divisions and logarithms, follow the source's conventions (e.g. 0·log 0 = 0) and flag degenerate cases in r instead of producing NaN.
 function view(p, r) - returns an SVG string built with V (below), normally V.svg(760, 420, ...). Make the mechanism visible: inputs -> intermediate quantities -> output, with labelled panels, axes and units; emphasise what changes.
 function readout(p, r) - returns an array of {label, value, formula?, note?} in calculation order, inputs -> intermediates -> output, which the page shows as a numbered chain (value: number, or string made with V.fmt; formula: the numbers substituted, e.g. "e^1.20 / 4.31") and/or {table: {title, headers: [...], rows: [[...]]}} showing the key intermediate values and every check the brief asks for (e.g. a row sum).
 function insight(p, r) - returns one plain sentence interpreting the current state.
 view, readout and insight may use only p, r, V, helper functions and their own locals: every number they show must come from r or p (e.g. p.alpha, never a bare alpha).
 const TESTS = [{name, params, check: (r, p) => boolean}] - 3 to 5 checks run against compute; params override defaults. Every expected value must be certain WITHOUT doing arithmetic yourself: (a) each check the brief names, with the brief's own numbers; (b) identities recomputed inside check from r and p (e.g. rebuild the output from the intermediate values in a separate loop, a sum of probabilities equals 1); (c) exact closed-form special cases (equal inputs, a single nonzero entry, zero, identity, symmetry). Never compare against a literal you worked out by multi-step arithmetic. A test may give a vector/matrix of any size (compute must use .length, not a fixed size). Include one edge case at a range end. Compare floats with a tolerance such as 1e-9 * max(1, |expected|).
 const INVARIANTS = [{name, check: (r, p) => boolean}] - 1 to 3 exact properties (never convergence or "small error" claims, which fail at range ends such as few iterations) that hold for EVERY valid input (e.g. "each row of weights sums to 1", "0 ≤ H ≤ log₂ n"); the page shows them live and the generator checks them on every state it tries.

""" + V_REFERENCE + """

Quality bar:
- Audience first: plain language for the stated audience; define every symbol and term on first use; short sentences.
- Fidelity: implement the source equation exactly (constants, normalisation, scaling, log base). Attribute nothing to the paper that the excerpt does not support. Toy inputs are illustrations: never claim they reproduce the paper's experiments or reported numbers.
- Cover every learning outcome and check named in the brief. Defaults must already show the mechanism clearly. Each exploration's preset and steps must produce exactly what its "observe" text describes with your code.
- Economy: no comments in CODE, no repetition; aim for under 4500 tokens in total."""

GEN_INSTRUCTION = ("The paper itself is not available to you beyond the text above (no web access). Base every claim "
                   "attributed to the paper on the excerpt; any general background you add belongs in grounding.ours. "
                   "Produce the SPEC and CODE now.")

RETRY_NOTE = ("\n\nIMPORTANT: your previous reply was cut off or lacked the required markers. Reply again in the exact "
              "three-marker format, more compactly (shorter texts, no comments in CODE).")

REPAIR_SYSTEM = """You repair an interactive explainer produced by an earlier step. A fixed template renders its SPEC (JSON) and runs its CODE (JavaScript), which defines compute(p), view(p, r), readout(p, r), insight(p, r), const TESTS and const INVARIANTS using the V helpers below. Automated checks executed the CODE and found problems.

Fix the root cause of every listed problem with the smallest correct change and keep everything that already works. When a TEST fails, decide from the source equation whether the code or the test is wrong; never weaken a correct test. A test whose expected value is a hand-computed literal is often the thing that is wrong: replace it with an identity recomputed inside check or an exact special case. Error locations refer to CODE line numbers.

Reply with exactly:
===SPEC_PATCH===
{JSON object with only the top-level SPEC keys you changed, e.g. "controls" or "explorations" (full new value of each); {} if none}
===CODE===
ONLY the top-level declarations you change, each complete (function name(...) {...} or const NAME = ...;); they replace the declarations with the same name and everything else is kept. Do not repeat unchanged declarations. Or the single word UNCHANGED.
===END===

CODE rules: ES2020, pure and deterministic (no DOM, fetch, import, Math.random); every displayed value finite for every valid input.
"""
# The V helper reference (~700 tokens) is only needed when the drawing code is involved.
_VIEW_PROBLEM = re.compile(r"view|SVG|visual|Displayed output|\bV\.", re.I)

SPEC_FIX_SYSTEM = ("You repair malformed JSON. Reply with ===SPEC=== on its own line, then the corrected JSON object, then "
                   "===END===. Keep all content; fix only syntax (double quotes, escaped inner quotes, no trailing commas, "
                   "no comments, no backslashes).")

_CORE = ("source_url", "focus", "audience")
_ORDER = ("id", "title", "paper", "paper_title", "source_url", "section", "excerpt", "focus", "audience")


def excerpt_text(case: dict) -> str:
    for k in ("excerpt", "source_excerpt", "paper_excerpt", "text", "content"):
        v = case.get(k)
        if isinstance(v, str) and v.strip():
            return v
    others = [v for k, v in case.items() if k not in _CORE and isinstance(v, str)]
    return max(others, key=len) if others else ""


def case_block(case: dict, limit: int = 30000) -> str:
    keys = [k for k in _ORDER if k in case] + [k for k in case if k not in _ORDER]
    out = []
    for k in keys:
        v = case[k]
        if v is None:
            continue
        s = (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)).strip()
        if not s:
            continue
        if len(s) > limit:
            s = s[:limit] + "\n[... truncated ...]"
        tag = re.sub(r"[^A-Za-z0-9_]", "_", str(k))[:40] or "field"
        out.append("<" + tag + ">\n" + s + "\n</" + tag + ">")
    if not excerpt_text(case).strip() or len(excerpt_text(case)) < 200:
        out.append("(No substantial excerpt was supplied: rely on the standard content of the cited section, and say "
                   "in grounding.ours that the excerpt was not available.)")
    return "\n".join(out)


def generation_messages(case: dict) -> list:
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": case_block(case) + "\n\n" + GEN_INSTRUCTION}]


RETRY_REPAIR_NOTE = ("A previous repair did not fix the problems below, so the error is not where it was assumed. Derive the "
                     "failing case from the source equation step by step (signs, ordering of pairs, indices, normalisation), "
                     "compare with the computed values shown, then decide whether compute or the check is wrong. A check "
                     "that expects an exact value a formula only approaches (e.g. softmax weight exactly 1) is wrong.")


DERIVE_NOTE = ("Before the patch, write ===DERIVATION=== and then at most 120 words: recompute the first failing case by hand "
               "from the source equation, using the inputs shown, and state which value is wrong and whether compute or the "
               "check must change. Then continue with ===SPEC_PATCH=== and ===CODE=== as usual.")


def repair_messages(case, spec, code, failures, warnings, include_excerpt, retry=False, derive=False) -> list:
    parts = []
    if retry:
        parts.append("<note>\n" + RETRY_REPAIR_NOTE + (" " + DERIVE_NOTE if derive else "") + "\n</note>")
    for k in ("focus", "audience"):
        v = str(case.get(k) or "").strip()
        if v:
            parts.append("<" + k + ">\n" + v + "\n</" + k + ">")
    if include_excerpt:
        ex = excerpt_text(case).strip()
        if ex:
            parts.append("<excerpt>\n" + ex[:8000] + "\n</excerpt>")
    keys = ["plan", "equation", "symbols", "controls", "explorations"]
    for k in SPEC_KEYS:
        if k not in keys and any(("SPEC." + k) in f for f in failures):
            keys.append(k)
    slim = {k: spec.get(k) for k in keys if k in spec}
    parts.append("<spec>\n" + json.dumps(slim, ensure_ascii=False, separators=(",", ":")) + "\n</spec>")
    parts.append("<code>\n" + code + "\n</code>")
    probs = "\n".join("- " + f for f in failures[:14])
    if warnings:
        probs += "\nAlso fix if quick:\n" + "\n".join("- " + w for w in warnings[:6])
    parts.append("<problems>\n" + probs + "\n</problems>")
    parts.append("Return SPEC_PATCH and CODE in the exact format.")
    system = REPAIR_SYSTEM + ("\n" + V_REFERENCE if _VIEW_PROBLEM.search(" ".join(failures + list(warnings or []))) else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def spec_fix_messages(raw: str, error: str) -> list:
    return [{"role": "system", "content": SPEC_FIX_SYSTEM},
            {"role": "user", "content": "Parser error: " + str(error) + "\n<broken>\n" + raw[:24000] + "\n</broken>"}]

#!/usr/bin/env python3
"""Offline self-test of the generator (no network, no API key):  python tests/offline_check.py
Uses a generic toy fixture (a weighted average, not a paper) to exercise parsing, SPEC normalisation,
executable JS checks, the repair loop with a scripted fake LLM, and rendering."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent  # noqa: E402
from p2p import checks, jsbundle, parsing, render  # noqa: E402
from p2p.spec import normalize_spec  # noqa: E402
from p2p.trace import Trace  # noqa: E402

CASE = {"source_url": "https://example.org/toy", "focus": "Toy weighted average (pipeline self-test).",
        "audience": "Testers", "excerpt": "Toy fixture: m = sum(w_i x_i) / sum(w_i)."}
SPEC = {
    "plan": "toy", "title": "Weighted average (pipeline self-test)",
    "paper": {"title": "Pipeline self-test (not a paper)", "authors": "n/a", "year": "n/a", "section": "n/a"},
    "idea": "A weighted average combines values using non-negative weights normalised to sum to one.",
    "why": "Fixture only.", "equation": "m = Σ w<sub>i</sub> x<sub>i</sub> / Σ w<sub>i</sub>",
    "symbols": [{"sym": "x<sub>i</sub>", "meaning": "values"}, {"sym": "w<sub>i</sub>", "meaning": "weights"}],
    "controls": [
        {"type": "slider", "id": "n", "label": "Number of items", "min": 1, "max": 6, "step": 1, "value": 3},
        {"type": "vector", "id": "w", "label": "Weights", "length": "n", "min": 0, "max": 5, "step": 0.5, "value": [1, 1, 2], "fill": 1},
        {"type": "toggle", "id": "norm", "label": "Normalise weights", "value": True},
        {"type": "select", "id": "vals", "label": "Values", "options": [{"value": "lin", "label": "1,2,3"}, {"value": "sq", "label": "1,4,9"}], "value": "lin"}],
    "visual_caption": "Bars show the weights used; the text shows the average.",
    "explorations": [
        {"title": "Equal weights", "preset": {"w": [1, 1, 1]}, "change": "Set all weights equal.", "observe": "The average equals the plain mean.", "why": "Each weight is 1/n."},
        {"title": "One dominant weight", "preset": {"w": [5, 0, 0]}, "change": "Give one item all the weight.", "observe": "The average equals that item.", "why": "Other terms vanish."}],
    "misconception": {"kind": "Common misunderstanding", "text": "Weights need not sum to one before normalisation."},
    "grounding": {"from_source": ["Fixture only."], "ours": ["All numbers are toy values."]},
}
GOOD = """function compute(p) {
  var xs = p.w.map(function (_, i) { return p.vals === "sq" ? (i + 1) * (i + 1) : i + 1; });
  var s = p.w.reduce(function (a, b) { return a + b; }, 0);
  var deg = s <= 0;
  var wn = p.w.map(function (w) { return deg ? 1 / p.w.length : (p.norm ? w / s : w); });
  var num = 0;
  for (var i = 0; i < xs.length; i++) num += wn[i] * xs[i];
  var m = (p.norm || deg) ? num : num / s;
  return { xs: xs, wn: wn, sum: s, mean: m, degenerate: deg };
}
function view(p, r) {
  return V.svg(760, 300, V.barChart({ x: 70, y: 40, w: 360, h: 200, labels: r.xs.map(String), values: r.wn, title: "Weights used", ylabel: "weight" }),
    V.text(480, 140, "mean = " + V.fmt(r.mean, 3), { size: 22, weight: 700 }));
}
function readout(p, r) {
  return [{ label: "Σ w", value: V.fmt(r.sum, 2) }, { label: "mean", value: V.fmt(r.mean, 4) },
    { table: { title: "Items", headers: ["i", "x", "w used"], rows: r.xs.map(function (x, i) { return [i + 1, x, V.fmt(r.wn[i], 3)]; }) } }];
}
function insight(p, r) { return "The weighted average is " + V.fmt(r.mean, 3) + "."; }
const TESTS = [
  { name: "equal weights give the plain mean", params: { w: [1, 1, 1] }, check: function (r) { return Math.abs(r.mean - 2) < 1e-9; } },
  { name: "normalised weights sum to 1", params: {}, check: function (r) { return Math.abs(r.wn.reduce(function (a, b) { return a + b; }, 0) - 1) < 1e-9; } },
  { name: "all-zero weights fall back to uniform", params: { w: [0, 0, 0] }, check: function (r) { return r.degenerate && Math.abs(r.mean - 2) < 1e-9; } }
];
const INVARIANTS = [{ name: "weights used sum to 1 when normalised", check: function (r, p) { return !(p.norm || r.degenerate) || Math.abs(r.wn.reduce(function (a, b) { return a + b; }, 0) - 1) < 1e-9; } }];
"""
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append(bool(cond))
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond or not detail else "  ::  " + str(detail)[:600]))


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests_made = self.prompt_tokens = self.completion_tokens = self.reasoning_tokens = 0

    def can_afford(self, n):
        return bool(self.responses) and self.requests_made < 10

    def chat(self, messages, stage, purpose, max_tokens):
        if not self.responses:
            raise agent.LLMUnavailable("no scripted response left")
        self.requests_made += 1
        self.prompt_tokens += 1000
        self.completion_tokens += 500
        return {"text": self.responses.pop(0), "finish_reason": "stop", "usage": {}}


def main() -> int:
    txt = ("<think>draft ===SPEC=== x</think>Here you go\n===SPEC===\n```json\n" + json.dumps(SPEC)
           + "\n```\n===CODE===\n```javascript\n" + GOOD + "\n```\n===END===")
    p = parsing.split_response(txt)
    check("parse markers, fences and think-tags", p.spec_text and p.code and p.complete and p.code.startswith("function compute"))
    obj, err = parsing.load_json_object(p.spec_text)
    check("load spec JSON", obj is not None and obj.get("title"), err)
    obj2, err2 = parsing.load_json_object('{"a": 1, // note\n "b": [1, 2,],}')
    check("lenient JSON (comments, trailing commas)", obj2 == {"a": 1, "b": [1, 2]}, err2)
    check("repair parsing (UNCHANGED)", parsing.split_repair("===SPEC_PATCH===\n{}\n===CODE===\nUNCHANGED\n===END===").code == "UNCHANGED")

    spec, probs, notes = normalize_spec(json.loads(json.dumps(SPEC)), CASE)
    check("spec normalises without problems", spec is not None and not probs, probs)
    check("vector length bound to slider", spec["controls"][1]["length"] == "n" and len(spec["controls"][1]["value"]) == 3)
    _, probs2, _ = normalize_spec({"idea": "x", "controls": [SPEC["controls"][0]], "explorations": SPEC["explorations"][:1]}, CASE)
    check("spec detects missing controls/explorations", any("controls" in x for x in probs2) and any("explorations" in x for x in probs2), probs2)

    if not checks.engine_available():
        print("SKIP  executable JS checks (quickjs not installed on this platform)")
    else:
        import quickjs
        ctx = quickjs.Context()
        for name in ("vlib.js", "harness.js", "runtime.js"):
            try:
                ctx.eval("new Function(" + json.dumps(jsbundle.asset(name)) + "); 1")
                check("asset parses: " + name, True)
            except Exception as exc:
                check("asset parses: " + name, False, exc)
        r = checks.run_js_checks(spec, GOOD)
        check("good fixture passes all executable checks", not r["failures"] and not r["fatal"], r["failures"])
        check("fixture TESTS executed and pass", len(r["tests"]) == 3 and all(t["pass"] for t in r["tests"]), r["tests"])
        check("all four controls detected as active", set(r["active"]) == {"n", "w", "norm", "vals"}, (r["active"], r["inert"]))
        r2 = checks.run_js_checks(spec, "function compute(p) {\n  var a = 1;\n  var x = ;\n}\n")
        check("syntax error is fatal and mapped to CODE line 3", r2["fatal"] and any("line 3" in f for f in r2["failures"]), r2["failures"])
        r3 = checks.run_js_checks(spec, GOOD.replace("var deg = s <= 0;", "var deg = false;"))
        check("zero-weight NaN / failing test detected", r3["failures"], r3)
        r4 = checks.run_js_checks(spec, "function compute(p) { while (true) {} }\nfunction view(p, r) { return V.svg(10, 10); }\n", timeout=8)
        check("infinite loop is contained", r4["fatal"], r4["failures"])
        r5 = checks.run_js_checks(spec, GOOD.replace("labels: r.xs.map(String), values: r.wn", "labels: [\"a\", \"b\", \"c\"], values: [1, 1, 1]").replace('"mean = " + V.fmt(r.mean, 3)', '"mean"'))
        check("static visual is detected", any("visual never changes" in f for f in r5["failures"]), r5["failures"])

        buggy = GOOD.replace('"The weighted average is " + V.fmt(r.mean, 3)', '"The weighted average is " + r.missing.toFixed(3)')
        out = Path(tempfile.mkdtemp(prefix="p2p_test_"))
        tr = Trace(out / "trace.jsonl", time.monotonic())
        llm = FakeLLM(["===SPEC===\n" + json.dumps(SPEC) + "\n===CODE===\n" + buggy + "\n===END===",
                       "===SPEC_PATCH===\n{}\n===CODE===\n" + GOOD + "\n===END==="])
        code = agent.Pipeline(CASE, llm, tr, out, "fake/model", time.monotonic() + 300).run()
        tr.close()
        events = [json.loads(line) for line in (out / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        html = (out / "index.html").read_text(encoding="utf-8")
        check("pipeline exits 0", code == 0)
        check("pipeline: failing initial candidate was repaired", any(e["action"] == "accept_revision" and e["result"] == "accepted" for e in events))
        check("pipeline: summary reports success with 2 requests", events[-1]["stage"] == "summary" and events[-1]["result"] == "success" and events[-1]["requests"] == 2, events[-1])
        check("page passes static checks", not checks.static_html_checks(html)[0], checks.static_html_checks(html))
        check("page embeds the repaired code", "r.missing" not in html and "weighted average" in html.lower())
        check("no unreplaced placeholders", "{{" not in html)
        check("page has settings, live checks, excerpt and stable ids", all(s in html for s in ('id="set-palette"', 'id="p2p-live-checks"', 'id="source-excerpt"' if len(CASE["excerpt"]) >= 200 else "", 'id="explore-1"', 'id="reveal-2"')))
        print("      sample page:", out / "index.html")
    fb = render.render_fallback(CASE, "test")
    check("fallback page renders", "could not be generated" in fb)
    print("\n%d/%d checks passed" % (sum(RESULTS), len(RESULTS)))
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())

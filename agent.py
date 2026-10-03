#!/usr/bin/env python3
"""Paper to Playground: research-paper excerpt + learning brief -> self-contained interactive HTML explainer.

    python agent.py --input case.json --output out --model MODEL_ID

Pipeline: (1) plan + generate: one LLM call returns a plan, a SPEC (JSON) and CODE (JavaScript);
(2) check: deterministic, zero-token checks that EXECUTE the generated JavaScript in QuickJS against
defaults, presets, its own TESTS, every control's range ends and random states; (3) revise: only if
checks fail, a compact repair call and a re-check, keeping the best candidate; (4) render a generic
template to out/index.html. Every stage is logged to out/trace.jsonl."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

T0 = time.monotonic()
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from p2p import checks, parsing, prompts, render  # noqa: E402
from p2p.llm import LLMUnavailable, OpenRouterClient  # noqa: E402
from p2p.spec import SPEC_KEYS, normalize_spec  # noqa: E402
from p2p.trace import Trace  # noqa: E402

HARD_LIMIT_S = 600.0
SAFETY_S = float(os.getenv("P2P_SAFETY_SECONDS", "40"))
GEN_MAX_TOKENS = int(os.getenv("P2P_GEN_MAX_TOKENS", "14000"))
REPAIR_MAX_TOKENS = int(os.getenv("P2P_REPAIR_MAX_TOKENS", "9000"))
MAX_REPAIRS = int(os.getenv("P2P_MAX_REPAIRS", "2"))
MAX_REQUESTS = 10
MAX_COMPLETION_TOKENS = 30000


@dataclass
class Candidate:
    label: str
    spec: dict | None
    code: str
    failures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    fatal: bool = False
    js: dict = field(default_factory=dict)

    @property
    def score(self) -> int:
        return (1000 if self.fatal else 0) + 10 * len(self.failures) + len(self.warnings)


class Pipeline:
    def __init__(self, case, llm, trace, out_dir, model, deadline, max_repairs=MAX_REPAIRS):
        self.case, self.llm, self.trace = case, llm, trace
        self.out_dir, self.model, self.deadline, self.max_repairs = Path(out_dir), model, deadline, max_repairs

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    def run(self) -> int:
        messages = prompts.generation_messages(self.case)
        self.trace.event("plan", "build_prompt", "ok", system_chars=len(messages[0]["content"]),
                         user_chars=len(messages[1]["content"]), excerpt_chars=len(prompts.excerpt_text(self.case)),
                         strategy="single generation call; repair calls only when executable checks fail")
        parsed = self._generate(messages)
        if parsed is None:
            return self._fail("the model produced no usable output")
        spec_raw = self._load_spec(parsed)
        if spec_raw is None:
            return self._fail("could not obtain a valid SPEC JSON object")
        best = self._evaluate("initial", spec_raw, parsed.code or "")
        if best.spec is None:
            return self._fail("SPEC unusable: " + "; ".join(best.failures[:3]))
        if best.spec.get("plan"):
            self.trace.event("plan", "model_plan", "ok", plan=best.spec["plan"])
        rounds = 0
        while best.failures and rounds < self.max_repairs:
            rounds += 1
            cand = self._revise(best, rounds)
            if cand is None:
                break
            if cand.score < best.score:
                self.trace.event("revise", "accept_revision", "accepted", round=rounds, score_before=best.score, score_after=cand.score)
                best = cand
            else:
                self.trace.event("revise", "accept_revision", "rejected", round=rounds, score_before=best.score,
                                 score_after=cand.score, reason="revision did not reduce check failures; kept previous candidate")
        return self._finish(best, rounds)

    def _generate(self, messages):
        last = None
        for attempt in (1, 2):
            if attempt == 2:
                if not self.llm.can_afford(4000) or self.time_left() < 90:
                    break
                messages = [messages[0], {"role": "user", "content": messages[1]["content"] + prompts.RETRY_NOTE}]
            try:
                res = self.llm.chat(messages, stage="generate", purpose="generate" if attempt == 1 else "generate_retry",
                                    max_tokens=GEN_MAX_TOKENS)
            except LLMUnavailable as exc:
                self.trace.event("generate", "llm_call", "unavailable", error=str(exc))
                break
            p = parsing.split_response(res["text"])
            ok = p.spec_text is not None and p.code is not None and (p.complete or res["finish_reason"] not in ("length", "max_tokens"))
            self.trace.event("parse", "split_response", "ok" if ok else "incomplete", attempt=attempt, finish_reason=res["finish_reason"],
                             has_spec=p.spec_text is not None, has_code=p.code is not None, end_marker=p.complete,
                             code_lines=(p.code.count("\n") + 1) if p.code else 0)
            if ok:
                return p
            if p.spec_text is not None:
                last = p
        return last

    def _load_spec(self, parsed):
        obj, err = parsing.load_json_object(parsed.spec_text)
        if obj is not None:
            self.trace.event("parse", "load_spec_json", "ok", keys=sorted(obj.keys()))
            return obj
        self.trace.event("parse", "load_spec_json", "fail", error=err)
        if parsed.spec_text is None or not self.llm.can_afford(2500) or self.time_left() < 60:
            return None
        try:
            res = self.llm.chat(prompts.spec_fix_messages(parsed.spec_text, err), stage="revise", purpose="fix_spec_json", max_tokens=6000)
        except LLMUnavailable as exc:
            self.trace.event("revise", "fix_spec_json", "unavailable", error=str(exc))
            return None
        obj, err2 = parsing.load_json_object(parsing.split_spec_only(res["text"]))
        self.trace.event("revise", "fix_spec_json", "ok" if obj is not None else "fail", error=err2)
        return obj

    def _evaluate(self, label, spec_raw, code) -> Candidate:
        spec, spec_fail, spec_warn = normalize_spec(spec_raw, self.case)
        if spec is None:
            self.trace.event("check", "evaluate_candidate", "fail", candidate=label, failures=spec_fail)
            return Candidate(label, None, code, spec_fail, spec_warn, fatal=True)
        code_fail, code_warn = checks.static_code_checks(code)
        try:
            js = checks.run_js_checks(spec, code, timeout=max(10.0, min(60.0, self.time_left() - 20.0)))
        except Exception as exc:  # a checker bug must never kill the run
            js = {"engine": None, "failures": [], "warnings": ["executable checks crashed: " + type(exc).__name__ + ": " + str(exc)],
                  "fatal": False, "tests": [], "active": [], "inert": [], "visual_active": None, "cases": 0, "duration_s": 0.0}
        failures = code_fail + js["failures"] + spec_fail
        warnings = spec_warn + code_warn + js["warnings"]
        cand = Candidate(label, spec, code, failures, warnings, fatal=bool(js.get("fatal")), js=js)
        tests = js.get("tests", [])
        self.trace.event("check", "evaluate_candidate", "pass" if not failures else "fail", candidate=label, engine=js.get("engine"),
                         cases_executed=js.get("cases"), invariants=js.get("invariants"), tests_passed=sum(1 for t in tests if t.get("pass")), tests_total=len(tests),
                         tests=tests, active_controls=js.get("active"), inert_controls=js.get("inert"),
                         visual_responds=js.get("visual_active"), failures=failures, warnings=warnings[:12],
                         check_seconds=js.get("duration_s"), score=cand.score)
        return cand

    def _revise(self, best, rnd):
        if not self.llm.can_afford(3000) or self.time_left() < 75:
            self.trace.event("revise", "skip", "budget", round=rnd, requests_used=self.llm.requests_made,
                             completion_tokens_used=self.llm.completion_tokens, seconds_left=round(self.time_left(), 1))
            return None
        include_excerpt = any(f.startswith("TEST") or "INVARIANT" in f for f in best.failures)
        msgs = prompts.repair_messages(self.case, best.spec, best.code, best.failures, best.warnings, include_excerpt)
        self.trace.event("revise", "build_repair_prompt", "ok", round=rnd, problems=len(best.failures), include_excerpt=include_excerpt)
        try:
            res = self.llm.chat(msgs, stage="revise", purpose="repair_" + str(rnd), max_tokens=REPAIR_MAX_TOKENS)
        except LLMUnavailable as exc:
            self.trace.event("revise", "llm_call", "unavailable", round=rnd, error=str(exc))
            return None
        rp = parsing.split_repair(res["text"])
        spec = json.loads(json.dumps(best.spec))
        changed = []
        if rp.patch_text and rp.patch_text.strip() not in ("", "{}"):
            patch, perr = parsing.load_json_object(rp.patch_text)
            if isinstance(patch, dict):
                for k, v in patch.items():
                    if k in SPEC_KEYS:
                        spec[k] = v
                        changed.append(k)
            else:
                self.trace.event("revise", "parse_spec_patch", "fail", round=rnd, error=perr)
        code = best.code
        if rp.code and rp.code.strip().upper() != "UNCHANGED":
            code = rp.code
            changed.append("CODE")
        self.trace.event("revise", "apply_repair", "ok" if changed else "no_change", round=rnd, changed=changed, code_complete=rp.complete)
        if not changed:
            return None
        return self._evaluate("revision_" + str(rnd), spec, code)

    def _finish(self, best, rounds) -> int:
        html = render.render_page(best.spec, best.code, model=self.model, case=self.case, checks_info=best.js)
        fails, warns = checks.static_html_checks(html)
        self.trace.event("check", "static_html_checks", "pass" if not fails else "fail", failures=fails, warnings=warns,
                         bytes=len(html.encode("utf-8")))
        path = self.out_dir / "index.html"
        path.write_text(html, encoding="utf-8")
        self.trace.event("output", "write_index_html", "ok", path=str(path), bytes=len(html.encode("utf-8")))
        self._summary("success" if not best.failures else "completed_with_unresolved_issues", best, rounds, 0)
        return 0

    def _fail(self, reason) -> int:
        (self.out_dir / "index.html").write_text(render.render_fallback(self.case, reason), encoding="utf-8")
        self.trace.event("output", "write_fallback_page", "ok", reason=reason)
        self._summary("failed", None, 0, 1)
        return 1

    def _summary(self, status, best, rounds, exit_code):
        llm, tests = self.llm, ((best.js or {}).get("tests", []) if best else [])
        self.trace.event("summary", "run_complete", status, exit_code=exit_code, requests=llm.requests_made,
                         prompt_tokens=llm.prompt_tokens, completion_tokens=llm.completion_tokens,
                         reasoning_tokens=getattr(llm, "reasoning_tokens", 0), total_tokens=llm.prompt_tokens + llm.completion_tokens,
                         elapsed_s=round(time.monotonic() - T0, 2), revision_rounds=rounds,
                         tests_passed=sum(1 for t in tests if t.get("pass")), tests_total=len(tests),
                         final_failures=(best.failures if best else None), final_warnings=(best.warnings[:10] if best else None))


def _dotenv_key() -> str:
    """Development convenience only: read OPENROUTER_API_KEY from a local, git-ignored .env file."""
    for base in (Path.cwd(), ROOT):
        p = base / ".env"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                k, sep, v = line.partition("=")
                if sep and k.strip().removeprefix("export ").strip() == "OPENROUTER_API_KEY":
                    return v.strip().strip('"').strip("'")
    return ""


def _load_case(path, trace):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            case = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        trace.event("input", "load_case", "error", error=type(exc).__name__ + ": " + str(exc))
        return None
    if not isinstance(case, dict):
        trace.event("input", "load_case", "error", error="case.json must contain a JSON object")
        return None
    missing = [k for k in ("source_url", "focus", "audience") if not str(case.get(k) or "").strip()]
    trace.event("input", "load_case", "ok" if not missing else "ok_with_gaps", missing=missing or None,
                fields={k: (len(v) if isinstance(v, str) else type(v).__name__) for k, v in case.items()},
                excerpt_chars=len(prompts.excerpt_text(case)), network_note="paper URL is never fetched; only OpenRouter is contacted")
    return case


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Paper to Playground generator")
    ap.add_argument("--input", required=True, help="path to case.json")
    ap.add_argument("--output", required=True, help="output directory (index.html, trace.jsonl)")
    ap.add_argument("--model", required=True, help="OpenRouter model id")
    args = ap.parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = Trace(out_dir / "trace.jsonl", T0)
    deadline = T0 + HARD_LIMIT_S - SAFETY_S
    try:
        trace.event("setup", "start", "ok", model=args.model, python=sys.version.split()[0], js_engine=checks.engine_available(),
                    limits={"requests": MAX_REQUESTS, "completion_tokens": MAX_COMPLETION_TOKENS, "seconds": HARD_LIMIT_S,
                            "internal_deadline_s": HARD_LIMIT_S - SAFETY_S, "max_repairs": MAX_REPAIRS})
        case = _load_case(args.input, trace)
        if case is None:
            (out_dir / "index.html").write_text(render.render_fallback({}, "invalid case.json"), encoding="utf-8")
            return 2
        key = os.environ.get("OPENROUTER_API_KEY", "").strip() or _dotenv_key()
        if not key:
            trace.event("setup", "read_api_key", "error", error="OPENROUTER_API_KEY is not set")
            (out_dir / "index.html").write_text(render.render_fallback(case, "OPENROUTER_API_KEY is not set"), encoding="utf-8")
            return 2
        trace.event("setup", "read_api_key", "ok")
        llm = OpenRouterClient(key, args.model, trace, deadline, MAX_REQUESTS, MAX_COMPLETION_TOKENS)
        return Pipeline(case, llm, trace, out_dir, args.model, deadline).run()
    except Exception as exc:
        trace.event("fatal", "unhandled_exception", "error", error=type(exc).__name__ + ": " + str(exc))
        try:
            if not (out_dir / "index.html").exists():
                (out_dir / "index.html").write_text(render.render_fallback({}, "internal error: " + type(exc).__name__), encoding="utf-8")
        except Exception:
            pass
        return 1
    finally:
        trace.close()


if __name__ == "__main__":
    sys.exit(main())

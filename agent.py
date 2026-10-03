"""Paper to Playground: research-paper excerpt -> interactive HTML explainer.

python agent.py --input case.json --output out --model MODEL_ID
"""
import argparse
import json
import os
import sys
from pathlib import Path

from core.checks import check_page, check_spec
from core.llm import LLM, BudgetExceeded
from core.prompts import generate_messages, revise_messages
from core.render import render
from core.source import get_excerpt
from core.trace import Trace

MAX_REVISIONS = 2


def load_dotenv():
    """Dev convenience only; assessment sets OPENROUTER_API_KEY in the environment."""
    env = Path(__file__).with_name(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    load_dotenv()
    out = Path(args.output)
    trace = Trace(out / "trace.jsonl")
    case = json.loads(Path(args.input).read_text(encoding="utf-8"))
    trace.log("input", "load_case", "ok", fields=sorted(case))

    llm = LLM(args.model, trace)
    spec, page = None, None
    try:
        excerpt = get_excerpt(case, trace)
        messages = generate_messages(case, excerpt)
        for attempt in range(MAX_REVISIONS + 1):
            raw = llm.chat("generate" if attempt == 0 else "revise", messages, json_mode=True)
            try:
                spec = parse_json(raw)
            except json.JSONDecodeError as e:
                failures = [f"invalid JSON: {e}"]
            else:
                page = render(spec)
                failures = check_spec(spec) + check_page(page)
            trace.log("check", f"attempt_{attempt}", "pass" if not failures else "fail", failures=failures)
            if not failures:
                break
            messages = revise_messages(raw, failures)
    except BudgetExceeded as e:
        trace.log("budget", "stop", "exceeded", reason=str(e))

    if page is None:
        trace.log("output", "write_page", "fail", usage=llm.usage())
        return 1
    (out / "index.html").write_text(page, encoding="utf-8")
    trace.log("output", "write_page", "ok", usage=llm.usage())
    return 0


if __name__ == "__main__":
    sys.exit(main())

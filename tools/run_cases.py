#!/usr/bin/env python3
"""Run agent.py on every practice case and print requests, tokens, latency and check results.
Usage: python tools/run_cases.py --model MODEL_ID [--cases examples/cases] [--out runs]"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summary(trace: Path) -> dict:
    s = {}
    if trace.is_file():
        for line in trace.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("stage") == "summary":
                s = e
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cases", default=str(ROOT / "examples" / "cases"))
    ap.add_argument("--out", default=str(ROOT / "runs"))
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    from p2p.checks import engine_available
    if sys.version_info[:2] != (3, 11) or not engine_available():
        # A run without the JS engine executes no checks, so every case "succeeds" untested: never let that pass silently.
        print("=" * 78 + "\nWARNING: Python %s, JavaScript engine available: %s.\nThe assessment uses Python 3.11 with "
              "quickjs; without it NO executable checks run and results are not comparable.\nUse the project venv: "
              ".venv\\Scripts\\python.exe tools/run_cases.py ...  (macOS/Linux: .venv/bin/python)\n" % (
                  sys.version.split()[0], engine_available()) + "=" * 78)
    rows = []
    for case in sorted(Path(args.cases).glob("*.json")):
        out = Path(args.out) / case.stem
        if out.exists():
            shutil.rmtree(out)
        t = time.monotonic()
        proc = subprocess.run([sys.executable, str(ROOT / "agent.py"), "--input", str(case), "--output", str(out), "--model", args.model])
        s = summary(out / "trace.jsonl")
        rows.append((case.stem, proc.returncode, round(time.monotonic() - t, 1), s.get("requests"), s.get("prompt_tokens"),
                     s.get("completion_tokens"), s.get("total_tokens"), str(s.get("tests_passed")) + "/" + str(s.get("tests_total")),
                     s.get("revision_rounds"), s.get("result")))
        print("done:", rows[-1])
    head = ("case", "exit", "sec", "req", "prompt", "compl", "total", "tests", "rev", "result")
    print("\n" + " | ".join(head))
    for r in rows:
        print(" | ".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

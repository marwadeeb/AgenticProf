"""Trace writer: one JSON object per line in out/trace.jsonl. Owner: Member A.

Every event has stage, action, result, and elapsed seconds since process start.
Never log credentials or hidden reasoning.
"""
import json
import time
from pathlib import Path

START = time.time()


class Trace:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def log(self, stage: str, action: str, result: str, **extra):
        event = {"t": round(time.time() - START, 3), "stage": stage, "action": action, "result": result, **extra}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

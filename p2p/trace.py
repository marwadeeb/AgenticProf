"""Append-only JSONL execution trace. Never records credentials or hidden reasoning."""
from __future__ import annotations

import datetime as _dt
import json
import re
import time
from pathlib import Path

_SECRET = re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-.]{8,}")


class Trace:
    def __init__(self, path, t0: float):
        self.path = Path(path)
        self.t0 = t0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")
        self.count = 0

    def event(self, stage: str, action: str, result: str, **data):
        self.count += 1
        rec = {
            "seq": self.count,
            "t": round(time.monotonic() - self.t0, 3),
            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds"),
            "stage": stage,
            "action": action,
            "result": result,
        }
        for k, v in data.items():
            if v is not None:
                rec[k] = v
        line = _SECRET.sub("[REDACTED]", json.dumps(rec, ensure_ascii=False, default=str))
        if self._fh and not self._fh.closed:
            self._fh.write(line + "\n")
            self._fh.flush()
        return rec

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass

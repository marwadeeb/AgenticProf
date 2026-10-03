"""OpenRouter client with hard budget guards. Owner: Member A.

Assessment limits per case: <=10 requests (incl. retries), <=30k completion tokens, <=10 min.
We stop well before them. Reasoning is disabled by default: on DeepSeek V4.1 Flash it
multiplied completion tokens ~25x for the same answer, and tokens are scored.
"""
import os
import time

import requests

from core.trace import START, Trace

URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_REQUESTS = 8              # hard limit is 10; keep headroom
MAX_COMPLETION_TOKENS = 26000  # hard limit is 30k
DEADLINE_S = 480              # hard limit is 600s


class BudgetExceeded(Exception):
    pass


class LLM:
    def __init__(self, model: str, trace: Trace):
        self.model = model
        self.trace = trace
        self.key = os.environ.get("OPENROUTER_API_KEY")
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def chat(self, stage: str, messages: list, max_tokens: int = 8000, json_mode: bool = False) -> str:
        if self.requests >= MAX_REQUESTS:
            raise BudgetExceeded("request budget exhausted")
        if self.completion_tokens + max_tokens > MAX_COMPLETION_TOKENS:
            max_tokens = MAX_COMPLETION_TOKENS - self.completion_tokens
            if max_tokens < 500:
                raise BudgetExceeded("completion token budget exhausted")
        remaining = DEADLINE_S - (time.time() - START)
        if remaining < 30:
            raise BudgetExceeded("time budget exhausted")

        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens,
                "reasoning": {"enabled": False}, "temperature": 0.2}
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        self.requests += 1
        t0 = time.time()
        r = requests.post(URL, headers={"Authorization": f"Bearer {self.key}"}, json=body, timeout=min(240, remaining))
        elapsed = round(time.time() - t0, 2)
        if r.status_code != 200:
            self.trace.log(stage, "llm_call", "error", status=r.status_code, body=r.text[:300], elapsed_s=elapsed)
            r.raise_for_status()
        data = r.json()
        u = data.get("usage", {})
        self.prompt_tokens += u.get("prompt_tokens", 0)
        self.completion_tokens += u.get("completion_tokens", 0)
        choice = data["choices"][0]
        self.trace.log(stage, "llm_call", "ok", request_no=self.requests,
                       prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                       reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                       finish_reason=choice.get("finish_reason"), elapsed_s=elapsed, generation_id=data.get("id"))
        return choice["message"]["content"] or ""

    def usage(self) -> dict:
        return {"requests": self.requests, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens}

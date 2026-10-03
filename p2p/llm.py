"""Minimal OpenRouter chat client with hard request / completion-token / time budgets.

Every HTTP attempt (including retries) counts against the request budget, and each call's
max_tokens is capped by the remaining completion-token budget, so the per-case limits
(10 requests, 30,000 completion tokens, 10 minutes) cannot be exceeded."""
from __future__ import annotations

import os
import time

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
SAFETY_TOKENS = 200
# Model families whose reasoning is on by default: ask for low effort to save tokens. For other
# models nothing is sent (sending an effort would switch extended thinking ON for e.g. Claude).
REASONING_PREFIXES = (
    "openai/o1", "openai/o3", "openai/o4", "openai/gpt-5", "openai/gpt-oss", "deepseek/deepseek-r1",
    "google/gemini-2.5", "google/gemini-3", "x-ai/grok-3-mini", "x-ai/grok-4", "qwen/qwq",
    "moonshotai/kimi-k2-thinking", "z-ai/glm-4.5", "z-ai/glm-4.6", "z-ai/glm-5", "minimax/minimax-m",
)
DISABLE_PREFIXES = ("deepseek/deepseek-v4", "deepseek/deepseek-v3.1", "deepseek/deepseek-chat-v3.1", "deepseek/deepseek-v3.2")
TRANSIENT = (408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529)


class LLMUnavailable(RuntimeError):
    """Raised when no further model call is possible (budget, time or unrecoverable API error)."""


def reasoning_setting(model: str):
    env = os.getenv("P2P_REASONING", "auto").strip().lower()
    if env in ("", "off", "omit", "default"):
        return None
    if env in ("disable", "disabled", "none"):
        return {"enabled": False}
    if env != "auto":
        return {"effort": env, "exclude": True}
    m = model.lower().lstrip("~")
    if m.startswith(DISABLE_PREFIXES):
        return {"enabled": False}
    if m.startswith(REASONING_PREFIXES) or "thinking" in m or "-r1" in m:
        return {"effort": "low", "exclude": True}
    return None


class OpenRouterClient:
    def __init__(self, api_key, model, trace, deadline, max_requests=10, max_completion_tokens=30000):
        self.model = model
        self.trace = trace
        self.deadline = deadline
        self.max_requests = max_requests
        self.max_completion_tokens = max_completion_tokens
        self.requests_made = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.reasoning_tokens = 0
        self.reasoning = reasoning_setting(model)
        self.temperature = None if (self.reasoning and "effort" in self.reasoning) else 0.2
        if os.getenv("P2P_TEMPERATURE"):
            try:
                self.temperature = float(os.environ["P2P_TEMPERATURE"])
            except ValueError:
                pass
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "X-Title": "Paper to Playground",
        })

    def completion_left(self) -> int:
        return self.max_completion_tokens - self.completion_tokens

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    def can_afford(self, min_completion: int) -> bool:
        return (self.requests_made < self.max_requests
                and self.completion_left() - SAFETY_TOKENS >= min_completion
                and self.time_left() > 30)

    def chat(self, messages, stage: str, purpose: str, max_tokens: int) -> dict:
        transient = 0
        stripped = False
        while True:
            if self.requests_made >= self.max_requests:
                raise LLMUnavailable("request budget exhausted")
            cap = self.completion_left() - SAFETY_TOKENS
            if cap < 512:
                raise LLMUnavailable("completion-token budget exhausted")
            tl = self.time_left()
            if tl < 20:
                raise LLMUnavailable("time budget exhausted")
            mt = int(min(max_tokens, cap))
            # Same model, but route to the fastest provider: unsorted routing varied 18 s to 166 s per call.
            body = {"model": self.model, "messages": messages, "max_tokens": mt, "usage": {"include": True},
                    "provider": {"sort": os.getenv("P2P_PROVIDER_SORT", "throughput")}}
            if self.temperature is not None:
                body["temperature"] = self.temperature
            if self.reasoning:
                body["reasoning"] = dict(self.reasoning)
            self.requests_made += 1
            rec = {"call": self.requests_made, "purpose": purpose, "model": self.model, "max_tokens": mt,
                   "reasoning_param": self.reasoning,
                   "prompt_chars": sum(len(str(m.get("content", ""))) for m in messages)}
            t = time.monotonic()
            try:
                resp = self.session.post(API_URL, json=body, timeout=(15, max(15.0, tl - 5)))
            except requests.RequestException as exc:
                rec.update(elapsed_s=round(time.monotonic() - t, 2), error=(type(exc).__name__ + ": " + str(exc))[:240])
                self.trace.event(stage, "llm_call", "network_error", **rec)
                transient += 1
                if transient <= 2 and self.time_left() > 60:
                    time.sleep(2.0 * transient)
                    continue
                raise LLMUnavailable(rec["error"])
            rec["elapsed_s"] = round(time.monotonic() - t, 2)
            rec["http_status"] = resp.status_code
            try:
                data = resp.json()
            except ValueError:
                data = None
            data = data if isinstance(data, dict) else {}
            usage = data.get("usage") or {}
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            rt = int(((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0)
            cached = int(((usage.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0)
            self.prompt_tokens += pt
            self.completion_tokens += ct
            self.reasoning_tokens += rt
            rec.update(prompt_tokens=pt, completion_tokens=ct, reasoning_tokens=rt, cached_prompt_tokens=cached,
                       total_tokens=pt + ct, generation_id=data.get("id"))
            choices = data.get("choices") or []
            if resp.status_code == 200 and choices:
                ch = choices[0] or {}
                msg = ch.get("message") or {}
                text = msg.get("content") or ""
                if isinstance(text, list):
                    text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                fr = ch.get("finish_reason")
                rec.update(finish_reason=fr, native_finish_reason=ch.get("native_finish_reason"), output_chars=len(text))
                if not text.strip() and fr not in ("length", "max_tokens") and transient < 1 and self.time_left() > 60:
                    self.trace.event(stage, "llm_call", "empty_output_retry", **rec)
                    transient += 1
                    continue
                self.trace.event(stage, "llm_call", "ok", **rec)
                return {"text": text, "finish_reason": fr, "usage": rec}
            err = data.get("error")
            emsg = (err.get("message") if isinstance(err, dict) else str(err or "")) or resp.text[:300]
            rec["error"] = str(emsg)[:300]
            self.trace.event(stage, "llm_call", "error", **rec)
            if resp.status_code == 400 and not stripped and (self.reasoning or self.temperature is not None):
                stripped = True  # an optional parameter may be unsupported: retry once without them
                self.reasoning = None
                self.temperature = None
                continue
            if resp.status_code in TRANSIENT or (resp.status_code == 200 and not choices):
                transient += 1
                if transient <= 2 and self.time_left() > 60:
                    time.sleep(min(10.0, 2.0 * transient + (3.0 if resp.status_code == 429 else 0.0)))
                    continue
            raise LLMUnavailable("OpenRouter HTTP " + str(resp.status_code) + ": " + str(emsg)[:200])

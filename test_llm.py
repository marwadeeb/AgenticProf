"""Smoke test for OpenRouter: a plain call and a tool-use round trip, with token usage and latency."""
import argparse
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()
URL = "https://openrouter.ai/api/v1/chat/completions"


def call(model, messages, **extra):
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or "your-key-here" in key:
        sys.exit("OPENROUTER_API_KEY not set in .env")
    t = time.time()
    r = requests.post(URL, headers={"Authorization": f"Bearer {key}"},
                      json={"model": model, "messages": messages, **extra}, timeout=120)
    r.raise_for_status()
    data = r.json()
    u = data.get("usage", {})
    print(f"  [{time.time() - t:.1f}s] prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')}")
    return data["choices"][0]["message"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="openai/gpt-4o-mini")
    model = p.parse_args().model

    print(f"[test] plain call ({model})")
    print("  ->", call(model, [{"role": "user", "content": "Say hi in 3 words."}])["content"])

    print("[test] tool call")
    tools = [{"type": "function", "function": {
        "name": "add", "description": "Add two numbers.",
        "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
    }}]
    messages = [{"role": "user", "content": "What is 1234 + 5678? Use the add tool."}]
    msg = call(model, messages, tools=tools)
    tc = msg["tool_calls"][0]
    args = json.loads(tc["function"]["arguments"])
    print(f"  -> {tc['function']['name']}({args})")
    messages += [msg, {"role": "tool", "tool_call_id": tc["id"], "content": str(args["a"] + args["b"])}]
    print("  ->", call(model, messages, tools=tools)["content"])
    print("[ok] OpenRouter works")

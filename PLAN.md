# Team plan

## Ownership (only edit your own files; `core/schema.py` changes together)

| Member A: agent pipeline | Member B: page + checks |
|---|---|
| `agent.py`, `core/llm.py`, `core/trace.py`, `core/source.py`, `core/prompts.py` | `templates/page.html`, `core/render.py`, `core/checks.py`, `cases/`, `README.md` |

## Facts we know

- Assessment model: `deepseek/deepseek-v4.1-flash`. Reasoning is **disabled** in `core/llm.py` (it costs ~25x completion tokens for the same answer).
- Limits per case: 10 requests, 30k completion tokens, 10 min. Our guards: 8 / 26k / 480 s.
- Score: 85 quality (accuracy 25, clarity 20, visual 15, interaction 15, autonomy+checks 10) + 15 efficiency (tokens 10, latency 5). Efficiency only counts if quality >= 50/85.
- Skeleton baseline: 1 call, ~3.2k tokens, ~9 s.

## Open questions for the instructor

1. case.json has "five required fields" but only 3 are listed. What are the other 2?
2. Network is limited to OpenRouter during assessment. Is the excerpt inside case.json?

## Git loop (every 20-30 min)

```
git pull --rebase
git add -A
git commit -m "..."
git push
```

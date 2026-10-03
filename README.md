# Paper to Playground

EECE503P / EECE798S Agentic Systems hackathon. `agent.py` turns a research-paper excerpt and a learning brief into a single, offline, interactive HTML explainer (`out/index.html`) plus an execution trace (`out/trace.jsonl`).

**Team:** Laure Mohsen, Marwa Deeb

**MODEL_ID:** the instructor-supplied OpenRouter model, passed as `--model MODEL_ID`. Assessment model: `deepseek/deepseek-v4.1-flash` (DeepSeek V4.1 Flash).

## Setup and usage

```bash
python -m pip install -r requirements.txt          # Python 3.11
export OPENROUTER_API_KEY=sk-or-...                 # never committed; a git-ignored .env also works for development
python agent.py --input examples/cases/attention.json --output out --model MODEL_ID
python -m http.server -d out 8000                   # then open http://localhost:8000 (or open out/index.html directly)
```

Exit codes: `0` page generated, `1` generation failed (a fallback page and the trace are still written), `2` invalid input or missing key.

## Architecture

```
case.json ─► 1. PLAN + GENERATE  one LLM call returns a short plan, a SPEC (JSON: texts, controls,
             │                   explorations, grounding) and CODE (JS: compute / view / readout / insight / TESTS)
             ▼
          2. CHECK (0 tokens)    • SPEC schema + teaching-structure validation (≥2 controls, exactly 2 explorations,
             │                     limitation, grounding), with safe auto-fixes
             │                   • static safety: offline, no DOM, no network, deterministic
             │                   • EXECUTES the CODE in QuickJS (subprocess, time-limited): defaults, both exploration
             │                     presets, the model's own TESTS, every control at its range ends, all-zero / tied
             │                     vectors, 6 random states; detects exceptions, NaN/undefined in displayed output,
             │                     malformed SVG, controls that change nothing, a static visual
             ▼  failures?
          3. REVISE (≤2 rounds)  compact repair prompt (failing checks + SPEC subset + CODE; the excerpt only when a
             │                   scientific TEST failed) → re-check → keep the best-scoring candidate
             ▼
          4. RENDER              generic template → one self-contained HTML file (inline CSS/JS/SVG, no CDN/fonts)
```

The page contains: the idea, why it matters, the key equation with its section, a symbol table; a playground (auto-built controls, an SVG visual recomputed on every change, a one-sentence live interpretation, intermediate values and tables); two guided explorations with one-click starting states; a limitation / assumption / misconception; source grounding that separates claims supported by the excerpt from our examples and simplifications, with an explicit scope disclaimer; and the model's correctness checks, re-run live in the browser.

**Token efficiency.** Normally exactly one call: the model writes only content and the mechanism-specific maths and drawing code, never HTML/CSS boilerplate (the template and a small SVG helper library `V` do that). Checks run locally at zero token cost; repairs happen only when an executed check fails and send a compact prompt. Reasoning effort is set to `low` for model families that reason by default thinking is disabled for hybrid models such as DeepSeek V4.1 Flash, and other models are left at their default.

**Limits.** The paper URL is never fetched; the only network calls go to `https://openrouter.ai/api/v1/chat/completions`. Every HTTP attempt, including retries, counts towards the 10-request cap; each call's `max_tokens` is capped by the remaining 30,000-token completion budget; an internal deadline of 560 s keeps runs inside 10 minutes. Per-call prompt, completion, reasoning and cached tokens, latency, finish reason and the OpenRouter generation id are logged. Credentials and hidden reasoning are never logged.

## Reader features (all zero-token: handled by the template, no extra model output)

- **Display settings** in the header: light/dark theme, colour palettes (standard, colour-blind safe Okabe-Ito, high contrast, greyscale), text size, show/hide formulas and notes, and a *predict before reveal* mode for the explorations. Settings can also be set by URL hash, e.g. `index.html#theme=dark&palette=colorblind&size=1.25`.
- **Live invariant checks** (e.g. "each row of weights sums to 1 ✓") recomputed on every input change; the same invariants are verified by the generator on every state it executes.
- **Numbered calculation chain** of intermediate values with the substituted formula, and change highlighting (▲/▼) after each edit, so cause and effect are visible.
- **One-click exploration states**, and the full **source excerpt** in a collapsible panel next to the grounding lists.
- **Agent-friendly controls**: stable ids (`in-<control>`, `in-<matrix>-<row>-<col>`, `explore-1`, `reveal-1`, `p2p-reset`, `set-*`) and a small API `window.p2p.get() / set(id, value) / load(i)`.

## Trace format (`out/trace.jsonl`)

One JSON object per line with `seq`, `t` (seconds since process start), `ts`, `stage`, `action`, `result` plus details. Stages: `setup`, `input`, `plan` (prompt strategy and the model's plan), `generate` (`llm_call` with token counts), `parse`, `check` (`evaluate_candidate`: tests run and passed, active/inert controls, failures, warnings; `static_html_checks`), `revise` (repair prompts, `accept_revision` accepted/rejected), `output`, and a final `summary` with total requests, tokens, elapsed time and remaining issues.

## Configuration (optional environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `P2P_REASONING` | `auto` | `auto`, `disable` (thinking off), `omit` (send nothing), or an effort (`low`, `medium`, `high`) |
| `P2P_MAX_REPAIRS` | `2` | maximum repair rounds |
| `P2P_GEN_MAX_TOKENS` / `P2P_REPAIR_MAX_TOKENS` | `14000` / `9000` | per-call caps (always also bounded by the remaining budget) |
| `P2P_SAFETY_SECONDS` | `40` | margin below the 600 s limit |

## Repository layout

```
agent.py                 CLI + pipeline (generate → check → revise → render)
p2p/llm.py               OpenRouter client with hard budgets and usage logging
p2p/prompts.py           generation, repair and JSON-fix prompts
p2p/parsing.py           marker/fence parsing, lenient JSON
p2p/spec.py              SPEC validation and normalisation
p2p/checks.py            static checks + executable checks; p2p/jscheck.py runs QuickJS in a subprocess
p2p/render.py            HTML rendering with a strict inline-tag whitelist
p2p/assets/              template.html, vlib.js (SVG helpers + parameter normalisation), runtime.js (page), harness.js (checker)
examples/cases/          six practice inputs (both public examples + Adam, BatchNorm, positional encoding, PageRank)
tests/offline_check.py   offline self-test with a toy fixture and a scripted fake LLM
tools/run_cases.py       runs every practice case and tabulates requests, tokens, latency and test results
```

## Testing

```bash
python tests/offline_check.py                       # no key or network needed
python tools/run_cases.py --model MODEL_ID          # all practice cases, results in runs/<case>/
```

## Example input/output

`examples/cases/attention.json` → `examples/attention_output/` (`index.html`, `trace.jsonl`), produced with
`python agent.py --input examples/cases/attention.json --output examples/attention_output --model MODEL_ID`.
Assessed outputs are generated afresh; this pair is only a showcase.

## Credits

- [QuickJS](https://bellard.org/quickjs/) (MIT, Fabrice Bellard and Charlie Gordon) through the [`quickjs`](https://github.com/PetterS/quickjs) Python binding (MIT, Petter Strandmark): executes generated JavaScript during self-checks.
- [requests](https://requests.readthedocs.io/) (Apache-2.0) and its dependencies.
- The template, SVG helper library, runtime, checker and agent were written for this project with the help of an AI coding assistant (Claude, Anthropic). Practice-case excerpts are short paraphrases written by us; the generator contains no paper-specific content.

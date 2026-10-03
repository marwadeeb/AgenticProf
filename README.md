# Paper to Playground

EECE503P / EECE798S Agentic Systems hackathon. `agent.py` turns a research-paper excerpt and a learning brief into a single, offline, interactive HTML explainer (`out/index.html`) plus an execution trace (`out/trace.jsonl`). The repository is the reusable generator; the pages are its results.

**Team:** Laure Mohsen, Marwa Deeb

**MODEL_ID:** passed as `--model MODEL_ID`. Developed and tested with the assessment model **`deepseek/deepseek-v4.1-flash`** (DeepSeek V4.1 Flash on OpenRouter).

## Setup and usage

```bash
python -m pip install -r requirements.txt          # Python 3.11
export OPENROUTER_API_KEY=sk-or-...                 # PowerShell: $env:OPENROUTER_API_KEY="sk-or-..."  (a git-ignored .env also works)
python agent.py --input examples/cases/attention.json --output out --model deepseek/deepseek-v4.1-flash
python -m http.server -d out 8000                   # then open http://localhost:8000
```

Exit codes: `0` page generated, `1` generation failed (a readable fallback page and the trace are still written), `2` invalid input or missing key.

Dependencies (all pure wheels, no system packages): `requests`, `quickjs` (executes the generated JavaScript during checks), `latex2mathml` (renders equations in textbook form at generation time).

## Architecture

```
case.json ─► 1. PLAN + GENERATE   ONE LLM call returns a short plan, a SPEC (JSON: texts, LaTeX equation, controls,
             │                    explorations, caveats, grounding) and CODE (JS: compute / view / readout / insight /
             │                    TESTS / INVARIANTS). The fixed template writes all HTML/CSS, so the model never does.
             ▼
          2. CHECK  (0 tokens)    • SPEC validation (≥2 controls, exactly 2 explorations, caveats, grounding)
             │                    • static safety: offline, no DOM, no network, deterministic
             │                    • EXECUTES the code in QuickJS (subprocess, time-limited) on the defaults, both
             │                      exploration presets, the model's own TESTS, every control at its range ends,
             │                      zero / tied inputs and random states; checks INVARIANTS on every state;
             │                      catches exceptions, NaN / leaked `undefined`, broken SVG, inert controls,
             │                      a static visual, tests that use unknown or mis-sized inputs.
             │                      Every failure carries the actual computed values, so a repair can see the bug.
             ▼  failures?
          3. REVISE (≤3 rounds)   escalation ladder, each step only if the previous one did not fix a maths failure:
             │                    plain repair → repair with a ≤120-word visible derivation → repair with capped
             │                    hidden reasoning. A repair returns ONLY the functions it changes (spliced in by
             │                    name, verified so no declaration is ever lost). The best-scoring candidate is kept.
             ▼
          4. RENDER               LaTeX → MathML, claims linked to excerpt sentences, one self-contained HTML file
```

### Why this design (measured, not guessed)

| Decision | Evidence from our runs |
|---|---|
| Reasoning **off** for generation | Same answer, completion tokens 103 → 4 on a probe; reasoning counts towards the token score |
| One generation call, template does the boilerplate | ~7k total tokens for a clean case |
| Patch-style repairs (changed functions only) | repair completion ≈ 3,000 → 400–900 tokens; average −22% tokens |
| Value-level diagnostics in failures | the attention case went from 0/6 tests after repairs to passing |
| Stop a repair loop that makes no progress | an identical prompt returned an identical answer in 7/7 observed cases |
| Escalation ladder (derivation, then capped reasoning) | fixed maths bugs (rotation formula, alias phase) that plain repairs never fixed |
| Fastest-provider routing for the same model | per-call latency varied 18–166 s with default routing |

**Last measured run (12 practice cases; Bloom filter, momentum and Huffman coding were run for the first time):** 12/12 pages generated with exit 0, 11/12 with every check passing, 8/12 clean in a single call, median ≈ 7.9k tokens and ≈ 18 s per case (mean 13.4k tokens, pulled up by cases that needed repairs).

## What every generated page contains

1. **The idea**: plain-language idea, why it matters, the key equation in textbook form (MathML, rendered natively, works offline), the source section, a symbol table, and **"With your numbers"**: the equation's last step with the current values substituted, updated live.
2. **Playground**: auto-built controls (sliders, toggles, selects, editable vectors/matrices), an SVG visual recomputed on every change (with animated transitions, automatic label de-cluttering and canvas fitting), a one-sentence live interpretation, live invariant checks (✓/✗), and a numbered step-by-step chain of intermediate values with the substituted formula and change highlighting.
3. **Two guided explorations**: Do → See → Why → Then (a follow-up that deepens the point), each with a one-click starting state; optional quiz mode hides the answers.
4. **Assumptions, limits and pitfalls**: one assumption, one limitation and one common misunderstanding, each explained and, where possible, tied to the playground.
5. **Source grounding**: claims supported by the excerpt (each shown with the **excerpt sentence that supports it**, matched locally at zero token cost) separated from our own examples and simplifications, the full excerpt, and an explicit scope statement (a toy demonstration, not a reproduction of the paper's results).
6. **Built-in correctness checks**: the model's TESTS, verified by the generator before the page was written and re-run live in the browser.

Also: shareable state links ("Copy link to this state" stores the playground state in the URL), a progress path, light/dark theme, colour-blind-safe and high-contrast palettes, text size, phone-width layout, and stable element ids plus `window.p2p.get() / set(id, value) / load(i)` for automated use.

**No unusable page.** Every optional feature is guarded; if the playground code fails, the explanation still renders with a clear message; if no model output is usable at all, a readable study page (brief + source excerpt) is written instead of a blank.

## Limits and budgets

The paper URL is never fetched; the only network calls go to `https://openrouter.ai/api/v1/chat/completions`. Every HTTP attempt, including retries, counts towards the 10-request cap; each call's `max_tokens` is capped by the remaining 30,000-token completion budget; an internal deadline of 560 s keeps runs inside 10 minutes. Credentials and hidden reasoning are never logged.

## Trace format (`out/trace.jsonl`)

One JSON object per line with `seq`, `t` (seconds since start), `ts`, `stage`, `action`, `result` plus details. Stages: `setup` (Python version, JS engine), `input`, `plan` (prompt strategy and the model's plan), `generate` (`llm_call`: prompt / completion / reasoning / cached tokens, latency, finish reason, OpenRouter generation id), `parse`, `check` (`evaluate_candidate`: states executed, tests passed, active / inert controls, failures with values), `revise` (`build_repair_prompt` with escalation level, `apply_repair` with the changed functions, `accept_revision` accepted / rejected, `stop`), `output`, and `summary` (requests, tokens, elapsed time, remaining issues).

## Configuration (optional environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `P2P_REASONING` | `auto` | generation reasoning: `auto` (off for DeepSeek V4.x), `disable`, `omit`, or an effort |
| `P2P_MAX_REPAIRS` | `3` | maximum repair rounds |
| `P2P_THINK_TOKENS` | `1500` | reasoning cap for the last escalation step |
| `P2P_PROVIDER_SORT` | `throughput` | OpenRouter provider ordering for the same model |
| `P2P_GEN_MAX_TOKENS` / `P2P_REPAIR_MAX_TOKENS` | `14000` / `9000` | per-call caps (always bounded by the remaining budget) |

## Repository layout

```
agent.py                 CLI + pipeline (generate → check → revise → render)
p2p/llm.py               OpenRouter client: hard budgets, retries, usage logging, provider routing
p2p/prompts.py           generation, repair and JSON-fix prompts
p2p/parsing.py           marker/fence parsing, lenient JSON, LaTeX-safe backslash handling
p2p/spec.py              SPEC validation and normalisation
p2p/checks.py            static + executable checks; p2p/jscheck.py runs QuickJS in a subprocess
p2p/jspatch.py           splices repaired functions into the code by name, never losing a declaration
p2p/mathml.py            LaTeX (and plain-text maths) → sanitised MathML
p2p/render.py            HTML rendering, claim → excerpt matching, fallback page
p2p/assets/              template.html, vlib.js (SVG helpers), runtime.js (page), harness.js (checker)
examples/cases/          12 practice inputs: the two public examples + Adam, BatchNorm, positional encoding,
                         PageRank, Kalman filter, dropout, sampling theorem, Bloom filter, momentum, Huffman coding
examples/attention_output/  showcase output for examples/cases/attention.json
tests/offline_check.py   offline self-test (29 checks, no key or network needed)
tools/run_cases.py       runs every practice case; warns loudly if the JS engine is missing
```

## Testing

```bash
python tests/offline_check.py                                         # no key or network needed
python tools/run_cases.py --model deepseek/deepseek-v4.1-flash          # all practice cases → runs/<case>/
```

Use Python 3.11 (the project venv): on Python 3.13+ `quickjs` has no wheel, the executable checks are skipped and `run_cases.py` prints a warning.

## Example input/output

`examples/cases/attention.json` → `examples/attention_output/` (`index.html`, `trace.jsonl`), produced with
`python agent.py --input examples/cases/attention.json --output examples/attention_output --model deepseek/deepseek-v4.1-flash`.
Assessed outputs are generated afresh; this pair is only a showcase.

## Credits

- [QuickJS](https://bellard.org/quickjs/) (MIT, Fabrice Bellard and Charlie Gordon) through the [`quickjs`](https://github.com/PetterS/quickjs) Python binding (MIT, Petter Strandmark): executes generated JavaScript during checks.
- [latex2mathml](https://github.com/roniemartinez/latex2mathml) (MIT, Ronie Martinez): LaTeX to MathML conversion.
- [requests](https://requests.readthedocs.io/) (Apache-2.0) and its dependencies.
- The agent, template, SVG helper library, runtime and checker were written for this project with the help of AI coding assistants (Claude, Anthropic). Practice-case excerpts are short paraphrases written by us; the generator contains no paper-specific content.

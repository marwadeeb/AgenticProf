# Paper to Playground

An agent that turns a focused research-paper excerpt into a single-file, offline, interactive HTML explainer.

**Team:** TODO (Member A), TODO (Member B)

## Run

```bash
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=...        # PowerShell: $env:OPENROUTER_API_KEY="..."
python agent.py --input cases/entropy.json --output out --model deepseek/deepseek-v4.1-flash
```

**MODEL_ID:** `deepseek/deepseek-v4.1-flash` (any OpenRouter model ID works).

Outputs: `out/index.html` (self-contained page) and `out/trace.jsonl` (one event per line).

## Architecture

TODO: diagram + short description of each stage.

```
case.json -> source (excerpt) -> generate (1 LLM call -> JSON spec) -> render (template) -> checks -> revise (only if checks fail) -> index.html + trace.jsonl
```

## Example

TODO: one input/output pair under `examples/`.

## Credits

TODO: list reused code and assets.

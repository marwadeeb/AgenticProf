"""Prompts for generation and revision. Owner: Member A.

Keep them short: every prompt token is scored.
"""
from core.schema import SPEC_KEYS

SYSTEM = "You build interactive, scientifically accurate explainers of one research-paper mechanism. Reply with JSON only."


def generate_messages(case: dict, excerpt: str) -> list:
    # TODO(A): tune wording; this is the first working draft.
    spec = "\n".join(f'- "{k}": {v}' for k, v in SPEC_KEYS.items())
    user = (f"Paper: {case.get('source_url')}\nAudience: {case.get('audience')}\nFocus: {case.get('focus')}\n"
            f"Excerpt:\n{excerpt or '(none provided)'}\n\nReturn a JSON object with keys:\n{spec}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def revise_messages(spec_json: str, failures: list) -> list:
    # TODO(A): send only the failing parts, not the whole spec, to save tokens.
    user = "Fix these problems and return the full corrected JSON:\n- " + "\n- ".join(failures) + f"\n\nJSON:\n{spec_json}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

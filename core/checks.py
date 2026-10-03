"""Deterministic checks on the spec and rendered page. Owner: Member B.

Returns a list of human-readable failures; empty list = pass. No LLM calls here.
"""
import re

from core.schema import REQUIRED_KEYS


def check_spec(spec: dict) -> list:
    failures = [f"missing key: {k}" for k in REQUIRED_KEYS if not spec.get(k)]
    if len(spec.get("controls", [])) < 2:
        failures.append("need at least 2 controls")
    if len(spec.get("explorations", [])) != 2:
        failures.append("need exactly 2 guided explorations")
    # TODO(B): run spec['tests'] against compute_js with quickjs; report mismatches with actual values.
    # TODO(B): syntax-check compute_js and render_js with quickjs.
    return failures


def check_page(page: str) -> list:
    failures = []
    if re.search(r"""(src|href)\s*=\s*["']https?://""", page) or "@import url(http" in page:
        failures.append("page references an external URL (must work offline)")
    # TODO(B): check every control id in spec exists in the page.
    return failures

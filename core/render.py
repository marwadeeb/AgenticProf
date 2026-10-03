"""Inject the spec into templates/page.html -> one self-contained HTML file. Owner: Member B."""
import html
import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "page.html"


def render(spec: dict) -> str:
    # TODO(B): real layout; for now the template just receives the spec as JSON + the JS functions.
    page = TEMPLATE.read_text(encoding="utf-8")
    data = {k: v for k, v in spec.items() if k not in ("compute_js", "render_js")}
    return (page.replace("{{TITLE}}", html.escape(spec.get("title", "Explainer")))
                .replace("{{SPEC_JSON}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                .replace("{{COMPUTE_JS}}", spec.get("compute_js", ""))
                .replace("{{RENDER_JS}}", spec.get("render_js", "")))

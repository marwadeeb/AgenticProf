"""THE SHARED CONTRACT between Member A (generation) and Member B (render + checks).

The LLM returns one JSON object with these keys. Change this file only together.
"""

SPEC_KEYS = {
    "title": "short page title",
    "paper": "paper title + authors/year",
    "section": "section / equation the concept comes from, e.g. 'Sec. 3.2.1, Eq. (1)'",
    "intro_html": "the idea + why it matters, for the given audience (HTML fragment)",
    "symbols": "list of {symbol, meaning}",
    "controls": "list of {id, label, type: 'range'|'number'|'checkbox'|'select', min, max, step, value, options}",
    "compute_js": "JS source defining function compute(inputs) -> object of results; pure, no DOM",
    "render_js": "JS source defining function render(inputs, results, el) that draws the visual into el (SVG/canvas)",
    "explorations": "exactly 2 x {title, change, observe, why}",
    "limitation": "one limitation / assumption / common misunderstanding",
    "grounding": "{from_paper: [statements supported by the excerpt], our_simplifications: [our own examples/simplifications]}",
    "tests": "list of {name, inputs, expect: {key: value}, tol} run against compute_js by the checker",
}

REQUIRED_KEYS = list(SPEC_KEYS)

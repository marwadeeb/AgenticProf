"""Get the paper text and trim it to the part relevant to `focus`. Owner: Member A.

During assessment network access is limited to OpenRouter, so prefer an excerpt
inside case.json; fetching source_url is a best-effort fallback.
"""


def get_excerpt(case: dict, trace) -> str:
    # TODO(A): confirm the 2 unlisted case.json fields with the instructor (likely the excerpt).
    for key in ("excerpt", "source_text", "text", "context"):
        if case.get(key):
            trace.log("source", "read_excerpt", "ok", field=key, chars=len(case[key]))
            return case[key]
    # TODO(A): best-effort fetch of source_url (html/pdf) + keyword trim around `focus`.
    trace.log("source", "read_excerpt", "missing", note="no excerpt field; relying on focus + model knowledge")
    return ""

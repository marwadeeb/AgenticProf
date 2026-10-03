"""Apply a repair that returns only the top-level JavaScript declarations it changes.

Repairs used to resend the whole CODE (~3k completion tokens) to change one function. Now the model
returns just the changed `function f(...) {...}` / `const X = ...;` declarations and we splice them in
by name. A reply that is a complete program (defines compute and view) replaces the code instead.
"""
from __future__ import annotations

import re

_DECL = re.compile(r"^\s*(?:async\s+)?(?:function\s*\*?\s*([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*))")
_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^") | {""}
_NEXT_DECL = re.compile(r"[ \t\r\n]*(?:async\s+function|function|const|let|var)\b")


def split_top_level(code: str) -> list:
    """Split JS source into top-level statements, respecting strings, template literals, comments, regexes."""
    out, start, i, n = [], 0, 0, len(code)
    depth, stack, prev = 0, [], ""
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if stack and stack[-1] == "`":
            if ch == "\\":
                i += 2
                continue
            if ch == "`":
                stack.pop()
            elif ch == "$" and nxt == "{":
                stack.append("${")
                depth += 1
                i += 2
                continue
            i += 1
            continue
        if ch in "\"'":
            j = i + 1
            while j < n and code[j] != ch:
                j += 2 if code[j] == "\\" else 1
            i, prev = j + 1, "a"
            continue
        if ch == "/" and nxt == "/":
            j = code.find("\n", i)
            i = n if j < 0 else j
            continue
        if ch == "/" and nxt == "*":
            j = code.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if ch == "/" and prev in _REGEX_PREV:
            j, cls = i + 1, False
            while j < n and (code[j] != "/" or cls) and code[j] != "\n":
                if code[j] == "\\":
                    j += 1
                elif code[j] == "[":
                    cls = True
                elif code[j] == "]":
                    cls = False
                j += 1
            i, prev = j + 1, "a"
            continue
        if ch == "`":
            stack.append("`")
        elif ch in "{([":
            depth += 1
        elif ch in "})]":
            depth -= 1
            if ch == "}" and stack and stack[-1] == "${" and depth >= 0:
                stack.pop()
                i += 1
                continue
            if depth == 0 and ch == "}":
                # a top-level block ends: a function declaration statement is complete here
                k = i + 1
                while k < n and code[k] in " \t\r":
                    k += 1
                rest = code[start:i + 1]
                if re.match(r"\s*(?:async\s+)?function\b", rest) and (k >= n or code[k] in "\n;"):
                    out.append(rest.strip())
                    start = i + 1
        elif ch == ";" and depth == 0:
            out.append(code[start:i + 1].strip())
            start = i + 1
        elif ch == "\n" and depth == 0 and code[start:i].strip() and _NEXT_DECL.match(code, i + 1):
            out.append(code[start:i].strip())  # statement ended by a newline (no semicolon)
            start = i + 1
        if not ch.isspace():
            prev = ch if not (ch.isalnum() or ch in "_$") else "a"
        i += 1
    tail = code[start:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s and s != ";"]


def decl_name(stmt: str):
    m = _DECL.match(stmt)
    return (m.group(1) or m.group(2)) if m else None


def is_full_program(code: str) -> bool:
    names = {decl_name(s) for s in split_top_level(code)}
    return {"compute", "view"} <= names


def apply_patch(old: str, patch: str) -> tuple:
    """Return (new_code, changed_names, mode). mode: 'full' | 'patch' | 'unchanged'."""
    patch = (patch or "").strip()
    if not patch or patch.upper() == "UNCHANGED":
        return old, [], "unchanged"
    if is_full_program(patch):
        return patch, ["<all>"], "full"
    new_stmts = split_top_level(patch)
    repl = {}
    for s in new_stmts:
        name = decl_name(s)
        if name is None:
            return old, [], "unparseable"  # loose statements: unsafe to splice
        repl[name] = s
    old_stmts = split_top_level(old)
    out, used = [], set()
    for s in old_stmts:
        name = decl_name(s)
        if name in repl:
            out.append(repl[name])
            used.add(name)
        else:
            out.append(s)
    out += [repl[k] for k in repl if k not in used]
    return "\n".join(out) + "\n", list(repl), "patch"

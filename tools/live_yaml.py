#!/usr/bin/env python3
"""Minimal YAML-subset reader for the live-runner manifests.

Stdlib only. The framework deliberately avoids a PyYAML dependency so
it runs identically on a developer checkout and on a GitHub Actions
runner. The supported subset is exactly what adapters/*.live.yaml
uses:

  - nested maps by 2-space indentation
  - lists of scalars ("- item")
  - scalars: plain strings, double/single-quoted strings, integers,
    booleans (true/false), null
  - full-line comments and trailing comments (" # ...") outside quotes
  - blank lines

Anything outside the subset raises ValueError with the offending line
number. Do NOT extend manifests past this subset without extending
this parser and tests/test_live_manifests.py together.
"""

import re

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def _strip_comment(line: str) -> str:
    """Remove a trailing ' # ...' comment outside quotes."""
    in_single = in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(line) and line[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            if in_double and i > 0 and line[i - 1] == "\\":
                pass
            else:
                in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1] in (" ", "\t"):
                return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _parse_scalar(text: str, lineno: int):
    text = text.strip()
    if text in ("", "~", "null", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            import json
            return json.loads(text)
        except Exception:
            raise ValueError(f"line {lineno}: bad double-quoted scalar")
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if _INT_RE.match(text):
        return int(text)
    if _FLOAT_RE.match(text):
        return float(text)
    return text


def parse_yaml(text: str) -> dict:
    """Parse the YAML subset into a plain dict. Raises ValueError."""
    lines = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if stripped.lstrip(" ") != stripped.lstrip():
            raise ValueError(f"line {lineno}: tabs are not indentation")
        lines.append((lineno, indent, stripped.strip()))

    root = {}
    # Stack of (indent, container). Root is at indent -2 so a top-level
    # key at indent 0 nests into it.
    stack = [(-2, root)]
    # Pending key awaiting a nested block: (indent, parent_dict, key)
    pending = None

    for lineno, indent, content in lines:
        if indent % 2 != 0:
            raise ValueError(
                f"line {lineno}: indentation must be a multiple of 2 "
                f"(got {indent})")
        # Pop containers strictly deeper than this line. A container
        # whose indent EQUALS this line's indent owns the line: a map
        # at indent N holds keys at indent N, and a list at indent N
        # holds items at indent N. (Popping on >= was a bug: it
        # ejected the list/map its own items/keys belonged to.)
        while stack and stack[-1][0] > indent:
            stack.pop()
        if not stack:
            raise ValueError(f"line {lineno}: indentation out of range")
        parent_indent, parent = stack[-1]

        if pending is not None:
            p_indent, p_parent, p_key = pending
            if indent == p_indent + 2:
                if content.startswith("- "):
                    child = []
                    p_parent[p_key] = child
                else:
                    child = {}
                    p_parent[p_key] = child
                stack.append((indent, child))
                parent_indent, parent = stack[-1]
                pending = None
            elif indent <= p_indent:
                p_parent[p_key] = None
                pending = None
            else:
                raise ValueError(
                    f"line {lineno}: child of '{p_key}' must be indented "
                    f"exactly 2 spaces (got {indent - p_indent})")

        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(
                    f"line {lineno}: list item outside a list")
            parent.append(_parse_scalar(content[2:], lineno))
            continue

        if content == "-":
            raise ValueError(
                f"line {lineno}: empty list items are not supported")
        if ":" not in content:
            raise ValueError(
                f"line {lineno}: expected 'key: value' or '- item'")
        key, _, rest = content.partition(":")
        key = key.strip()
        if not key or key.startswith(("-", " ")):
            raise ValueError(f"line {lineno}: bad key {key!r}")
        if isinstance(parent, list):
            raise ValueError(
                f"line {lineno}: mapping entry inside a list is not "
                "supported by this subset")
        rest = rest.strip()
        if rest == "":
            pending = (indent, parent, key)
        else:
            parent[key] = _parse_scalar(rest, lineno)

    if pending is not None:
        p_indent, p_parent, p_key = pending
        p_parent[p_key] = None

    return root

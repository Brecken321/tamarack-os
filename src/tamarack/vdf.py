"""Minimal parser for Valve's text KeyValues format (.vdf / .acf files).

Steam stores its library folders, installed-app manifests and per-game
compatibility-tool choices in this format. Only the text variant is
supported (not the binary appinfo/shortcuts format).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Union

VdfValue = Union[str, "VdfDict"]
VdfDict = dict[str, VdfValue]


class VdfError(ValueError):
    pass


def _tokens(text: str) -> Iterator[tuple[str, int]]:
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "/" and text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end + 1
        elif c in "{}":
            yield c, i
            i += 1
        elif c == '"':
            j = i + 1
            out = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    nxt = text[j + 1]
                    out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(nxt, "\\" + nxt))
                    j += 2
                else:
                    out.append(text[j])
                    j += 1
            if j >= n:
                raise VdfError(f"unterminated string at offset {i}")
            yield '"' + "".join(out), i
            i = j + 1
        else:
            # Unquoted token (Steam rarely writes these, but accept them).
            j = i
            while j < n and text[j] not in ' \t\r\n{}"':
                j += 1
            yield '"' + text[i:j], i
            i = j


def loads(text: str) -> VdfDict:
    """Parse KeyValues text. Keys are case-preserved; duplicates keep the last."""
    root: VdfDict = {}
    stack: list[VdfDict] = [root]
    pending_key: str | None = None
    for token, offset in _tokens(text):
        if token == "{":
            if pending_key is None:
                raise VdfError(f"unexpected '{{' at offset {offset}")
            child: VdfDict = {}
            stack[-1][pending_key] = child
            stack.append(child)
            pending_key = None
        elif token == "}":
            if pending_key is not None or len(stack) == 1:
                raise VdfError(f"unexpected '}}' at offset {offset}")
            stack.pop()
        else:
            value = token[1:]
            if pending_key is None:
                pending_key = value
            else:
                stack[-1][pending_key] = value
                pending_key = None
    if pending_key is not None or len(stack) != 1:
        raise VdfError("unexpected end of input")
    return root


def get_ci(mapping: VdfDict, key: str) -> VdfValue | None:
    """Case-insensitive lookup (Steam is inconsistent about key casing)."""
    if key in mapping:
        return mapping[key]
    lowered = key.lower()
    for k, v in mapping.items():
        if k.lower() == lowered:
            return v
    return None


def get_dict(mapping: VdfDict, *path: str) -> VdfDict:
    """Follow ``path`` case-insensitively; returns {} when anything is missing."""
    current: VdfValue | None = mapping
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = get_ci(current, key)
    return current if isinstance(current, dict) else {}

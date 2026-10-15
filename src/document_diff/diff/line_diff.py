"""Line-based unified diff for matched blocks (stdlib difflib; pygit2 not required)."""
from __future__ import annotations

import textwrap
from difflib import unified_diff
from typing import Iterable, List

from ..models import UNCHANGED, Change


def _lines(text: str, width: int = 100) -> List[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or [text]


def unified_patch(changes: Iterable[Change], old_name: str, new_name: str) -> str:
    """Render all non-unchanged rows as one unified-diff style patch (text content only)."""
    out: List[str] = ["--- a/%s" % old_name, "+++ b/%s" % new_name]
    for c in changes:
        if c.kind == UNCHANGED:
            continue
        out.append("@@ %s %s%s @@" % (c.id, c.kind, (" | " + c.section) if c.section else ""))
        body = list(unified_diff(_lines(c.old_text or ""), _lines(c.new_text or ""), lineterm="", n=0))
        out.extend(body[2:])  # drop per-block ---/+++ headers
    return "\n".join(out) + "\n"

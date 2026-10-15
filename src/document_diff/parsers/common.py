"""Shared parser helpers: section tracking and block construction."""
from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Tuple

from ..models import DocumentBlock
from ..normalize import nfc, normalize_text

_ART = re.compile(r"^(điều|article)\s+\d+[a-z]?\s*[.:\-–]", re.IGNORECASE)
_BIG = re.compile(r"^(chương|phần|chapter|part)\s+[0-9ivxlc]+\b", re.IGNORECASE)
_MID = re.compile(r"^(mục|section)\s+[0-9ivxlc]+\b", re.IGNORECASE)


def legal_heading_level(text: str) -> Optional[int]:
    """Detect legal-style headings (Chương/Mục/Điều) in plain paragraphs."""
    t = text.strip()
    if len(t) > 150:
        return None
    if _BIG.match(t):
        return 1
    if _MID.match(t):
        return 2
    if _ART.match(t):
        return 3
    return None


class SectionTracker:
    def __init__(self) -> None:
        self._stack: List[Tuple[int, str]] = []

    def enter(self, level: int, title: str) -> List[str]:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, title))
        return self.path()

    def path(self) -> List[str]:
        return [t for _, t in self._stack]


class BlockBuilder:
    """Creates ordered DocumentBlocks, tracking section path automatically."""

    def __init__(self, id_prefix: str = "b") -> None:
        self.prefix = id_prefix
        self.blocks: List[DocumentBlock] = []
        self.tracker = SectionTracker()

    def add(self, kind: str, text: str, *, level: Optional[int] = None, page: Optional[int] = None,
            pages: Optional[List[int]] = None, bbox=None, source_ref: Optional[str] = None,
            table_cells: Optional[List[List[str]]] = None) -> Optional[DocumentBlock]:
        text = nfc(text)
        if not text:
            return None
        if kind in ("paragraph", "list"):
            lvl = legal_heading_level(text)
            if lvl is not None:
                kind, level = "heading", lvl
        if kind == "heading":
            path = self.tracker.enter(level or 1, text[:120])
        else:
            path = self.tracker.path()
        order = len(self.blocks)
        normalized = normalize_text(text)
        block = DocumentBlock(
            id="%s-%05d" % (self.prefix, order), kind=kind, text=text,
            normalized_text=normalized, section_path=list(path), order=order,
            page=page, bbox=bbox, source_ref=source_ref, level=level if kind == "heading" else None,
            content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            pages=list(pages) if pages else ([page] if page else []), table_cells=table_cells,
        )
        self.blocks.append(block)
        return block

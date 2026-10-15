"""Canonical data model shared by parsers, matchers, diff engine and reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Change kinds
ADDED = "ADDED"
DELETED = "DELETED"
MODIFIED = "MODIFIED"
MOVED = "MOVED"
UNRESOLVED = "UNRESOLVED"
FORMATTING_ONLY = "FORMATTING_ONLY"
UNCHANGED = "UNCHANGED"

CHANGE_KINDS = (ADDED, DELETED, MODIFIED, MOVED, UNRESOLVED, FORMATTING_ONLY)


class ParseError(Exception):
    """Raised when a document cannot be parsed or yields no usable text."""


@dataclass
class DocumentBlock:
    id: str
    kind: str  # heading | paragraph | list | table
    text: str  # original text (Unicode NFC)
    normalized_text: str
    section_path: List[str]
    order: int
    page: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    source_ref: Optional[str] = None
    level: Optional[int] = None  # heading level
    content_hash: str = ""  # SHA-256 of normalized_text
    pages: List[int] = field(default_factory=list)  # all pages (stitched paragraphs span several)
    table_cells: Optional[List[List[str]]] = None  # 2-D data when kind == "table"


@dataclass
class ParseResult:
    blocks: List[DocumentBlock]
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Change:
    id: str
    kind: str
    old_block_ids: List[str]
    new_block_ids: List[str]
    old_text: Optional[str]
    new_text: Optional[str]
    diff_spans: List[Dict[str, Any]]
    similarity: Optional[float]
    review_required: bool
    section: str = ""
    old_location: Optional[Dict[str, Any]] = None
    new_location: Optional[Dict[str, Any]] = None
    method: str = ""
    moved: bool = False
    note: str = ""
    review_reason: Optional[str] = None
    table_diffs: Optional[List[Dict[str, Any]]] = None  # row/cell level diff for tables


@dataclass
class CompareOptions:
    ignore_formatting: bool = True  # whitespace/quote/dash-only differences -> UNCHANGED
    fuzzy_threshold: int = 75  # >= : MODIFIED pair
    unresolved_threshold: int = 55  # [this, fuzzy) : UNRESOLVED pair
    move_threshold: int = 85  # fuzzy match across distant positions
    min_move_length: int = 15  # shorter blocks are never matched as exact moves
    merge_min_score: int = 70  # min similarity of a 1-N / N-1 merged candidate
    merge_gain: int = 15  # merged score must beat best single score by this much
    max_upload_mb: int = 50


@dataclass
class ComparisonResult:
    comparison_id: str
    old_file: str
    new_file: str
    old_sha256: str
    new_sha256: str
    old_blocks: List[DocumentBlock]
    new_blocks: List[DocumentBlock]
    changes: List[Change]  # all aligned rows in document order (incl. UNCHANGED)
    warnings: List[str]
    stats: Dict[str, Any]

    @property
    def summary(self) -> Dict[str, int]:
        keys = ["added", "deleted", "modified", "moved", "unresolved", "formatting_only"]
        out = {k: 0 for k in keys}
        out["unchanged"] = 0
        for c in self.changes:
            out[c.kind.lower()] += 1
        return out

    @property
    def real_changes(self) -> List[Change]:
        return [c for c in self.changes if c.kind != UNCHANGED]

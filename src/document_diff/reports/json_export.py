"""JSON export following the v2.0 output contract."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from ..models import UNCHANGED, Change, ComparisonResult

SCHEMA_VERSION = "2.0"

_ALIGNMENT = {
    "exact": "exact_hash", "moved_exact": "exact_hash", "heading_fuzzy": "heading_anchor",
    "merged_fuzzy": "merged_fuzzy", "fuzzy": "fuzzy", "low": "fuzzy", "moved_fuzzy": "fuzzy",
    "unmatched": "unmatched",
}


def _prov(ids: List[str], blocks_by_id) -> List[Dict[str, Any]]:
    out = []
    for bid in ids:
        b = blocks_by_id[bid]
        out.append({"block_id": b.id, "page": b.page, "pages": b.pages, "section_path": b.section_path,
                    "source_ref": b.source_ref, "bbox": list(b.bbox) if b.bbox else None})
    return out


def _file_meta(name: str, sha: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": name, "sha256": sha, "pages": meta.get("pages"),
            "format": os.path.splitext(name)[1].lstrip(".").lower()}


def _change_dict(c: Change, blocks_by_id, include_spans: bool) -> Dict[str, Any]:
    item = {
        "id": c.id,
        "change_type": c.kind,
        "alignment_method": _ALIGNMENT.get(c.method, c.method),
        "section_context": c.section.replace(" › ", " > "),
        "old_provenance": _prov(c.old_block_ids, blocks_by_id),
        "new_provenance": _prov(c.new_block_ids, blocks_by_id),
        "old_text": c.old_text,
        "new_text": c.new_text,
        "similarity": c.similarity,
        "review_required": c.review_required,
        "review_reason": c.review_reason,
        "moved": c.moved,
        "note": c.note,
    }
    if include_spans:
        item["diff_spans"] = [{"op": s["op"], "text": s["text"], "old_start": s.get("old_start"),
                               "old_end": s.get("old_end"), "new_start": s.get("new_start"),
                               "new_end": s.get("new_end")} for s in c.diff_spans]
        if c.table_diffs is not None:
            item["table_diffs"] = c.table_diffs
    return item


def to_dict(result: ComparisonResult, include_unchanged: bool = False, include_spans: bool = True) -> Dict[str, Any]:
    blocks_by_id = {b.id: b for b in result.old_blocks + result.new_blocks}
    summary = dict(result.summary)
    summary["review_required_count"] = sum(1 for c in result.changes if c.review_required)
    return {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": result.comparison_id,
        "metadata": {
            "created_at": result.stats.get("created_at"),
            "processing_time_ms": int(result.stats.get("total_seconds", 0) * 1000),
            "old_file": _file_meta(result.old_file, result.old_sha256, result.stats.get("old_metadata", {})),
            "new_file": _file_meta(result.new_file, result.new_sha256, result.stats.get("new_metadata", {})),
        },
        "summary": summary,
        "warnings": result.warnings,
        "stats": result.stats,
        "changes": [_change_dict(c, blocks_by_id, include_spans) for c in result.changes
                    if include_unchanged or c.kind != UNCHANGED],
    }


def to_json(result: ComparisonResult, **kwargs) -> str:
    return json.dumps(to_dict(result, **kwargs), ensure_ascii=False, indent=2)

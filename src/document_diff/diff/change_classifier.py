"""Turns aligned block groups into classified Change rows with inline/table diffs."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..matching.common import Pair
from ..models import (ADDED, DELETED, FORMATTING_ONLY, MODIFIED, MOVED, UNCHANGED, UNRESOLVED,
                      Change, CompareOptions, DocumentBlock)
from ..normalize import match_text
from .inline_diff import inline_diff
from .table_diff import table_diff


def _loc(b: DocumentBlock) -> Dict:
    return {"page": b.page, "pages": b.pages, "source_ref": b.source_ref, "block_order": b.order,
            "bbox": list(b.bbox) if b.bbox else None}


def _section(*blocks: Optional[DocumentBlock]) -> str:
    for b in blocks:
        if b is not None and b.section_path:
            return " › ".join(b.section_path)
    return ""


def classify(old: Sequence[DocumentBlock], new: Sequence[DocumentBlock], pairs: Sequence[Pair],
             opts: CompareOptions) -> List[Change]:
    rows = []  # (sort_key, Change)
    by_old: Dict[int, Pair] = {}
    mapped_new = set()
    for p in pairs:
        for i in [p.old] + p.old_more:
            by_old[i] = p
        mapped_new.update([p.new] + p.new_more)

    for p in pairs:
        ob = [old[i] for i in [p.old] + p.old_more]
        nb = [new[j] for j in [p.new] + p.new_more]
        merged = len(ob) > 1 or len(nb) > 1
        otext = " ".join(b.text for b in ob)
        ntext = " ".join(b.text for b in nb)
        onorm = " ".join(b.normalized_text for b in ob)
        nnorm = " ".join(b.normalized_text for b in nb)
        spans: List[Dict] = []
        tdiff = None
        note = ""
        reason = None
        review = False
        if onorm == nnorm:
            if p.moved:
                kind = MOVED
            elif otext == ntext:
                kind = UNCHANGED
            else:
                kind = UNCHANGED if opts.ignore_formatting else FORMATTING_ONLY
            if kind == FORMATTING_ONLY:
                spans = inline_diff(otext, ntext)
            sim = 1.0
        else:
            sim = p.score
            if p.method == "low":
                kind, review = UNRESOLVED, True
                reason = "Độ tương đồng thấp (%d%%): ghép không chắc chắn, cần người dùng kiểm tra" % round(sim * 100)
            else:
                kind = MODIFIED
                if p.moved:
                    review, reason = True, "Đoạn bị di chuyển và có chỉnh sửa"
                elif sim * 100 < max(opts.fuzzy_threshold + 5, 80):
                    review, reason = True, "Độ tương đồng thấp (%d%%): nghi ngờ sửa đổi lớn" % round(sim * 100)
                elif merged and sim < 0.9:
                    review, reason = True, "Ghép nhiều khối (tách/gộp đoạn) với độ tương đồng %d%%" % round(sim * 100)
                if match_text(onorm) == match_text(nnorm):
                    note = "renumbered"
            if (not merged and ob[0].table_cells and nb[0].table_cells):
                tdiff = table_diff(ob[0].table_cells, nb[0].table_cells)
            else:
                spans = inline_diff(otext, ntext)
        rows.append(((p.new, 0.0, p.old), Change(
            id="", kind=kind, old_block_ids=[b.id for b in ob], new_block_ids=[b.id for b in nb],
            old_text=otext, new_text=ntext, diff_spans=spans, similarity=round(sim, 4),
            review_required=review, section=_section(nb[0], ob[0]), old_location=_loc(ob[0]),
            new_location=_loc(nb[0]), method=p.method, moved=p.moved, note=note,
            review_reason=reason, table_diffs=tdiff)))

    for j, n in enumerate(new):
        if j in mapped_new:
            continue
        rows.append(((j, 0.0, -1), Change(
            id="", kind=ADDED, old_block_ids=[], new_block_ids=[n.id], old_text=None, new_text=n.text,
            diff_spans=[{"op": "insert", "text": n.text, "old_start": 0, "old_end": 0,
                         "new_start": 0, "new_end": len(n.text)}],
            similarity=None, review_required=False, section=_section(n), new_location=_loc(n),
            method="unmatched")))

    for i, o in enumerate(old):
        if i in by_old:
            continue
        prev = i - 1
        while prev >= 0 and prev not in by_old:
            prev -= 1
        anchor = by_old[prev].new + len(by_old[prev].new_more) if prev >= 0 else -1
        rows.append(((anchor, 0.5, i), Change(
            id="", kind=DELETED, old_block_ids=[o.id], new_block_ids=[], old_text=o.text, new_text=None,
            diff_spans=[{"op": "delete", "text": o.text, "old_start": 0, "old_end": len(o.text),
                         "new_start": 0, "new_end": 0}],
            similarity=None, review_required=False, section=_section(o), old_location=_loc(o),
            method="unmatched")))

    rows.sort(key=lambda r: r[0])
    out = []
    for idx, (_, c) in enumerate(rows, start=1):
        c.id = "chg-%05d" % idx
        out.append(c)
    return out

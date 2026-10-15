"""Self-contained side-by-side HTML report / viewer fragment."""
from __future__ import annotations

from html import escape
from typing import Iterable, List, Optional

from ..models import UNCHANGED, Change, ComparisonResult

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#1f2328;background:#fff}
.hdr{padding:10px 16px;background:#f6f8fa;border-bottom:1px solid #d0d7de;font-size:13px}
.warn{background:#fff8c5;border:1px solid #d4a72c;padding:6px 12px;margin:8px 16px;border-radius:6px;font-size:13px}
table{border-collapse:collapse;width:100%;table-layout:fixed}
th{position:sticky;top:0;background:#f6f8fa;border-bottom:1px solid #d0d7de;padding:6px;font-size:13px}
td{vertical-align:top;padding:6px 10px;border-bottom:1px solid #eaeef2;font-size:14px;line-height:1.5;
   white-space:pre-wrap;word-wrap:break-word;width:50%}
.meta{font-size:11px;color:#656d76;margin-bottom:2px}
tr.ADDED td.r{background:#e6ffec} tr.ADDED td.l{background:#f6f8fa}
tr.DELETED td.l{background:#ffebe9} tr.DELETED td.r{background:#f6f8fa}
tr.MODIFIED td,tr.MOVED td,tr.FORMATTING_ONLY td{background:#fff8e1}
tr.UNRESOLVED td{background:#ffe8d6}
tr.UNCHANGED td{color:#656d76}
tr.focus{outline:3px solid #0969da;outline-offset:-3px}
ins{background:#aceebb;text-decoration:none;border-radius:2px}
del{background:#ffc1ba;border-radius:2px}
.tag{font-size:10px;font-weight:600;padding:1px 6px;border-radius:8px;background:#d0d7de;margin-right:4px}
.gap td{text-align:center;color:#8c959f;font-size:12px;background:#fafbfc}
table.inner{width:auto;table-layout:auto;margin-top:4px}
table.inner td{width:auto;border:1px solid #d0d7de;padding:3px 8px;white-space:normal;background:transparent}
table.inner tr.rowadded td{background:#e6ffec} table.inner tr.rowdeleted td{background:#ffebe9}
table.inner td.cellmod{background:#fff3b0}
"""


def _render_spans(spans, side: str) -> str:
    out = []
    for s in spans:
        t = escape(s["text"])
        if s["op"] == "equal":
            out.append(t)
        elif s["op"] == "delete" and side == "l":
            out.append("<del>%s</del>" % t)
        elif s["op"] == "insert" and side == "r":
            out.append("<ins>%s</ins>" % t)
    return "".join(out)


def _table_html(c: Change, side: str) -> str:
    rows = []
    for r in c.table_diffs or []:
        op = r["op"]
        if (side == "l" and op == "added") or (side == "r" and op == "deleted"):
            continue
        cells = "".join(
            '<td class="%s">%s</td>' % ("cellmod" if cell["op"] == "modified" else "", _render_spans(cell["spans"], side))
            for cell in r["cells"])
        rows.append('<tr class="row%s">%s</tr>' % (op, cells))
    return '<table class="inner">%s</table>' % "".join(rows)


def _spans_html(c: Change, side: str) -> str:
    text = c.old_text if side == "l" else c.new_text
    if text is None:
        return ""
    if c.table_diffs is not None:
        return _table_html(c, side)
    if not c.diff_spans:
        return escape(text)
    return _render_spans(c.diff_spans, side)


def _meta(c: Change, loc: Optional[dict], with_tag: bool) -> str:
    bits = []
    if with_tag:
        bits.append('<span class="tag">%s</span>' % c.kind)
        if c.review_required:
            bits.append('<span class="tag" style="background:#ffd8a8" title="%s">review</span>'
                        % escape(c.review_reason or ""))
    if loc:
        pages = loc.get("pages") or ([loc["page"]] if loc.get("page") else [])
        if pages:
            bits.append("p.%s" % (pages[0] if len(pages) == 1 else "%s–%s" % (pages[0], pages[-1])))
        elif loc.get("source_ref"):
            bits.append(escape(str(loc["source_ref"])))
    if c.section:
        bits.append(escape(c.section[:80]))
    if with_tag is False and c.review_reason:
        bits.append("⚠ " + escape(c.review_reason))
    return '<div class="meta">%s</div>' % " · ".join(bits) if bits else ""


def top_section(c: Change) -> str:
    return c.section.split(" › ")[0] if c.section else "(Không có mục)"


def section_groups(result: ComparisonResult) -> List[str]:
    """Ordered unique top-level sections (Chương/Mục) used for paginated viewing."""
    seen: List[str] = []
    for c in result.changes:
        s = top_section(c)
        if s not in seen:
            seen.append(s)
    return seen


def render_html(result: ComparisonResult, kinds: Optional[Iterable[str]] = None, focus_id: Optional[str] = None,
                show_unchanged: bool = True, context: int = 1, full_page: bool = True,
                section: Optional[str] = None, review_only: bool = False) -> str:
    kinds = set(kinds) if kinds is not None else None
    rows: List[Change] = result.changes
    visible = [True] * len(rows)
    for i, c in enumerate(rows):
        if c.kind == UNCHANGED:
            visible[i] = show_unchanged
        elif kinds is not None and c.kind not in kinds:
            visible[i] = False
        elif review_only and not c.review_required:
            visible[i] = False
    if not show_unchanged:  # keep a little context around changes
        for i, c in enumerate(rows):
            if c.kind != UNCHANGED and visible[i]:
                for k in range(max(0, i - context), min(len(rows), i + context + 1)):
                    if rows[k].kind == UNCHANGED:
                        visible[k] = True
    if section is not None:  # pagination by top-level section
        visible = [v and top_section(c) == section for c, v in zip(rows, visible)]

    parts = []
    hidden = 0
    for c, vis in zip(rows, visible):
        if not vis:
            hidden += 1
            continue
        if hidden:
            parts.append('<tr class="gap"><td colspan="2">… %d block(s) hidden …</td></tr>' % hidden)
            hidden = 0
        cls = c.kind + (" focus" if c.id == focus_id else "")
        show_tag = c.kind != UNCHANGED
        parts.append(
            '<tr id="%s" class="%s"><td class="l">%s%s</td><td class="r">%s%s</td></tr>' % (
                c.id, cls, _meta(c, c.old_location, show_tag), _spans_html(c, "l"),
                _meta(c, c.new_location, False), _spans_html(c, "r")))
    if hidden:
        parts.append('<tr class="gap"><td colspan="2">… %d block(s) hidden …</td></tr>' % hidden)

    s = result.summary
    header = "<b>%s</b> → <b>%s</b> &nbsp;|&nbsp; added %d · deleted %d · modified %d · moved %d · unresolved %d" % (
        escape(result.old_file), escape(result.new_file), s["added"], s["deleted"], s["modified"],
        s["moved"], s["unresolved"])
    if s["formatting_only"]:
        header += " · formatting-only %d" % s["formatting_only"]
    warns = "".join('<div class="warn">⚠ %s</div>' % escape(w) for w in result.warnings)
    script = ("<script>var e=document.querySelector('tr.focus');if(e){e.scrollIntoView({block:'center'});}</script>"
              if focus_id else "")
    table = ('<table><thead><tr><th>%s (before)</th><th>%s (after)</th></tr></thead><tbody>%s</tbody></table>'
             % (escape(result.old_file), escape(result.new_file), "".join(parts)))
    body = '<div class="hdr">%s</div>%s%s%s' % (header, warns, table, script)
    if not full_page:
        return "<style>%s</style>%s" % (CSS, body)
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Document diff</title><style>%s</style>'
            "</head><body>%s</body></html>" % (CSS, body))

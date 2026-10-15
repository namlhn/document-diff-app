"""Document Diff - Streamlit viewer. Run: streamlit run app.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

from document_diff.diff import unified_patch  # noqa: E402
from document_diff.models import CHANGE_KINDS, CompareOptions, ParseError  # noqa: E402
from document_diff.pipeline import compare_documents  # noqa: E402
from document_diff.reports import render_html, section_groups, to_json, top_section  # noqa: E402

MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
TYPES = ["pdf", "docx", "md"]

st.set_page_config(page_title="Document Diff", layout="wide")
st.title("📄 Document Diff")
st.caption("So sánh hai tài liệu (PDF, DOCX, Markdown) như công cụ compare source code.")

c1, c2 = st.columns(2)
old_file = c1.file_uploader("Bản cũ (before)", type=TYPES, key="old")
new_file = c2.file_uploader("Bản mới (after)", type=TYPES, key="new")

with st.sidebar:
    st.header("Tùy chọn")
    ignore_fmt = st.checkbox("Bỏ qua khác biệt whitespace/format", value=True)
    fuzzy = st.slider("Ngưỡng ghép 'sửa' (%)", 60, 95, 75)

if st.button("So sánh", type="primary", disabled=not (old_file and new_file)):
    opts = CompareOptions(ignore_formatting=ignore_fmt, fuzzy_threshold=fuzzy, max_upload_mb=MAX_MB)
    try:
        with st.spinner("Đang phân tích..."):
            st.session_state["result"] = compare_documents(
                old_file.getvalue(), old_file.name, new_file.getvalue(), new_file.name, opts)
    except ParseError as exc:
        st.session_state.pop("result", None)
        st.error("Không thể so sánh: %s" % exc)

result = st.session_state.get("result")
if result is not None:
    s = result.summary
    cols = st.columns(6)
    for col, key in zip(cols, ["added", "deleted", "modified", "moved", "unresolved", "formatting_only"]):
        col.metric(key.replace("_", " ").title(), s[key])
    for w in result.warnings:
        st.warning(w)
    if s["unresolved"]:
        st.info("Có %d mục UNRESOLVED cần người dùng kiểm tra." % s["unresolved"])
    st.caption("Xử lý trong %.2fs · %d / %d khối" % (
        result.stats["total_seconds"], result.stats["old_blocks"], result.stats["new_blocks"]))

    kinds = st.multiselect("Lọc theo loại", list(CHANGE_KINDS), default=list(CHANGE_KINDS))
    review_only = st.checkbox("Chỉ hiện mục cần kiểm tra (REVIEW_REQUIRED)", value=False)
    items = [c for c in result.real_changes if c.kind in kinds and (c.review_required or not review_only)]
    focus = None
    if items:
        labels = {c.id: "%s · %s · %s" % (c.id, c.kind, (c.section or (c.new_text or c.old_text or ""))[:60])
                  for c in items}
        focus = st.selectbox("Đi tới thay đổi", [None] + [c.id for c in items],
                             format_func=lambda x: "—" if x is None else labels[x])
        if focus:
            c = next(x for x in items if x.id == focus)
            loc = c.new_location or c.old_location or {}
            st.caption("Nguồn: %s · trang: %s · mục: %s" % (
                loc.get("source_ref") or "-", loc.get("page") or "-", c.section or "-"))
            if c.review_reason:
                st.warning(c.review_reason)
    else:
        st.success("Không có thay đổi phù hợp bộ lọc.")

    mode = st.radio("Chế độ xem", ["Chỉ hiện thay đổi (kèm ngữ cảnh)", "Hiện toàn bộ (phân trang theo Chương/Mục)"],
                    horizontal=True)
    section = None
    show_unchanged = mode.startswith("Hiện toàn bộ")
    if show_unchanged:
        groups = section_groups(result)
        default = 0
        if focus:
            default = groups.index(top_section(next(x for x in items if x.id == focus)))
        section = st.selectbox("Chương/Mục", groups, index=default, key="sec-%s" % focus)

    components.html(render_html(result, kinds=kinds, focus_id=focus, show_unchanged=show_unchanged,
                                full_page=False, section=section, review_only=review_only),
                    height=700, scrolling=True)

    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ JSON", to_json(result), "diff-report.json", "application/json")
    d2.download_button("⬇ HTML", render_html(result, show_unchanged=False), "diff-report.html", "text/html")
    d3.download_button("⬇ Unified diff", unified_patch(result.changes, result.old_file, result.new_file),
                       "diff.patch", "text/plain")

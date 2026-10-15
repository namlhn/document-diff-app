import time

import pytest

from document_diff.models import CompareOptions, ParseError
from document_diff.pipeline import compare_documents
from document_diff.reports import render_html, to_json
from helpers import long_doc_items, make_docx, make_md, make_pdf, paginate

NEW_TEXT = "Khoan 2 cua Dieu 15 quy dinh ve nghia vu thuc hien so 152 voi noi dung da duoc sua doi."


def real(res):
    return [c for c in res.changes if c.kind != "UNCHANGED"]


def test_long_pdf_single_sentence_change():
    old = make_pdf(paginate(long_doc_items(40)))
    new = make_pdf(paginate(long_doc_items(40, 15, NEW_TEXT)))
    t = time.perf_counter()
    res = compare_documents(old, "v1.pdf", new, "v2.pdf")
    elapsed = time.perf_counter() - t
    ch = real(res)
    assert len(ch) == 1, [(c.kind, c.old_text) for c in ch]
    c = ch[0]
    assert c.kind == "MODIFIED"
    assert "Dieu 15" in c.section
    assert c.new_location["page"] is not None
    assert any(s["op"] == "insert" for s in c.diff_spans)
    assert elapsed < 30


def test_insert_at_start_cross_format_pdf_docx_md():
    base = [("h2", "Dieu 1. Pham vi"), ("p", "Noi dung dieu mot rat quan trong voi moi nguoi."),
            ("p", "Noi dung thu hai cua van ban nay khong thay doi.")]
    added = [("p", "Doan moi duoc them vao dau tai lieu de kiem tra.")] + base
    old_md, new_md = make_md(base), make_md(added)
    res = compare_documents(old_md, "a.md", new_md, "b.md")
    assert [c.kind for c in real(res)] == ["ADDED"]
    res = compare_documents(make_docx(base), "a.docx", make_docx(added), "b.docx")
    assert [c.kind for c in real(res)] == ["ADDED"]
    res = compare_documents(make_md(base), "a.md", make_docx(added), "b.docx")
    assert [c.kind for c in real(res)] == ["ADDED"]
    assert any("Cross-format" in w for w in res.warnings)


def test_formatting_option():
    old = make_md([("p", "Cau van   co   nhieu khoang trang   thua trong do.")])
    new = make_md([("p", "Cau van co nhieu khoang trang thua trong do.")])
    assert real(compare_documents(old, "a.md", new, "b.md")) == []
    res = compare_documents(old, "a.md", new, "b.md", CompareOptions(ignore_formatting=False))
    assert [c.kind for c in real(res)] == ["FORMATTING_ONLY"]


def test_identical_and_errors_not_silent():
    md = make_md([("p", "Mot doan van ban bat ky de so sanh.")])
    res = compare_documents(md, "a.md", md, "b.md")
    assert real(res) == [] and any("identical" in w for w in res.warnings)
    with pytest.raises(ParseError):
        compare_documents(b"", "a.md", md, "b.md")


def test_upload_limit():
    md = make_md([("p", "x" * 3000)])
    with pytest.raises(ParseError, match="limit"):
        compare_documents(md, "a.md", md, "b.md", CompareOptions(max_upload_mb=0))


def test_exports_render():
    old = make_md([("p", "Thoi han la 3 nam theo quy dinh.")])
    new = make_md([("p", "Thoi han la 5 nam theo quy dinh.")])
    res = compare_documents(old, "a.md", new, "b.md")
    html = render_html(res, focus_id=res.changes[0].id)
    assert "<ins>5</ins>" in html and "<del>3</del>" in html
    assert '"schema_version"' in to_json(res)


def test_benchmark_100_pages():
    items = long_doc_items(120)
    old = make_pdf(paginate(items))
    items2 = long_doc_items(120, 60, NEW_TEXT.replace("15", "60"))
    new = make_pdf(paginate(items2))
    res = compare_documents(old, "a.pdf", new, "b.pdf")
    assert len(real(res)) == 1
    print("100-page benchmark:", res.stats)

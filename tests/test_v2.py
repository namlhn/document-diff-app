"""Tests for v2 features: stitching, header/footer, split/merge, tables, review flags, JSON contract."""
import fitz
from hypothesis import given, settings, strategies as st

from document_diff.diff import inline_diff, table_diff
from document_diff.models import CompareOptions
from document_diff.parsers import parse_document
from document_diff.pipeline import compare_documents
from document_diff.reports import render_html, section_groups, to_dict
from helpers import make_docx, make_md

LONG = ("Ben nhan co nghia vu bao quan toan bo tai lieu duoc giao trong suot thoi han hop dong va phai "
        "hoan tra day du cho ben giao khi ket thuc hop dong theo dung quy dinh da thoa thuan truoc do.")
HEAD = "CONG TY ABC - BAO CAO NOI BO"


def pdf_with_split_paragraph(split_at=70, pages=3):
    """Each page: header, body paragraph, footer. Page 1 bottom paragraph continues on page 2."""
    doc = fitz.open()
    cut = LONG.rfind(" ", 0, split_at)
    first, second = LONG[:cut], LONG[cut + 1:]
    for p in range(pages):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 15, 545, 40), HEAD, fontsize=9)
        page.insert_textbox(fitz.Rect(250, 810, 350, 835), "Trang %d" % (p + 1), fontsize=9)
        if p == 0:
            page.insert_textbox(fitz.Rect(50, 100, 545, 160), "Doan mo dau cua tai lieu so mot.", fontsize=11)
            page.insert_textbox(fitz.Rect(50, 700, 545, 760), first, fontsize=11)
        elif p == 1:
            page.insert_textbox(fitz.Rect(50, 100, 545, 160), second, fontsize=11)
            page.insert_textbox(fitz.Rect(50, 200, 545, 260), "Doan ket thuc cua trang hai.", fontsize=11)
        else:
            page.insert_textbox(fitz.Rect(50, 100, 545, 160), "Noi dung trang ba hoan toan khac.", fontsize=11)
    return doc.tobytes()


def test_header_footer_removed_and_paragraph_stitched():
    r = parse_document(pdf_with_split_paragraph(), "a.pdf")
    texts = [b.text for b in r.blocks]
    assert not any(HEAD in t or t.startswith("Trang") for t in texts)
    stitched = [b for b in r.blocks if b.text.replace("  ", " ").startswith("Ben nhan")]
    assert len(stitched) == 1 and stitched[0].pages == [1, 2]
    assert r.metadata["stitched_paragraphs"] == 1


def test_pdf_vs_docx_split_paragraph_no_false_changes():
    items = [("p", "Doan mo dau cua tai lieu so mot."), ("p", LONG), ("p", "Doan ket thuc cua trang hai."),
             ("p", "Noi dung trang ba hoan toan khac.")]
    res = compare_documents(pdf_with_split_paragraph(), "a.pdf", make_docx(items), "b.docx")
    real = [c for c in res.changes if c.kind != "UNCHANGED"]
    assert real == [], [(c.kind, c.old_text, c.new_text) for c in real]


def test_merge_resolver_split_across_blocks():
    old = make_md([("p", LONG), ("p", "Doan khac biet hoan toan o giua hai vi tri.")])
    half = len(LONG) // 2
    cut = LONG.rfind(" ", 0, half)
    new = make_md([("p", LONG[:cut]), ("p", LONG[cut + 1:]), ("p", "Doan khac biet hoan toan o giua hai vi tri.")])
    res = compare_documents(old, "a.md", new, "b.md")
    merged = [c for c in res.changes if c.method == "merged_fuzzy"]
    assert len(merged) == 1 and len(merged[0].new_block_ids) == 2
    assert merged[0].kind == "UNCHANGED"
    assert not [c for c in res.changes if c.kind in ("ADDED", "DELETED")]


def test_merge_with_edit_is_modified_and_reviewable():
    old = make_md([("p", LONG)])
    edited = LONG.replace("toan bo", "mot phan")
    cut = edited.rfind(" ", 0, len(edited) // 2)
    new = make_md([("p", edited[:cut]), ("p", edited[cut + 1:])])
    res = compare_documents(old, "a.md", new, "b.md")
    c = [x for x in res.changes if x.kind != "UNCHANGED"]
    assert len(c) == 1 and c[0].kind == "MODIFIED" and c[0].method == "merged_fuzzy"


def test_table_cell_level_diff():
    old = [["Ten", "Gia tri"], ["Thoi han", "3 nam"], ["Phi", "100"]]
    new = [["Ten", "Gia tri"], ["Thoi han", "5 nam"], ["Phi", "100"], ["Moi", "1"]]
    rows = table_diff(old, new)
    assert [r["op"] for r in rows] == ["equal", "modified", "equal", "added"]
    mod = rows[1]["cells"]
    assert [c["op"] for c in mod] == ["equal", "modified"]  # only one cell highlighted


def test_table_change_in_pipeline_and_html():
    base = [("p", "Bang phi dich vu ap dung cho khach hang."), ("table", "Ten|Gia;Phi A|100;Phi B|200")]
    chg = [("p", "Bang phi dich vu ap dung cho khach hang."), ("table", "Ten|Gia;Phi A|100;Phi B|250")]
    res = compare_documents(make_docx(base), "a.docx", make_docx(chg), "b.docx")
    real = [c for c in res.changes if c.kind != "UNCHANGED"]
    assert len(real) == 1 and real[0].kind == "MODIFIED" and real[0].table_diffs
    html = render_html(res)
    assert html.count('class="cellmod"') == 2  # one cell on each side
    assert "<del>200</del>" in html and "<ins>250</ins>" in html


def test_review_reason_for_low_similarity_and_unresolved():
    a = "Hop dong nay co hieu luc ke tu ngay ky va keo dai trong vong hai muoi bon thang lien tuc."
    b = "Hop dong nay co hieu luc ke tu ngay ky ket va tiep tuc cho toi khi mot ben thong bao cham dut."
    res = compare_documents(make_md([("p", a)]), "a.md", make_md([("p", b)]), "b.md",
                            CompareOptions(fuzzy_threshold=90, unresolved_threshold=50))
    c = [x for x in res.changes if x.kind != "UNCHANGED"]
    assert c and all(x.review_required and x.review_reason for x in c if x.kind in ("MODIFIED", "UNRESOLVED"))


def test_json_contract_v2():
    old = make_md([("h1", "Dieu 15. Thoi han"), ("p", "Thoi han bao hanh san pham la 12 thang ke tu ngay nghiem thu.")])
    new = make_md([("h1", "Dieu 15. Thoi han"), ("p", "Thoi han bao hanh san pham la 24 thang ke tu ngay ban giao.")])
    d = to_dict(compare_documents(old, "a.md", new, "b.md"))
    assert d["schema_version"] == "2.0"
    assert d["metadata"]["old_file"]["format"] == "md" and d["metadata"]["old_file"]["sha256"]
    assert "review_required_count" in d["summary"] and d["metadata"]["processing_time_ms"] >= 0
    ch = d["changes"][0]
    assert ch["change_type"] == "MODIFIED" and ch["alignment_method"] in ("fuzzy", "merged_fuzzy")
    assert ch["old_provenance"][0]["block_id"].startswith("old-")
    assert "Dieu 15" in ch["section_context"]


def test_section_pagination():
    items = [("h1", "Chuong I"), ("p", "Noi dung chuong mot rat quan trong."),
             ("h1", "Chuong II"), ("p", "Noi dung chuong hai cung quan trong.")]
    new_items = items[:3] + [("p", "Noi dung chuong hai cung quan trong, da duoc sua doi.")]
    res = compare_documents(make_md(items), "a.md", make_md(new_items), "b.md")
    groups = section_groups(res)
    assert groups == ["Chuong I", "Chuong II"]
    html = render_html(res, show_unchanged=True, section="Chuong II")
    assert "Chuong II" in html and "chuong mot" not in html


@settings(max_examples=60, deadline=None)
@given(st.text(alphabet="abc dEf,.ăâđêôơưáàảãạ", max_size=60), st.text(alphabet="abc dEf,.ăâđêôơưáàảãạ", max_size=60))
def test_inline_diff_roundtrip_property(a, b):
    spans = inline_diff(a, b)
    assert "".join(s["text"] for s in spans if s["op"] != "insert") == a
    assert "".join(s["text"] for s in spans if s["op"] != "delete") == b

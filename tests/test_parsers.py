import pytest

from document_diff.models import ParseError
from document_diff.parsers import parse_document
from helpers import make_docx, make_md, make_pdf

ITEMS = [("h1", "Chương I. Quy định chung"), ("h2", "Điều 1. Phạm vi"),
         ("p", "Văn bản này quy định về thời hạn lưu trữ tài liệu."), ("li", "Mục thứ nhất của danh sách."),
         ("table", "Tên|Giá trị;Thời hạn|3 năm")]


def test_markdown_vietnamese_structure():
    r = parse_document(make_md(ITEMS[:4]), "a.md")
    kinds = [b.kind for b in r.blocks]
    assert kinds == ["heading", "heading", "paragraph", "list"]
    assert r.blocks[2].section_path == ["Chương I. Quy định chung", "Điều 1. Phạm vi"]
    assert "thời hạn lưu trữ" in r.blocks[2].text


def test_markdown_table():
    md = b"| a | b |\n|---|---|\n| 1 | 2 |\n"
    r = parse_document(md, "t.md")
    assert len(r.blocks) == 1 and r.blocks[0].kind == "table"
    assert r.blocks[0].table_cells == [["a", "b"], ["1", "2"]]


def test_docx_order_and_tables():
    r = parse_document(make_docx(ITEMS), "a.docx")
    assert [b.kind for b in r.blocks] == ["heading", "heading", "paragraph", "list", "table"]
    assert r.blocks[-1].table_cells == [["Tên", "Giá trị"], ["Thời hạn", "3 năm"]]
    assert len(r.blocks[0].content_hash) == 64


def test_pdf_pages_headings_and_footer_dropped():
    pdf = make_pdf([[("h1", "Title one"), ("p", "Hello world paragraph one.")],
                    [("p", "Second page paragraph.")]])
    r = parse_document(pdf, "a.pdf")
    assert [b.page for b in r.blocks] == [1, 1, 2]
    assert r.blocks[0].kind == "heading"
    assert all(not b.text.strip().isdigit() for b in r.blocks)  # page numbers removed


def test_scanned_pdf_detected():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(fitz.Rect(10, 10, 200, 200), pixmap=pix)
    with pytest.raises(ParseError, match="scanned|OCR"):
        parse_document(doc.tobytes(), "scan.pdf")


@pytest.mark.parametrize("name,data", [("x.pdf", b"not a pdf"), ("x.docx", b"not a docx"),
                                       ("x.md", b"\xff\xfe\x00bad"), ("x.txt", b"hi"), ("x.md", b""),
                                       ("x.docx", b"PKbroken")])
def test_invalid_inputs_raise(name, data):
    with pytest.raises(ParseError):
        parse_document(data, name)

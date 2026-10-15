"""DOCX parser based on python-docx. Preserves document order of paragraphs and tables."""
from __future__ import annotations

import io
import re

from ..models import ParseError, ParseResult
from .common import BlockBuilder


def parse_docx(data: bytes, id_prefix: str = "b") -> ParseResult:
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:  # pragma: no cover
        raise ParseError("python-docx is not installed") from exc
    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("Cannot open DOCX (corrupted or not a DOCX): %s" % exc) from exc

    bb = BlockBuilder(id_prefix)
    n_par = n_tbl = 0
    try:
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                n_par += 1
                p = Paragraph(child, doc)
                text = p.text
                style = (p.style.name if p.style is not None else "") or ""
                ref = "paragraph %d" % n_par
                m = re.match(r"(?i)heading\s*(\d+)", style)
                if m:
                    bb.add("heading", text, level=min(int(m.group(1)), 6), source_ref=ref)
                elif style.lower() == "title":
                    bb.add("heading", text, level=1, source_ref=ref)
                else:
                    ppr = child.pPr
                    is_list = style.lower().startswith("list") or (ppr is not None and ppr.numPr is not None)
                    bb.add("list" if is_list else "paragraph", text, source_ref=ref)
            elif tag == "tbl":
                n_tbl += 1
                table = Table(child, doc)
                grid = []
                for row in table.rows:
                    seen, cells = set(), []
                    for cell in row.cells:
                        if id(cell._tc) in seen:
                            continue  # merged cell repeated
                        seen.add(id(cell._tc))
                        cells.append(" ".join(cell.text.split()))
                    if any(cells):
                        grid.append(cells)
                if grid:
                    bb.add("table", "\n".join(" | ".join(r) for r in grid), table_cells=grid,
                           source_ref="table %d" % n_tbl)
    except Exception as exc:
        raise ParseError("Failed to read DOCX content: %s" % exc) from exc

    if not bb.blocks:
        raise ParseError("DOCX contains no text")
    return ParseResult(bb.blocks, [], {"paragraphs": n_par, "tables": n_tbl})

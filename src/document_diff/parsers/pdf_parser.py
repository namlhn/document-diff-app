"""PDF parser based on PyMuPDF.

Keeps page/bbox/reading order, removes repeated headers/footers and page numbers,
stitches paragraphs split across pages, and infers headings from font + regex.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List

from ..models import ParseError, ParseResult
from ..normalize import normalize_text
from .common import BlockBuilder

_PAGE_NO = re.compile(r"^(?:page|trang)?\s*\d+(?:\s*(?:/|of)\s*\d+)?$", re.IGNORECASE)
_MARGIN = 0.08  # top/bottom fraction treated as header/footer zone
_HF_PAGE_RATIO = 0.4
_SENTENCE_END = (".", ":", ";", "!", "?", "…")
_LIST_ITEM = re.compile(r"^(?:[-•*·▪●‣◦]|\(?\d+[.)]|\(?[a-zđ][.)])\s", re.IGNORECASE)
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-ZĐÀ-Ỹ]")
_LEGAL_HEADING = re.compile(r"^(CHƯƠNG|MỤC|ĐIỀU|PHẦN|CHAPTER|SECTION|ARTICLE|PART)\s+[IVXLCDM\d]+", re.IGNORECASE)

_ALL_CAPS_HEADING = re.compile(
    r"^[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ\d\s&/,\-–—()]{3,80}$"
)


def _join_lines(lines: List[str]) -> str:
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif re.search(r"[^\W\d_]-$", out) and ln[:1].islower():
            out = out[:-1] + ln  # de-hyphenate across line break
        else:
            out += " " + ln
    return out


def _signature(text: str) -> str:
    return re.sub(r"\d+", "#", normalize_text(text))


def parse_pdf(data: bytes, id_prefix: str = "b") -> ParseResult:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise ParseError("PyMuPDF is not installed") from exc
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError("Cannot open PDF (corrupted or not a PDF): %s" % exc) from exc
    if doc.needs_pass:
        raise ParseError("PDF is encrypted / password protected")

    entries: List[Dict] = []
    scanned_pages: List[int] = []
    warnings: List[str] = []
    try:
        for pno, page in enumerate(doc, start=1):
            height = page.rect.height or 1
            d = page.get_text("dict", sort=True)
            page_chars = 0
            has_image = False
            for b in d.get("blocks", []):
                if b.get("type") == 1:
                    has_image = True
                    continue
                if b.get("type") != 0:
                    continue
                lines, sizes, bold_chars, total = [], [], 0, 0
                for ln in b.get("lines", []):
                    txt = "".join(s.get("text", "") for s in ln.get("spans", [])).strip()
                    if not txt:
                        continue
                    lines.append(txt)
                    for s in ln.get("spans", []):
                        n = len(s.get("text", "").strip())
                        total += n
                        sizes.append((round(s.get("size", 0), 1), n))
                        if s.get("flags", 0) & 16 or "bold" in s.get("font", "").lower():
                            bold_chars += n
                if not lines:
                    continue
                x0, y0, x1, y1 = b["bbox"]
                main = Counter()
                for sz, n in sizes:
                    main[sz] += n
                page_chars += total
                entries.append({
                    "page": pno, "bbox": (x0, y0, x1, y1), "text": _join_lines(lines), "nlines": len(lines),
                    "size": main.most_common(1)[0][0] if main else 0, "sizes": sizes,
                    "bold": total > 0 and bold_chars >= total * 0.8, "height": height,
                    "margin": y1 < height * _MARGIN or y0 > height * (1 - _MARGIN),
                })
            if page_chars == 0 and has_image:
                scanned_pages.append(pno)
    except Exception as exc:
        raise ParseError("Failed to read PDF content: %s" % exc) from exc

    n_pages = doc.page_count
    doc.close()
    if scanned_pages:
        warnings.append(
            "PDF has %d page(s) without a text layer (scanned images, OCR not supported): %s"
            % (len(scanned_pages), ", ".join(map(str, scanned_pages[:20])) + (" ..." if len(scanned_pages) > 20 else ""))
        )

    # --- header / footer removal: margin text repeated (digits ignored) on >= 40% pages
    pages_by_sig: Dict[str, set] = defaultdict(set)
    for e in entries:
        if e["margin"]:
            pages_by_sig[_signature(e["text"])].add(e["page"])
    min_pages = max(2, math.ceil(_HF_PAGE_RATIO * n_pages))
    repeated = {s for s, p in pages_by_sig.items() if len(p) >= min_pages}
    kept = [e for e in entries
            if not (e["margin"] and (_signature(e["text"]) in repeated or _PAGE_NO.match(e["text"].strip())))]
    removed = len(entries) - len(kept)

    if not kept:
        raise ParseError("No extractable text in PDF. It may be a scanned document; OCR is not supported yet.")

    size_weights: Counter = Counter()
    for e in kept:
        for sz, n in e["sizes"]:
            size_weights[sz] += n
    body = size_weights.most_common(1)[0][0]
    heading_sizes = sorted({e["size"] for e in kept if body and e["size"] >= body * 1.15}, reverse=True)

    for e in kept:
        t = e["text"]
        big = e["size"] in heading_sizes
        is_all_caps = bool(_ALL_CAPS_HEADING.fullmatch(t)) and any(c.isalpha() for c in t)
        e["heading"] = e["nlines"] <= 2 and len(t) <= 200 and (
            big or (e["bold"] and (
                _LEGAL_HEADING.match(t) or _NUMBERED_HEADING.match(t)
                or (e["nlines"] == 1 and is_all_caps))))
        e["level"] = min(heading_sizes.index(e["size"]) + 1, 6) if big else 2

    # --- cross-page paragraph stitching
    items: List[Dict] = []
    stitched = 0
    for e in kept:
        prev = items[-1] if items else None
        if (prev is not None and not prev["heading"] and not e["heading"]
                and e["page"] == prev["pages"][-1] + 1
                and not prev["text"].rstrip().endswith(_SENTENCE_END) and len(prev["text"]) >= 30
                and not _LIST_ITEM.match(e["text"])
                and prev["last_y1"] > prev["height"] * 0.75 and e["bbox"][1] < e["height"] * 0.3
                and abs(prev["size"] - e["size"]) < 0.6):
            prev["text"] = _join_lines([prev["text"], e["text"]])
            prev["pages"].append(e["page"])
            prev["last_y1"] = e["bbox"][3]
            stitched += 1
            continue
        items.append(dict(e, pages=[e["page"]], last_y1=e["bbox"][3]))

    bb = BlockBuilder(id_prefix)
    for it in items:
        ref = "page %s" % ("-".join(map(str, (it["pages"][0], it["pages"][-1]))) if len(it["pages"]) > 1
                          else it["pages"][0])
        if it["heading"]:
            bb.add("heading", it["text"], level=it["level"], page=it["page"], pages=it["pages"],
                   bbox=it["bbox"], source_ref=ref)
        else:
            bb.add("paragraph", it["text"], page=it["page"], pages=it["pages"], bbox=it["bbox"], source_ref=ref)
    return ParseResult(bb.blocks, warnings, {
        "pages": n_pages, "scanned_pages": scanned_pages, "header_footer_removed": removed,
        "stitched_paragraphs": stitched})

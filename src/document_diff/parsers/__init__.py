"""Parser dispatch and upload validation."""
from __future__ import annotations

import hashlib
import os
from typing import Tuple

from ..models import ParseError, ParseResult
from .docx_parser import parse_docx
from .markdown_parser import parse_markdown
from .pdf_parser import parse_pdf

SUPPORTED = {".pdf": parse_pdf, ".docx": parse_docx, ".md": parse_markdown, ".markdown": parse_markdown}


def validate_upload(data: bytes, filename: str, max_mb: int = 50) -> Tuple[str, str]:
    """Return (extension, sha256). Raises ParseError for invalid input."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED:
        raise ParseError("Unsupported file type '%s' (%s). Supported: .pdf, .docx, .md" % (ext, filename))
    if not data:
        raise ParseError("File is empty: %s" % filename)
    if len(data) > max_mb * 1024 * 1024:
        raise ParseError("File %s exceeds the %d MB limit" % (filename, max_mb))
    if ext == ".pdf" and not data.lstrip()[:5] == b"%PDF-":
        raise ParseError("%s is not a valid PDF (missing %%PDF header)" % filename)
    if ext == ".docx" and data[:2] != b"PK":
        raise ParseError("%s is not a valid DOCX (not a zip container)" % filename)
    return ext, hashlib.sha256(data).hexdigest()


def parse_document(data: bytes, filename: str, id_prefix: str = "b", max_mb: int = 50) -> ParseResult:
    ext, sha256 = validate_upload(data, filename, max_mb)
    result = SUPPORTED[ext](data, id_prefix)
    result.metadata["sha256"] = sha256
    return result


__all__ = ["parse_document", "validate_upload", "parse_pdf", "parse_docx", "parse_markdown"]

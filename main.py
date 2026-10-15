"""FastAPI application entrypoint for Document Diff API.

Run with:
    uvicorn main:app --reload --port 8000
or:
    python main.py
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from document_diff.diff import unified_patch
from document_diff.models import CompareOptions, ParseError
from document_diff.pipeline import compare_documents
from document_diff.reports import render_html, to_dict

MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown"}

app = FastAPI(
    title="Document Diff API",
    description="REST API for structural & granular document comparison (PDF, DOCX, Markdown).",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_file_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}' for file '{filename}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "app": "Document Diff API", "version": "2.0.0"}


@app.post("/api/v1/diff", summary="Compare two documents and return JSON report (Contract v2.0)")
async def compare_documents_json(
    old_file: UploadFile = File(..., description="Original (before) document: .pdf, .docx, or .md"),
    new_file: UploadFile = File(..., description="Modified (after) document: .pdf, .docx, or .md"),
    ignore_formatting: bool = Form(True, description="Ignore whitespace, quote, and punctuation differences"),
    fuzzy_threshold: int = Form(75, ge=50, le=100, description="Similarity threshold (%) for MODIFIED classification"),
    unresolved_threshold: int = Form(55, ge=30, le=90, description="Similarity threshold (%) for UNRESOLVED classification"),
    include_unchanged: bool = Form(False, description="Include UNCHANGED blocks in the changes list"),
    include_spans: bool = Form(True, description="Include word-level inline diff spans"),
):
    """Upload two documents and receive a comprehensive structured JSON diff report."""
    _validate_file_extension(old_file.filename or "")
    _validate_file_extension(new_file.filename or "")

    old_bytes = await old_file.read()
    new_bytes = await new_file.read()

    opts = CompareOptions(
        ignore_formatting=ignore_formatting,
        fuzzy_threshold=fuzzy_threshold,
        unresolved_threshold=unresolved_threshold,
        max_upload_mb=MAX_MB,
    )

    try:
        result = await run_in_threadpool(
            compare_documents,
            old_bytes,
            old_file.filename or "old_file",
            new_bytes,
            new_file.filename or "new_file",
            options=opts,
        )
    except ParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {exc}")

    return to_dict(result, include_unchanged=include_unchanged, include_spans=include_spans)


@app.post("/api/v1/diff/html", response_class=HTMLResponse, summary="Compare two documents and return standalone HTML report")
async def compare_documents_html(
    old_file: UploadFile = File(..., description="Original (before) document"),
    new_file: UploadFile = File(..., description="Modified (after) document"),
    ignore_formatting: bool = Form(True, description="Ignore whitespace differences"),
    fuzzy_threshold: int = Form(75, ge=50, le=100),
    show_unchanged: bool = Form(False, description="Display unchanged blocks as well"),
    review_only: bool = Form(False, description="Display only changes flagged for review"),
):
    """Upload two documents and receive a complete self-contained HTML side-by-side report."""
    _validate_file_extension(old_file.filename or "")
    _validate_file_extension(new_file.filename or "")

    old_bytes = await old_file.read()
    new_bytes = await new_file.read()

    opts = CompareOptions(
        ignore_formatting=ignore_formatting,
        fuzzy_threshold=fuzzy_threshold,
        max_upload_mb=MAX_MB,
    )

    try:
        result = await run_in_threadpool(
            compare_documents,
            old_bytes,
            old_file.filename or "old_file",
            new_bytes,
            new_file.filename or "new_file",
            options=opts,
        )
    except ParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {exc}")

    html_content = render_html(
        result,
        show_unchanged=show_unchanged,
        full_page=True,
        review_only=review_only,
    )
    return HTMLResponse(content=html_content)


@app.post("/api/v1/diff/patch", response_class=PlainTextResponse, summary="Compare two documents and return Unified Diff patch")
async def compare_documents_patch(
    old_file: UploadFile = File(..., description="Original (before) document"),
    new_file: UploadFile = File(..., description="Modified (after) document"),
    ignore_formatting: bool = Form(True),
):
    """Upload two documents and receive standard unified diff patch text."""
    _validate_file_extension(old_file.filename or "")
    _validate_file_extension(new_file.filename or "")

    old_bytes = await old_file.read()
    new_bytes = await new_file.read()

    opts = CompareOptions(ignore_formatting=ignore_formatting, max_upload_mb=MAX_MB)

    try:
        result = await run_in_threadpool(
            compare_documents,
            old_bytes,
            old_file.filename or "old_file",
            new_bytes,
            new_file.filename or "new_file",
            options=opts,
        )
    except ParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Comparison failed: {exc}")

    patch_text = unified_patch(result.changes, result.old_file, result.new_file)
    return PlainTextResponse(content=patch_text)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

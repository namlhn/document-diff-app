# Document Diff

Compare two documents (`.pdf`, `.docx`, `.md`) side by side, like a source-code diff tool. Runs locally.

## How it works

Parse (PDF: header/footer removal, cross-page paragraph stitching, heading inference) → canonical `DocumentBlock[]` → structural alignment (exact anchors → moves → headings → split/merge healing 1‑N / N‑1 → fuzzy in gaps → fuzzy moves) → classify (`ADDED / DELETED / MODIFIED / MOVED / UNRESOLVED / FORMATTING_ONLY`, with `review_required` + `review_reason`) → word-level inline diff (diff-match-patch) and table row/cell diff → viewer (changes with context, or paginated by Chương/Mục) / JSON (schema 2.0) / HTML / unified patch.

Similarity scores are string similarity, **not** confidence. Defaults: ≥75% → `MODIFIED`, 55–75% → `UNRESOLVED` (needs review). This is stricter than the 40/65% proposed in plan v2, because RapidFuzz scores of 50–60% often occur between unrelated paragraphs; all thresholds are in `CompareOptions`.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Web UI (Streamlit)
streamlit run app.py

# 2. REST API (FastAPI)
python main.py
# Hoặc chạy qua uvicorn:
uvicorn main:app --reload --port 8000

# 3. CLI
python -m document_diff.cli old.pdf new.docx --json out.json --html out.html --patch out.diff

# 4. Tests
pytest
```

### FastAPI Endpoints (`main.py`):
- `GET /health`: Health check API.
- `POST /api/v1/diff`: Nhận `old_file` và `new_file` (multipart/form-data), trả về kết quả JSON theo Schema Contract v2.0.
- `POST /api/v1/diff/html`: Trả về báo cáo HTML side-by-side độc lập.
- `POST /api/v1/diff/patch`: Trả về unified diff patch dạng text.
- Tài liệu Swagger UI tự động tại: `http://localhost:8000/docs`

Docker: `docker build -t document-diff . && docker run -p 8501:8501 document-diff`. Upload limit: `MAX_UPLOAD_MB` (default 50).

## Known limitations

- No OCR: scanned PDFs are detected and warned about; a fully scanned PDF is rejected rather than reported as "no changes".
- PDF reading order relies on PyMuPDF sorting; multi-column layouts may need review. Headings are guessed from font size.
- Cross-format comparison (PDF ↔ DOCX ↔ MD) works, but paragraph boundaries differ between formats; expect more `UNRESOLVED`.
- DOCX has no page numbers (not stored in the file); location is paragraph/table reference.
- Line diff uses stdlib `difflib` (pygit2/libgit2 not integrated); inline diff uses the `diff-match-patch` PyPI package on word tokens.
- Not covered: AI summarisation, legal-effect analysis, amendment-command extraction, version history, database.

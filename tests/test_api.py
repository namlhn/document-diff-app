"""Tests for FastAPI endpoints in main.py."""
import pytest

from fastapi.testclient import TestClient

from main import app
from helpers import make_md

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_api_diff_json():
    old_md = make_md([("h1", "Điều 1"), ("p", "Thời hạn là 3 năm.")])
    new_md = make_md([("h1", "Điều 1"), ("p", "Thời hạn là 5 năm.")])

    response = client.post(
        "/api/v1/diff",
        files={
            "old_file": ("old.md", old_md, "text/markdown"),
            "new_file": ("new.md", new_md, "text/markdown"),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "2.0"
    assert data["summary"]["modified"] == 1
    assert data["changes"][0]["change_type"] == "MODIFIED"


def test_api_diff_html():
    old_md = make_md([("p", "Văn bản cũ")])
    new_md = make_md([("p", "Văn bản mới")])

    response = client.post(
        "/api/v1/diff/html",
        files={
            "old_file": ("old.md", old_md, "text/markdown"),
            "new_file": ("new.md", new_md, "text/markdown"),
        },
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_api_diff_patch():
    old_md = make_md([("p", "Dòng ban đầu")])
    new_md = make_md([("p", "Dòng đã sửa đổi")])

    response = client.post(
        "/api/v1/diff/patch",
        files={
            "old_file": ("old.md", old_md, "text/markdown"),
            "new_file": ("new.md", new_md, "text/markdown"),
        },
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "--- a/old.md" in response.text
    assert "+++ b/new.md" in response.text


def test_api_invalid_file_extension():
    response = client.post(
        "/api/v1/diff",
        files={
            "old_file": ("invalid.txt", b"plain text", "text/plain"),
            "new_file": ("valid.md", b"markdown text", "text/markdown"),
        },
    )
    assert response.status_code == 400
    assert "Chỉ chấp nhận .pdf, .docx, .md" in response.json()["detail"]


@pytest.mark.parametrize("endpoint", ["/api/v1/diff", "/api/v1/diff/html", "/api/v1/diff/patch"])
def test_comparison_runs_outside_event_loop(monkeypatch, endpoint):
    import asyncio
    import main

    original = main.compare_documents
    worker_calls = []

    def compare_in_worker(*args, **kwargs):
        with pytest.raises(RuntimeError, match="no running event loop"):
            asyncio.get_running_loop()
        worker_calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(main, "compare_documents", compare_in_worker)
    response = client.post(endpoint, files={
        "old_file": ("old.md", b"Old paragraph.", "text/markdown"),
        "new_file": ("new.md", b"New paragraph.", "text/markdown"),
    })
    assert response.status_code == 200
    assert worker_calls == [True]


@pytest.mark.parametrize("endpoint", ["/api/v1/diff", "/api/v1/diff/html", "/api/v1/diff/patch"])
@pytest.mark.parametrize("names", [("a.pdf", "b.docx"), ("a.markdown", "b.markdown")])
def test_api_rejects_invalid_file_pair(endpoint, names):
    response = client.post(endpoint, files={
        "old_file": (names[0], b"content"), "new_file": (names[1], b"content"),
    })
    assert response.status_code == 400


@pytest.mark.parametrize("endpoint", ["/api/v1/diff", "/api/v1/diff/html", "/api/v1/diff/patch"])
def test_api_reports_scanned_pdf(endpoint):
    import fitz

    with fitz.open() as doc:
        page = doc.new_page()
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), False)
        pix.set_rect(pix.irect, (200, 200, 200))
        page.insert_image(fitz.Rect(10, 10, 200, 200), pixmap=pix)
        data = doc.tobytes()
    response = client.post(endpoint, files={
        "old_file": ("scan.pdf", data), "new_file": ("new.pdf", data),
    })
    assert response.status_code == 422
    assert "scan/ảnh" in response.json()["detail"]
    assert "OCR" in response.json()["detail"]

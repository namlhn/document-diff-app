"""Tests for FastAPI endpoints in main.py."""
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
    assert "Unsupported file type" in response.json()["detail"]

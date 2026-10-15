from document_diff.diff import inline_diff, unified_patch
from document_diff.reports import to_dict
from document_diff.pipeline import compare_documents
from helpers import make_md


def test_inline_diff_word_level_offsets():
    old, new = "Thời hạn lưu trữ là 3 năm.", "Thời hạn lưu trữ là 5 năm."
    spans = inline_diff(old, new)
    dels = [s for s in spans if s["op"] == "delete"]
    ins = [s for s in spans if s["op"] == "insert"]
    assert [s["text"] for s in dels] == ["3"] and [s["text"] for s in ins] == ["5"]
    assert old[dels[0]["old_start"]:dels[0]["old_end"]] == "3"
    assert new[ins[0]["new_start"]:ins[0]["new_end"]] == "5"
    assert "".join(s["text"] for s in spans if s["op"] != "insert") == old
    assert "".join(s["text"] for s in spans if s["op"] != "delete") == new


def test_inline_diff_identical():
    assert [s["op"] for s in inline_diff("abc def", "abc def")] == ["equal"]


def test_summary_consistent_with_changes_and_json():
    old = make_md([("h2", "Điều 1"), ("p", "Thời hạn lưu trữ là 3 năm."), ("p", "Đoạn bị xóa hoàn toàn khỏi văn bản."),
                   ("p", "Đoạn giữ nguyên không thay đổi gì cả trong tài liệu.")])
    new = make_md([("h2", "Điều 1"), ("p", "Thời hạn lưu trữ là 5 năm."),
                   ("p", "Đoạn giữ nguyên không thay đổi gì cả trong tài liệu."),
                   ("p", "Một quy định hoàn toàn mới được bổ sung ở cuối.")])
    res = compare_documents(old, "a.md", new, "b.md")
    d = to_dict(res)
    counts = {}
    for c in d["changes"]:
        counts[c["change_type"].lower()] = counts.get(c["change_type"].lower(), 0) + 1
    for k, v in counts.items():
        assert d["summary"][k] == v
    assert d["summary"]["modified"] == 1 and d["summary"]["added"] == 1 and d["summary"]["deleted"] == 1
    patch = unified_patch(res.changes, "a.md", "b.md")
    assert "-Thời hạn lưu trữ là 3 năm." in patch and "+Thời hạn lưu trữ là 5 năm." in patch

from document_diff.matching import align
from document_diff.models import CompareOptions
from document_diff.normalize import normalize_text
from document_diff.parsers.common import BlockBuilder


def blocks(texts, prefix="b"):
    bb = BlockBuilder(prefix)
    for t in texts:
        bb.add("paragraph", t)
    return bb.blocks


P = [
    "Bên A có nghĩa vụ thanh toán đầy đủ trong thời hạn quy định của hợp đồng này.",
    "Bên B có trách nhiệm giao hàng đúng chất lượng và số lượng đã thỏa thuận.",
    "Mọi tranh chấp phát sinh sẽ được giải quyết bằng thương lượng giữa các bên.",
    "Hợp đồng có hiệu lực kể từ ngày ký và kéo dài trong vòng hai mươi bốn tháng.",
]


def mapping(old, new, **kw):
    return {(p.old, p.new): p for p in align(old, new, CompareOptions(**kw))}


def test_insert_at_start_does_not_shift():
    m = mapping(blocks(P), blocks(["Đoạn mới thêm vào đầu tài liệu hoàn toàn khác."] + P))
    assert set(m) == {(0, 1), (1, 2), (2, 3), (3, 4)}
    assert all(p.method == "exact" for p in m.values())


def test_modified_paragraph_is_paired():
    new = list(P)
    new[3] = new[3].replace("hai mươi bốn", "ba mươi sáu")
    m = mapping(blocks(P), blocks(new))
    assert m[(3, 3)].method == "fuzzy"


def test_exact_move_detected():
    new = [P[2], P[0], P[1], P[3]]
    m = mapping(blocks(P), blocks(new))
    moved = [p for p in m.values() if p.moved]
    assert len(moved) >= 1 and all(p.score == 1.0 for p in moved)
    assert len(m) == 4


def test_one_to_one_with_duplicates():
    dup = "Điều khoản bảo mật được áp dụng cho cả hai bên trong mọi trường hợp."
    old, new = blocks([dup, dup, P[0]]), blocks([dup, P[0]])
    pairs = align(old, new)
    assert len({p.new for p in pairs}) == len(pairs)
    assert len({p.old for p in pairs}) == len(pairs)
    assert len(pairs) == 2  # one duplicate remains unmatched (deleted)


def test_renumbering_pairs_by_content():
    old = blocks(["1. " + P[0], "2. " + P[1]])
    new = blocks(["2. " + P[0], "3. " + P[1]])
    m = mapping(old, new)
    assert set(m) == {(0, 0), (1, 1)}


def test_unrelated_blocks_remain_unmatched():
    assert align(blocks([P[0]]), blocks(["Hoàn toàn khác biệt: lorem ipsum dolor sit amet xyz."])) == []


def test_normalize_formatting():
    assert normalize_text("a\u00a0 b\u2019s  \u2013 c") == "a b's - c"

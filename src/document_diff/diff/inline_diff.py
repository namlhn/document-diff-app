"""Word-level inline diff using diff-match-patch (Python package) on tokenized text."""
from __future__ import annotations

import re
from typing import Dict, List

_TOKEN = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text)


def _code(n: int) -> str:
    c = 0x100 + n
    if c >= 0xD800:
        c += 0x800  # skip surrogate range
    return chr(c)


def _raw_diff(old: str, new: str):
    from diff_match_patch import diff_match_patch

    ot, nt = tokenize(old), tokenize(new)
    vocab: Dict[str, str] = {}
    rev: Dict[str, str] = {}

    def enc(tokens):
        out = []
        for t in tokens:
            ch = vocab.get(t)
            if ch is None:
                ch = vocab[t] = _code(len(vocab))
                rev[ch] = t
            out.append(ch)
        return "".join(out)

    dmp = diff_match_patch()
    dmp.Diff_Timeout = 2.0
    diffs = dmp.diff_main(enc(ot), enc(nt), False)
    return [(op, "".join(rev[c] for c in chars)) for op, chars in diffs]


def inline_diff(old: str, new: str) -> List[Dict]:
    """Return spans: {op: equal|delete|insert, text, old_start, old_end, new_start, new_end}.

    Whitespace-only equal runs sitting between two edits are absorbed so that a
    replaced phrase is highlighted as one block.
    """
    raw = _raw_diff(old, new)
    # absorb whitespace between edits
    segs = []
    for idx, (op, text) in enumerate(raw):
        if (op == 0 and text.strip() == "" and 0 < idx < len(raw) - 1
                and raw[idx - 1][0] != 0 and raw[idx + 1][0] != 0):
            segs.append((-1, text))
            segs.append((1, text))
        else:
            segs.append((op, text))
    # group edit runs into one delete + one insert
    merged = []
    dbuf, ibuf = "", ""
    for op, text in segs:
        if op == 0:
            if dbuf:
                merged.append((-1, dbuf))
            if ibuf:
                merged.append((1, ibuf))
            dbuf = ibuf = ""
            merged.append((0, text))
        elif op == -1:
            dbuf += text
        else:
            ibuf += text
    if dbuf:
        merged.append((-1, dbuf))
    if ibuf:
        merged.append((1, ibuf))

    spans, op_pos, np_pos = [], 0, 0
    names = {0: "equal", -1: "delete", 1: "insert"}
    for op, text in merged:
        o0, n0 = op_pos, np_pos
        if op in (0, -1):
            op_pos += len(text)
        if op in (0, 1):
            np_pos += len(text)
        spans.append({"op": names[op], "text": text, "old_start": o0, "old_end": op_pos,
                      "new_start": n0, "new_end": np_pos})
    return spans

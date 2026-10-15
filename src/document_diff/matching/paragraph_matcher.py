"""Structural alignment of old/new blocks.

Pipeline: exact anchors (order-preserving) -> exact moves -> heading fuzzy ->
fuzzy inside gaps between anchors -> fuzzy across distant positions (moves).
Every pairing is strictly one-to-one; leftovers become ADDED/DELETED.
"""
from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Dict, List, Sequence, Tuple

from ..models import CompareOptions, DocumentBlock
from ..normalize import match_text
from .common import Pair, greedy_fuzzy
from .merge_resolver import find_merges
from .section_matcher import match_headings


def align(old: Sequence[DocumentBlock], new: Sequence[DocumentBlock],
          opts: CompareOptions = None) -> List[Pair]:
    opts = opts or CompareOptions()
    mo: Dict[int, Pair] = {}
    mn: Dict[int, Pair] = {}
    pairs: List[Pair] = []

    def add(p: Pair) -> None:
        pairs.append(p)
        for i in [p.old] + p.old_more:
            mo[i] = p
        for j in [p.new] + p.new_more:
            mn[j] = p

    def free_old(lo=0, hi=None) -> List[int]:
        return [i for i in range(lo, len(old) if hi is None else hi) if i not in mo]

    def free_new(lo=0, hi=None) -> List[int]:
        return [j for j in range(lo, len(new) if hi is None else hi) if j not in mn]

    # 1. exact anchors keeping relative order (an inserted paragraph shifts nothing)
    sm = SequenceMatcher(None, [b.normalized_text for b in old], [b.normalized_text for b in new],
                         autojunk=False)
    gaps: List[Tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                add(Pair(i1 + k, j1 + k, "exact", 1.0))
        else:
            gaps.append((i1, i2, j1, j2))

    # 2. exact moves (identical text at a different position, one-to-one)
    pool: Dict[str, List[int]] = defaultdict(list)
    for j in free_new():
        if len(new[j].normalized_text) >= opts.min_move_length:
            pool[new[j].normalized_text].append(j)
    for i in free_old():
        key = old[i].normalized_text
        if len(key) >= opts.min_move_length and pool.get(key):
            add(Pair(i, pool[key].pop(0), "moved_exact", 1.0, True))

    # 3. headings
    for p in match_headings(old, new, free_old(), free_new()):
        add(p)

    # 4. fuzzy inside each gap: split/merge healing first, then one-to-one fuzzy
    for i1, i2, j1, j2 in gaps:
        for p in find_merges(old, new, free_old(i1, i2), free_new(j1, j2), opts):
            add(p)
        fo, fn = free_old(i1, i2), free_new(j1, j2)
        res = greedy_fuzzy([match_text(old[i].normalized_text) for i in fo],
                           [match_text(new[j].normalized_text) for j in fn], opts.unresolved_threshold)
        for a, b, s in res:
            method = "fuzzy" if s * 100 >= opts.fuzzy_threshold else "low"
            add(Pair(fo[a], fn[b], method, s))

    # 5. fuzzy across the document (moved + edited)
    fo, fn = free_old(), free_new()
    res = greedy_fuzzy([match_text(old[i].normalized_text) for i in fo],
                       [match_text(new[j].normalized_text) for j in fn], opts.move_threshold)
    for a, b, s in res:
        add(Pair(fo[a], fn[b], "moved_fuzzy", s, True))

    pairs.sort(key=lambda p: p.old)
    return pairs

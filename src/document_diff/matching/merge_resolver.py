"""Split/merge healing: 1-to-N and N-to-1 block grouping.

Typical case: a paragraph that one format keeps whole is split into two blocks
by the other (page break, column break, different paragraph boundaries).
A group is accepted only if the merged similarity clearly beats every single match.
"""
from __future__ import annotations

from typing import List, Sequence

from ..models import CompareOptions, DocumentBlock
from ..normalize import match_text
from .common import Pair

_MAX_COMPARISONS = 60000


def find_merges(old: Sequence[DocumentBlock], new: Sequence[DocumentBlock], free_old: Sequence[int],
                free_new: Sequence[int], opts: CompareOptions) -> List[Pair]:
    if not free_old or not free_new or len(free_old) * len(free_new) > _MAX_COMPARISONS:
        return []
    from rapidfuzz import fuzz

    fo, fn = set(free_old), set(free_new)
    ot = {i: match_text(old[i].normalized_text) for i in free_old}
    nt = {j: match_text(new[j].normalized_text) for j in free_new}
    cands = []

    for i in free_old:  # 1 old -> 2 new
        for j in free_new:
            if j + 1 in fn:
                sm = fuzz.ratio(ot[i], nt[j] + " " + nt[j + 1])
                if sm >= opts.merge_min_score:
                    gain = sm - max(fuzz.ratio(ot[i], nt[j]), fuzz.ratio(ot[i], nt[j + 1]))
                    if gain >= opts.merge_gain:
                        cands.append((sm, gain, [i], [j, j + 1]))
    for j in free_new:  # 2 old -> 1 new
        for i in free_old:
            if i + 1 in fo:
                sm = fuzz.ratio(ot[i] + " " + ot[i + 1], nt[j])
                if sm >= opts.merge_min_score:
                    gain = sm - max(fuzz.ratio(ot[i], nt[j]), fuzz.ratio(ot[i + 1], nt[j]))
                    if gain >= opts.merge_gain:
                        cands.append((sm, gain, [i, i + 1], [j]))

    cands.sort(key=lambda c: (-c[0], -c[1]))
    used_o, used_n, out = set(), set(), []
    for sm, _, os_, ns_ in cands:
        if used_o.intersection(os_) or used_n.intersection(ns_):
            continue
        used_o.update(os_)
        used_n.update(ns_)
        out.append(Pair(os_[0], ns_[0], "merged_fuzzy", sm / 100.0, old_more=os_[1:], new_more=ns_[1:]))
    return out

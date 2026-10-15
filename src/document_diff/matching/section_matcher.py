"""Heading/section matching for headings left unmatched by exact hashing."""
from __future__ import annotations

from typing import List, Sequence

from ..models import DocumentBlock
from ..normalize import match_text
from .common import Pair, greedy_fuzzy


def match_headings(old: Sequence[DocumentBlock], new: Sequence[DocumentBlock],
                   free_old: Sequence[int], free_new: Sequence[int], cutoff: float = 70) -> List[Pair]:
    """Fuzzy-match unmatched headings (renamed or renumbered sections)."""
    o = [i for i in free_old if old[i].kind == "heading"]
    n = [j for j in free_new if new[j].kind == "heading"]
    res = greedy_fuzzy([match_text(old[i].normalized_text) for i in o],
                       [match_text(new[j].normalized_text) for j in n], cutoff)
    return [Pair(o[a], n[b], "heading_fuzzy", s) for a, b, s in res]

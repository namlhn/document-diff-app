"""Shared types and fuzzy-matching primitives for the matchers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple


@dataclass
class Pair:
    old: int
    new: int
    method: str  # exact | moved_exact | heading_fuzzy | merged_fuzzy | fuzzy | low | moved_fuzzy
    score: float  # 0..1 similarity; NOT a confidence value
    moved: bool = False
    old_more: List[int] = field(default_factory=list)  # extra consecutive old blocks (N-to-1)
    new_more: List[int] = field(default_factory=list)  # extra consecutive new blocks (1-to-N)


def greedy_fuzzy(old_texts: Sequence[str], new_texts: Sequence[str], cutoff: float) -> List[Tuple[int, int, float]]:
    """One-to-one greedy assignment on RapidFuzz ratio (best scores first).

    Returns (old_local_idx, new_local_idx, score_0_to_1). Ties are broken by
    relative position so duplicated paragraphs keep their order.
    """
    if not old_texts or not new_texts:
        return []
    import numpy as np
    from rapidfuzz import fuzz, process

    mat = process.cdist(list(old_texts), list(new_texts), scorer=fuzz.ratio,
                        score_cutoff=cutoff, dtype=np.float32, workers=1)
    ii, jj = np.nonzero(mat >= cutoff)
    if len(ii) == 0:
        return []
    scores = mat[ii, jj]
    posdiff = np.abs(ii / max(len(old_texts), 1) - jj / max(len(new_texts), 1))
    order = np.lexsort((posdiff, -scores))
    used_o, used_n, out = set(), set(), []
    for k in order:
        i, j = int(ii[k]), int(jj[k])
        if i in used_o or j in used_n:
            continue
        used_o.add(i)
        used_n.add(j)
        out.append((i, j, float(scores[k]) / 100.0))
    return out

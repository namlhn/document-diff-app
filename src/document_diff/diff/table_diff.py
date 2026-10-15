"""Table diff: row alignment (difflib) then cell-by-cell inline diff."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence

from ..matching.common import greedy_fuzzy
from ..normalize import match_text
from .inline_diff import inline_diff


def _eq_cells(row: Sequence[str]) -> List[Dict[str, Any]]:
    return [{"col": c, "op": "equal", "spans": [{"op": "equal", "text": t}]} for c, t in enumerate(row)]


def _one_sided(row: Sequence[str], op: str) -> List[Dict[str, Any]]:
    name = "insert" if op == "added" else "delete"
    return [{"col": c, "op": op, "spans": [{"op": name, "text": t}]} for c, t in enumerate(row)]


def _modified_cells(o: Sequence[str], n: Sequence[str]) -> List[Dict[str, Any]]:
    cells = []
    for c in range(max(len(o), len(n))):
        ot = o[c] if c < len(o) else ""
        nt = n[c] if c < len(n) else ""
        if ot == nt:
            cells.append({"col": c, "op": "equal", "spans": [{"op": "equal", "text": nt}]})
        else:
            cells.append({"col": c, "op": "modified", "spans": inline_diff(ot, nt)})
    return cells


def table_diff(old_cells: List[List[str]], new_cells: List[List[str]]) -> List[Dict[str, Any]]:
    """Return ordered row records: {op: equal|modified|added|deleted, old_row, new_row, cells}."""
    orow = [" | ".join(r) for r in old_cells]
    nrow = [" | ".join(r) for r in new_cells]
    out: List[Dict[str, Any]] = []
    sm = SequenceMatcher(None, orow, nrow, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                out.append({"op": "equal", "old_row": i1 + k, "new_row": j1 + k, "cells": _eq_cells(new_cells[j1 + k])})
            continue
        fo, fn = list(range(i1, i2)), list(range(j1, j2))
        res = greedy_fuzzy([match_text(orow[i]) for i in fo], [match_text(nrow[j]) for j in fn], 50)
        kept, last_b = [], -1
        for a, b, _ in sorted(res):  # keep monotonic (order-preserving) pairs only
            if b > last_b:
                kept.append((fo[a], fn[b]))
                last_b = b
        di, dj = i1, j1
        for a, b in kept:
            while di < a:
                out.append({"op": "deleted", "old_row": di, "new_row": None, "cells": _one_sided(old_cells[di], "deleted")})
                di += 1
            while dj < b:
                out.append({"op": "added", "old_row": None, "new_row": dj, "cells": _one_sided(new_cells[dj], "added")})
                dj += 1
            out.append({"op": "modified", "old_row": a, "new_row": b, "cells": _modified_cells(old_cells[a], new_cells[b])})
            di, dj = a + 1, b + 1
        while di < i2:
            out.append({"op": "deleted", "old_row": di, "new_row": None, "cells": _one_sided(old_cells[di], "deleted")})
            di += 1
        while dj < j2:
            out.append({"op": "added", "old_row": None, "new_row": dj, "cells": _one_sided(new_cells[dj], "added")})
            dj += 1
    return out

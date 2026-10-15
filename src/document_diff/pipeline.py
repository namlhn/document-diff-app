"""End-to-end comparison pipeline."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from .diff import classify
from .matching import align
from .models import ComparisonResult, CompareOptions
from .parsers import parse_document, validate_file_pair


def compare_documents(old_data: bytes, old_name: str, new_data: bytes, new_name: str,
                      options: Optional[CompareOptions] = None) -> ComparisonResult:
    """Compare two documents. Raises ParseError on invalid/empty/unparseable input."""
    validate_file_pair(old_name, new_name)
    opts = options or CompareOptions()
    t0 = time.perf_counter()
    old_res = parse_document(old_data, old_name, "old", opts.max_upload_mb)
    new_res = parse_document(new_data, new_name, "new", opts.max_upload_mb)
    old_hash = old_res.metadata["sha256"]
    new_hash = new_res.metadata["sha256"]
    t1 = time.perf_counter()

    pairs = align(old_res.blocks, new_res.blocks, opts)
    t2 = time.perf_counter()
    changes = classify(old_res.blocks, new_res.blocks, pairs, opts)
    t3 = time.perf_counter()

    warnings = ["[old] " + w for w in old_res.warnings] + ["[new] " + w for w in new_res.warnings]
    if old_hash == new_hash:
        warnings.append("Both files are byte-identical.")
    stats = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "old_blocks": len(old_res.blocks), "new_blocks": len(new_res.blocks),
        "parse_seconds": round(t1 - t0, 3), "align_seconds": round(t2 - t1, 3),
        "diff_seconds": round(t3 - t2, 3), "total_seconds": round(t3 - t0, 3),
        "old_metadata": old_res.metadata, "new_metadata": new_res.metadata,
    }
    return ComparisonResult(
        comparison_id="cmp-" + uuid.uuid4().hex[:8], old_file=old_name, new_file=new_name,
        old_sha256=old_hash, new_sha256=new_hash, old_blocks=old_res.blocks, new_blocks=new_res.blocks,
        changes=changes, warnings=warnings, stats=stats)

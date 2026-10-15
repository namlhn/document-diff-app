"""Command line interface: document-diff OLD NEW [--json out.json] [--html out.html] [--patch out.diff]."""
from __future__ import annotations

import argparse
import os
import sys

from .diff import unified_patch
from .models import CompareOptions, ParseError
from .pipeline import compare_documents
from .reports import render_html, to_json


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="document-diff", description="Compare two PDF/DOCX/MD documents")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json")
    ap.add_argument("--html")
    ap.add_argument("--patch")
    ap.add_argument("--strict-formatting", action="store_true", help="report whitespace-only differences")
    args = ap.parse_args(argv)
    try:
        with open(args.old, "rb") as f:
            od = f.read()
        with open(args.new, "rb") as f:
            nd = f.read()
        res = compare_documents(od, os.path.basename(args.old), nd, os.path.basename(args.new),
                                CompareOptions(ignore_formatting=not args.strict_formatting))
    except (ParseError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    for w in res.warnings:
        print("warning: %s" % w, file=sys.stderr)
    print(res.summary)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(to_json(res))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(res, show_unchanged=False))
    if args.patch:
        with open(args.patch, "w", encoding="utf-8") as f:
            f.write(unified_patch(res.changes, res.old_file, res.new_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Markdown parser based on markdown-it-py (token AST)."""
from __future__ import annotations

from ..models import ParseError, ParseResult
from .common import BlockBuilder


def _inline_text(tok) -> str:
    parts = []
    for ch in tok.children or []:
        if ch.type in ("text", "code_inline"):
            parts.append(ch.content)
        elif ch.type in ("softbreak", "hardbreak"):
            parts.append(" ")
        elif ch.type == "image":
            parts.append(ch.content)
    return "".join(parts) if tok.children is not None else tok.content


def parse_markdown(data: bytes, id_prefix: str = "b") -> ParseResult:
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:  # pragma: no cover
        raise ParseError("markdown-it-py is not installed") from exc
    try:
        source = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError("Markdown file is not valid UTF-8: %s" % exc) from exc

    tokens = MarkdownIt("commonmark").enable("table").parse(source)
    bb = BlockBuilder(id_prefix)
    list_depth = 0
    i = 0

    def ref(tok) -> str:
        return "L%d-%d" % (tok.map[0] + 1, tok.map[1]) if tok.map else ""

    while i < len(tokens):
        tok = tokens[i]
        t = tok.type
        if t in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif t in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif t == "heading_open":
            bb.add("heading", _inline_text(tokens[i + 1]), level=int(tok.tag[1]), source_ref=ref(tok))
        elif t == "paragraph_open":
            bb.add("list" if list_depth > 0 else "paragraph", _inline_text(tokens[i + 1]), source_ref=ref(tok))
        elif t in ("fence", "code_block"):
            bb.add("paragraph", tok.content, source_ref=ref(tok))
        elif t == "table_open":
            grid, j = [], i + 1
            while tokens[j].type != "table_close":
                if tokens[j].type == "tr_open":
                    cells = []
                    j += 1
                    while tokens[j].type != "tr_close":
                        if tokens[j].type == "inline":
                            cells.append(_inline_text(tokens[j]).strip())
                        j += 1
                    if any(cells):
                        grid.append(cells)
                j += 1
            if grid:
                bb.add("table", "\n".join(" | ".join(r) for r in grid), table_cells=grid, source_ref=ref(tok))
            i = j
        i += 1

    if not bb.blocks:
        raise ParseError("Markdown file contains no text")
    return ParseResult(bb.blocks, [], {"lines": source.count("\n") + 1})

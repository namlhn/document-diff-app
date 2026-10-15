"""Text normalization helpers. Original text is always preserved separately."""
from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
_QUOTES = {
    ord("\u2018"): "'", ord("\u2019"): "'", ord("\u201a"): "'", ord("\u201b"): "'",
    ord("\u201c"): '"', ord("\u201d"): '"', ord("\u201e"): '"',
    ord("\u2010"): "-", ord("\u2011"): "-", ord("\u2012"): "-", ord("\u2013"): "-",
    ord("\u2014"): "-", ord("\u2212"): "-", ord("\u2026"): "...",
}
_WS = re.compile(r"\s+", re.UNICODE)

_NUMBERING = re.compile(
    r"""^\s*(?:
        (?:điều|chương|mục|phần|khoản|article|section|chapter|part|clause)\s+[0-9ivxlc]+[a-z]?\s*[.:)\-]?\s*
      | \d+(?:\.\d+)*[.)]?\s+
      | \(?[ivxlcdm]+[.)]\s+
      | \(?[a-zđ][.)]\s+
      | [-•*·▪●‣◦]\s+
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def normalize_text(text: str) -> str:
    """Normalize whitespace, quotes, dashes and invisible characters."""
    t = unicodedata.normalize("NFC", text).translate(_ZERO_WIDTH).translate(_QUOTES)
    return _WS.sub(" ", t).strip()


def match_text(normalized: str) -> str:
    """Text used for fuzzy matching: numbering stripped, lower-cased."""
    stripped = _NUMBERING.sub("", normalized, count=1)
    return (stripped or normalized).lower()

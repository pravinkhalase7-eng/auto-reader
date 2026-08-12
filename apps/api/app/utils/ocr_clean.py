"""Strip OCR garbage: chroma leftovers, headers, symbols, low-signal lines."""

from __future__ import annotations

import re

LETTER = re.compile(r"[A-Za-z\u0900-\u097F]")
GARBAGE_TOKEN = re.compile(
    r"^[\W_|~`^=*#@+$\\/<>\[\]{}©®™•·…“”\"'`´]+$|"
    r"^[Il1|]{3,}$"
)
PAGE_NUMBER_LINE = re.compile(r"^[\W_]*\d{1,3}[\W_]*$")
REPEATED_JUNK = re.compile(r"(.)\1{4,}")
URLISH = re.compile(r"(https?://|www\.)", re.I)


def _letter_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    letters = sum(1 for c in chars if LETTER.search(c))
    return letters / len(chars)


def _clean_token(token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    if GARBAGE_TOKEN.match(token):
        return None
    if len(token) == 1 and not LETTER.search(token) and token not in {".", ",", "?", "!", "।", ";", ":"}:
        return None
    return token


def clean_ocr_text(raw: str) -> str:
    """Keep real lesson language; drop decorative OCR noise."""
    if not raw:
        return ""

    text = raw.replace("\x0c", "\n").replace("\r\n", "\n")
    text = REPEATED_JUNK.sub(r"\1\1", text)

    kept_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        if PAGE_NUMBER_LINE.match(stripped):
            continue
        if URLISH.search(stripped):
            continue
        tokens = [_clean_token(t) for t in stripped.split()]
        words = [t for t in tokens if t]
        if not words:
            continue
        rebuilt = " ".join(words)
        if _letter_ratio(rebuilt) < 0.4 and len(rebuilt) > 4:
            continue
        kept_lines.append(rebuilt)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

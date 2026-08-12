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
DECORATIVE = re.compile(r"[\u00ad\u200b-\u200f\ufeff\u2500-\u259f\u25a0-\u25ff]")
CHROMA_RUN = re.compile(r"(?:\s*[|~^•·]{1,}\s*){2,}")
SHORT_LATIN = {"a", "i", "an", "am", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is", "it", "me", "my", "no", "of", "oh", "ok", "on", "or", "so", "to", "up", "us", "we"}


def _letter_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    letters = sum(1 for c in chars if LETTER.search(c))
    return letters / len(chars)


def _clean_token(token: str) -> str | None:
    token = DECORATIVE.sub("", token).strip()
    token = token.strip("|_~`^=*#@+$\\/<>[]{}©®™•·…“”\"'`´")
    if not token:
        return None
    if GARBAGE_TOKEN.match(token):
        return None
    if len(token) == 1 and not LETTER.search(token) and token not in {".", ",", "?", "!", "।", ";", ":"}:
        return None
    latin = re.sub(r"[^A-Za-z]", "", token)
    if len(token) <= 2 and latin.lower() == token.lower() and token.lower() not in SHORT_LATIN:
        if not re.search(r"[\u0900-\u097F]", token):
            return None
    if re.search(r"[A-Za-z\u0900-\u097F].*[\W_]|[\W_].*[A-Za-z\u0900-\u097F]", token):
        if not re.match(r"^[A-Za-z\u0900-\u097F]+[-'][A-Za-z\u0900-\u097F]+[.,!?;:।]?$", token):
            letters_only = re.sub(r"[^\w\u0900-\u097F]", "", token)
            if len(letters_only) < 3 and letters_only.lower() not in SHORT_LATIN:
                return None
            token = letters_only or token
    return token


def clean_ocr_text(raw: str) -> str:
    """Keep real lesson language; drop decorative OCR noise."""
    if not raw:
        return ""

    text = raw.replace("\x0c", "\n").replace("\r\n", "\n")
    text = DECORATIVE.sub(" ", text)
    text = REPEATED_JUNK.sub(r"\1\1", text)
    text = CHROMA_RUN.sub(" ", text)

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
        if _letter_ratio(rebuilt) < 0.5 and len(rebuilt) > 4:
            continue
        kept_lines.append(rebuilt)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


_SENTENCE_END = ".!?।\"'”’"


def merge_page_texts(page_texts: list[str]) -> str:
    """Join OCR pages into one continuous story, stitching mid-sentence page breaks."""
    chunks: list[str] = []
    for raw in page_texts:
        text = (raw or "").strip()
        if not text:
            continue
        if not chunks:
            chunks.append(text)
            continue
        prev = chunks[-1].rstrip()
        if prev and prev[-1] not in _SENTENCE_END:
            chunks[-1] = f"{prev} {text.lstrip()}"
        else:
            chunks.append(text)
    return "\n\n".join(chunks)

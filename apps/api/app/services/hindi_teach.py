"""Generate child-friendly Hindi explanations for lesson sentences."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.prompts import hindi_explain as prompts
from app.utils.segmentation import tokenize_words

logger = logging.getLogger(__name__)

EASY_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "at",
    "he",
    "she",
    "it",
    "they",
    "we",
    "you",
    "i",
    "his",
    "her",
    "their",
    "this",
    "that",
    "with",
    "for",
    "from",
    "as",
    "by",
    "not",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "did",
    "so",
    "but",
    "if",
    "then",
    "than",
    "into",
    "up",
    "out",
    "about",
    "said",
    "says",
}

COMMON_HI = {
    "forest": "जंगल",
    "lion": "शेर",
    "mouse": "चूहा",
    "king": "राजा",
    "queen": "रानी",
    "friend": "मित्र / दोस्त",
    "brave": "बहादुर",
    "afraid": "डरा हुआ",
    "hungry": "भूखा",
    "angry": "गुस्सा",
    "happy": "खुश",
    "sad": "उदास",
    "village": "गाँव",
    "river": "नदी",
    "mountain": "पहाड़",
    "clever": "चालाक",
    "kind": "दयालु",
    "strong": "मज़बूत",
    "weak": "कमज़ोर",
    "promise": "वादा",
    "help": "मदद",
    "escape": "भाग निकलना",
    "hunter": "शिकारी",
    "rope": "रस्सी",
    "net": "जाल",
}


def _clean_word(token: str) -> str:
    return re.sub(r"^[^\w]+|[^\w]+$", "", token, flags=re.UNICODE)


def _local_hard_words(text: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for raw in tokenize_words(text):
        word = _clean_word(raw)
        key = word.lower()
        if len(key) < 5 or key in EASY_WORDS or key in seen:
            continue
        seen.add(key)
        meaning = COMMON_HI.get(key)
        if not meaning and len(key) < 6:
            continue
        out.append(
            {
                "word": word,
                "meaning_hi": meaning or f"“{word}” — कहानी का एक ज़रूरी शब्द; ध्यान से समझो।",
            }
        )
        if len(out) >= 3:
            break
    return out


def _local_meaning(text: str) -> str:
    short = re.sub(r"\s+", " ", text).strip()
    if len(short) > 120:
        short = short[:117] + "…"
    return (
        f"इस वाक्य का सीधा मतलब है: कहानी में बताया गया है — “{short}”. "
        "इसे धीरे-धीरे दोबारा सोचो ताकि बात साफ़ समझ आए।"
    )


def local_explain(sentences: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for item in sentences:
        rows.append(
            {
                "id": item["id"],
                "text": item["text"],
                "meaning_hi": _local_meaning(item["text"]),
                "hard_words": _local_hard_words(item["text"]),
            }
        )
    return rows


async def _gemini_explain(title: str, language: str, sentences: list[dict[str, str]]) -> list[dict[str, Any]] | None:
    settings = get_settings()
    api_key = settings.resolved_gemini_api_key
    if not api_key:
        return None
    model = settings.gemini_model or "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    prompt = f"{prompts.SYSTEM}\n\n{prompts.user_prompt(title, language, sentences)}"
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
            )
        if resp.status_code >= 400:
            logger.warning("hindi_explain_gemini_http status=%s", resp.status_code)
            return None
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hindi_explain_gemini_failed err=%r", exc)
        return None

    by_id = {str(row.get("id")): row for row in (data.get("sentences") or []) if isinstance(row, dict)}
    rows: list[dict[str, Any]] = []
    for item in sentences:
        row = by_id.get(item["id"]) or {}
        hard = []
        for hw in row.get("hard_words") or []:
            if not isinstance(hw, dict):
                continue
            word = str(hw.get("word") or "").strip()
            meaning = str(hw.get("meaning_hi") or "").strip()
            if word and meaning:
                hard.append({"word": word, "meaning_hi": meaning})
        meaning_hi = str(row.get("meaning_hi") or "").strip() or _local_meaning(item["text"])
        rows.append(
            {
                "id": item["id"],
                "text": item["text"],
                "meaning_hi": meaning_hi,
                "hard_words": hard[:3] or _local_hard_words(item["text"]),
            }
        )
    return rows


async def explain_sentences_in_hindi(
    *,
    title: str,
    language: str,
    sentences: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if not sentences:
        return []
    gemini = await _gemini_explain(title, language, sentences)
    if gemini:
        return gemini
    return local_explain(sentences)


def spoken_hindi_script(meaning_hi: str) -> str:
    """Spoken line after each sentence — meaning only (hard words come at the end)."""
    return (meaning_hi or "").strip()


def collect_all_hard_words(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Dedupe hard words across the lesson, preserving first-seen order."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        for hw in row.get("hard_words") or []:
            if not isinstance(hw, dict):
                continue
            word = str(hw.get("word") or "").strip()
            meaning = str(hw.get("meaning_hi") or "").strip()
            if not word or not meaning:
                continue
            key = word.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"word": word, "meaning_hi": meaning})
    return out


def spoken_hard_words_script(hard_words: list[dict[str, str]]) -> str:
    """Spoken wrap-up of all hard words after the full story."""
    if not hard_words:
        return ""
    parts = ["अब कहानी के मुश्किल शब्द समझते हैं।"]
    for hw in hard_words:
        word = (hw.get("word") or "").strip()
        meaning = (hw.get("meaning_hi") or "").strip()
        if word and meaning:
            parts.append(f"{word} का मतलब है: {meaning}।")
    return " ".join(parts)

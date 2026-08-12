"""Fallback word timing when TTS provider does not return boundaries.

Isolated so it can be replaced by real timestamps from Google/OpenAI TTS.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WordTimingEstimate:
    word_id: str
    text: str
    start_ms: int
    end_ms: int


SPEED_FACTORS = {
    "very_slow": 0.55,
    "slow": 0.7,
    "normal": 0.85,
}


def estimate_word_timings(
    words: list[tuple[str, str]],
    *,
    speed: str = "slow",
    base_wpm: float = 110.0,
    pause_ms_between_sentences: int = 350,
) -> list[WordTimingEstimate]:
    """Estimate timings from word character length and speech rate.

    Tuned slower for children. Prefer real TTS word boundaries when available.
    words: list of (word_id, text)
    """
    factor = SPEED_FACTORS.get(speed, 0.7)
    ms_per_char = (60_000 / (base_wpm * 5)) / factor  # ~5 chars per word baseline

    timings: list[WordTimingEstimate] = []
    cursor = 250  # small lead-in

    for word_id, text in words:
        clean = text.strip(".,!?;:\"'()[]{}।")
        # Devanagari syllables need more time than Latin letters
        is_indic = any("\u0900" <= ch <= "\u097F" for ch in clean)
        base = max(220 if is_indic else 180, int(len(clean) * ms_per_char) + (120 if is_indic else 80))
        duration = base
        if text.endswith((".", "!", "?", "।")):
            duration += pause_ms_between_sentences
        end = cursor + duration
        timings.append(WordTimingEstimate(word_id=word_id, text=text, start_ms=cursor, end_ms=end))
        cursor = end + 60

    return timings

#!/usr/bin/env python3
"""Jenkins / CI smoke test for AI Teacher API image."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python scripts/jenkins_smoke.py` from apps/api (local + Docker PYTHONPATH=/app)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    os.environ.setdefault("SEED_ON_STARTUP", "false")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./smoke.db")
    os.environ.setdefault("SECRET_KEY", "jenkins-smoke-secret")
    os.environ.setdefault("AI_PROVIDER", "local")
    os.environ.setdefault("OCR_PROVIDER", "local")

    from app.main import app
    from app.utils.segmentation import reconstruct_from_text
    from app.utils.word_timing import estimate_word_timings
    from app.providers.ai import LocalAIProvider

    assert app.title, "app title missing"
    print("import_ok", app.title)

    tree = reconstruct_from_text(
        "The clever crow dropped pebbles into the pot.",
        title="The Clever Crow",
        language="en",
        content_type="story",
    )
    if tree.word_count < 3:
        print("FAIL segmentation word_count=", tree.word_count, file=sys.stderr)
        return 1
    print("segmentation_ok", tree.word_count)

    words = [("1", "The"), ("2", "crow"), ("3", "drank.")]
    timings = estimate_word_timings(words, speed="normal")
    if len(timings) != 3 or timings[-1].end_ms <= timings[0].start_ms:
        print("FAIL timings", timings, file=sys.stderr)
        return 1
    print("timings_ok", timings[-1].end_ms)

    import asyncio

    async def _quiz() -> None:
        ai = LocalAIProvider()
        qs = await ai.generate_questions(
            "The crow drank water from the pot.",
            "en",
            difficulty="easy",
            class_level=3,
            count=3,
        )
        if len(qs) < 2:
            raise SystemExit(f"FAIL quiz count={len(qs)}")
        print("quiz_ok", len(qs))

    asyncio.run(_quiz())
    print("smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

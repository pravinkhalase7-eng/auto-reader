"""Canonical assistant name: पवी (not पावी / Paavi)."""

from __future__ import annotations

import re

ASSISTANT_NAME = "पवी"
ASSISTANT_NAME_EN = "Pavi"

_PAAVI = re.compile(r"\bPaavi\b", re.IGNORECASE)


def canonicalize_pavi_spelling(text: str | None) -> str:
    if not text:
        return ""
    return _PAAVI.sub(ASSISTANT_NAME, text.replace("पावी", ASSISTANT_NAME))

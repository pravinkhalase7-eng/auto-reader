"""E.164 phone helpers. Never log full numbers."""

from __future__ import annotations

import phonenumbers
from phonenumbers import NumberParseException


def normalize_phone(number: str | None, default_region: str = "IN") -> str | None:
    if not number or not str(number).strip():
        return None
    raw = str(number).strip()
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def mask_phone(number: str | None) -> str:
    if not number:
        return ""
    digits = number.strip()
    if len(digits) <= 6:
        return "*" * len(digits)
    return f"{digits[:3]}******{digits[-4:]}"


def validate_phone(number: str | None, default_region: str = "IN") -> str:
    normalized = normalize_phone(number, default_region)
    if not normalized:
        raise ValueError("Please enter a valid phone number in E.164 format, e.g. +9198XXXXXXXX.")
    return normalized

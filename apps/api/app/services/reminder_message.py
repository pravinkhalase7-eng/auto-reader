"""Spoken reminder copy in English, Hindi, and Marathi."""

from __future__ import annotations

from app.models import Appointment, Reminder
from app.utils.datetime import from_utc
from app.utils.pavi_name import canonicalize_pavi_spelling


TEMPLATES = {
    "en": {
        "hello": "Hello, this is Pavi.",
        "item": "You have {title} today at {time} IST.",
        "appointment": "I'm calling about your appointment, {title}, at {time} IST.",
        "location": "Your appointment is at {location}.",
        "dont_forget": "Please don't forget.",
        "bye": "Have a great day.",
        "simple": "It's time to {title}.",
    },
    "hi": {
        "hello": "नमस्ते, मैं पवी हूँ।",
        "item": "आपकी {title} आज {time} बजे है।",
        "appointment": "मैं आपकी अपॉइंटमेंट के बारे में कॉल कर रही हूँ, {title}, {time} बजे।",
        "location": "यह {location} पर है।",
        "dont_forget": "कृपया इसे न भूलें।",
        "bye": "आपका दिन शुभ हो।",
        "simple": "{title} का समय हो गया है।",
    },
    "mr": {
        "hello": "नमस्कार, मी पवी आहे.",
        "item": "तुमची {title} आज {time} वाजता आहे.",
        "appointment": "मी तुमच्या अपॉइंटमेंटबद्दल कॉल करत आहे, {title}, {time} वाजता.",
        "location": "ही {location} येथे आहे.",
        "dont_forget": "कृपया विसरू नका.",
        "bye": "तुमचा दिवस चांगला जावो.",
        "simple": "{title} ची वेळ झाली आहे.",
    },
}


def _time_label(reminder: Reminder, language: str) -> str:
    local = from_utc(reminder.reminder_time_utc, reminder.timezone)
    if language == "hi":
        return local.strftime("%I:%M %p").lstrip("0")
    if language == "mr":
        return local.strftime("%I:%M %p").lstrip("0")
    return local.strftime("%I:%M %p").lstrip("0")


def generate_reminder_speech(
    reminder: Reminder,
    *,
    appointment: Appointment | None = None,
    language: str | None = None,
) -> str:
    lang = (language or reminder.language or "en").split("-")[0]
    t = TEMPLATES.get(lang, TEMPLATES["en"])
    title = canonicalize_pavi_spelling(reminder.title)
    time_label = _time_label(reminder, lang)
    location = appointment.location if appointment else None
    parts = [t["hello"]]
    if appointment or getattr(reminder, "appointment_id", None):
        parts.append(t["appointment"].format(title=title, time=time_label))
    else:
        parts.append(t["item"].format(title=title, time=time_label))
    if location:
        parts.append(t["location"].format(location=location))
    parts.append(t["dont_forget"])
    parts.append(t["bye"])
    return " ".join(parts)

"""Pavi agent: Google ADK + Gemini, with a deterministic mock fallback for tests/dev."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import PAVI_INSTRUCTION
from app.agents.tools import PAVI_TOOLS, pavi_db, pavi_user
from app.core.config import get_settings
from app.models import User
from app.services.preference_service import PreferenceService
from app.utils.datetime import format_local, now_utc

logger = logging.getLogger("app.pavi.agent")

FRIENDLY_GEMINI_ERROR = "I'm having trouble understanding that right now. Please try again."
FRIENDLY_DB_ERROR = "I couldn't save that reminder right now. Please try again."

GEMINI_MODEL_FALLBACKS = (
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
)


@dataclass
class AgentResult:
    text: str
    confirmation: dict[str, Any] | None = None
    tool_events: list[dict[str, Any]] = field(default_factory=list)


def _import_adk():
    try:
        from google.adk import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        return Agent, Runner, InMemorySessionService, types
    except ImportError:
        try:
            from google.adk.agents import Agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            return Agent, Runner, InMemorySessionService, types
        except ImportError:
            return None


class PaviAgent:
    def __init__(self, db: AsyncSession, user: User):
        self.db = db
        self.user = user
        self.settings = get_settings()

    async def reply(self, message: str, history: list[tuple[str, str]]) -> AgentResult:
        token_db = pavi_db.set(self.db)
        token_user = pavi_user.set(self.user)
        try:
            use_adk = self.settings.pavi_agent_mode == "adk" and bool(self.settings.resolved_gemini_api_key)
            if use_adk and _import_adk():
                try:
                    return await self._run_adk(message, history)
                except Exception:
                    logger.exception("pavi_adk_failed")
                    logger.warning("pavi_adk_falling_back_to_mock")
                    return await self._run_mock(message, history)
            return await self._run_mock(message, history)
        finally:
            pavi_db.reset(token_db)
            pavi_user.reset(token_user)

    async def _run_adk(self, message: str, history: list[tuple[str, str]]) -> AgentResult:
        models = [self.settings.gemini_model, *GEMINI_MODEL_FALLBACKS]
        seen: set[str] = set()
        last_error: Exception | None = None
        for model in models:
            if not model or model in seen:
                continue
            seen.add(model)
            try:
                return await self._run_adk_with_model(message, history, model)
            except Exception as exc:
                last_error = exc
                logger.warning("pavi_adk_model_failed model=%s err=%s", model, exc)
        if last_error:
            raise last_error
        return AgentResult(text=FRIENDLY_GEMINI_ERROR)

    async def _run_adk_with_model(self, message: str, history: list[tuple[str, str]], model: str) -> AgentResult:
        Agent, Runner, InMemorySessionService, types = _import_adk()
        pref = await PreferenceService(self.db, self.user).get()
        os.environ.setdefault("GOOGLE_API_KEY", self.settings.resolved_gemini_api_key)
        os.environ.setdefault("GEMINI_API_KEY", self.settings.resolved_gemini_api_key)
        history_block = "\n".join(f"{role}: {text}" for role, text in history[- self.settings.pavi_context_messages :])
        instruction = (
            f"{PAVI_INSTRUCTION}\n\n"
            f"User timezone: {pref.timezone} (treat as IST / India unless it is not Asia/Kolkata)\n"
            f"Preferred language: {pref.preferred_language}\n"
            f"Current local time in India: {format_local(now_utc(), pref.timezone)}\n"
            f"Saved phone on file: {'yes' if pref.phone_number else 'no — ask for a +91 mobile if scheduling a call'}\n"
        )
        if history_block:
            instruction += f"\nRecent conversation:\n{history_block}\n"
        agent = Agent(
            name="pavi",
            model=model,
            instruction=instruction,
            description="Pavi is a personal AI assistant for reminders, appointments, and phone call alerts.",
            tools=PAVI_TOOLS,
        )
        session_service = InMemorySessionService()
        app_name = "pavi"
        session_id = f"pavi-{self.user.id}"
        await session_service.create_session(app_name=app_name, user_id=self.user.id, session_id=session_id)
        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        content = types.Content(role="user", parts=[types.Part(text=message)])
        final_text = ""
        events: list[dict[str, Any]] = []
        async for event in runner.run_async(user_id=self.user.id, session_id=session_id, new_message=content):
            if getattr(event, "content", None) and getattr(event.content, "parts", None):
                for part in event.content.parts:
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        events.append({"type": "tool_call", "name": getattr(fc, "name", ""), "args": dict(getattr(fc, "args", {}) or {})})
                    if getattr(part, "function_response", None):
                        fr = part.function_response
                        events.append({"type": "tool_result", "name": getattr(fr, "name", ""), "response": getattr(fr, "response", None)})
                    if getattr(part, "text", None):
                        final_text = part.text
            is_final = getattr(event, "is_final_response", None)
            if callable(is_final) and is_final() and getattr(event, "content", None):
                parts = event.content.parts or []
                texts = [p.text for p in parts if getattr(p, "text", None)]
                if texts:
                    final_text = texts[-1]
        if not (final_text or "").strip():
            final_text = FRIENDLY_GEMINI_ERROR
        return AgentResult(text=final_text.strip(), confirmation=_confirmation_from_events(events), tool_events=events)

    async def _run_mock(self, message: str, history: list[tuple[str, str]]) -> AgentResult:
        from app.agents.tools import (
            cancel_appointment,
            cancel_booking,
            cancel_reminder,
            create_appointment,
            create_reminder,
            get_reminders,
            update_reminder,
        )

        text = message.strip()
        lower = text.lower()
        events: list[dict[str, Any]] = []
        last_assistant = next((t for r, t in reversed(history) if r == "assistant"), "")
        last_user = next((t for r, t in reversed(history) if r == "user"), "")

        if "what would you like me to remind you about" in last_assistant.lower():
            title = text[:1].upper() + text[1:]
            combined = f"{last_user} {text}"
            if not re.search(r"\d|noon|morning|evening|am|pm", combined, re.I):
                return AgentResult(text="Sure. What time tomorrow should I remind you?")
            result = await create_reminder(title=title, reminder_time=combined, phone_call_enabled=True)
            events.append({"type": "tool_result", "name": "create_reminder", "response": result})
            if result.get("success"):
                return AgentResult(
                    text=f"Done. I'll remind you {result.get('when')} to {title.lower()}.",
                    confirmation={"kind": "reminder", "title": title, "when_label": result.get("when") or "", "phone_call_enabled": True},
                    tool_events=events,
                )
            return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)

        if "what time" in last_assistant.lower():
            title = _infer_title(last_user) or last_user
            result = await create_reminder(title=title, reminder_time=text, phone_call_enabled=True)
            events.append({"type": "tool_result", "name": "create_reminder", "response": result})
            if result.get("success"):
                return AgentResult(
                    text=f"Done. I'll remind you {result.get('when')} to {title.lower()}.",
                    confirmation={"kind": "reminder", "title": title, "when_label": result.get("when") or "", "phone_call_enabled": True},
                    tool_events=events,
                )
            return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)

        if re.search(r"\b(what reminders|list reminders|do i have)\b", lower):
            day = "tomorrow" if "tomorrow" in lower else ("today" if "today" in lower else "")
            result = await get_reminders(day)
            events.append({"type": "tool_result", "name": "get_reminders", "response": result})
            if not result.get("success"):
                return AgentResult(text=FRIENDLY_DB_ERROR, tool_events=events)
            items = result.get("reminders") or []
            if not items:
                reply = "You don't have any reminders" + (" tomorrow." if day == "tomorrow" else " right now.")
                return AgentResult(text=reply, tool_events=events)
            lines = [f"{i+1}. {it['title']} at {it['when']}." for i, it in enumerate(items)]
            header = "You have " + ("two reminders tomorrow:" if day == "tomorrow" and len(items) == 2 else f"{len(items)} reminder(s):")
            if day == "tomorrow":
                header = f"You have {len(items)} reminder{'s' if len(items) != 1 else ''} tomorrow:"
            return AgentResult(text=header + "\n\n" + "\n".join(lines), tool_events=events)

        if re.search(r"\b(cancel|remove|delete)\b.{0,40}\b(appointment|booking)\b", lower) or re.search(
            r"\b(appointment|booking)\b.{0,24}\b(cancel|remove|delete)\b", lower
        ):
            if "booking" in lower and "appointment" not in lower:
                result = await cancel_booking()
                events.append({"type": "tool_result", "name": "cancel_booking", "response": result})
                kind = "booking"
            else:
                result = await cancel_appointment()
                events.append({"type": "tool_result", "name": "cancel_appointment", "response": result})
                kind = "appointment"
            if result.get("success"):
                return AgentResult(text=f"Done! I've cancelled that {kind} and the phone reminder.", tool_events=events)
            return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)

        if re.search(r"\b(cancel it|cancel that|delete it|remove it)\b", lower):
            result = await cancel_reminder()
            events.append({"type": "tool_result", "name": "cancel_reminder", "response": result})
            if result.get("success"):
                return AgentResult(text="Done! I've cancelled that reminder.", tool_events=events)
            return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)

        move = re.search(r"\b(move|change|reschedule).{0,40}?(to|at)\s+(.+)$", lower)
        if move or re.search(r"\bmove (the )?(second|first|it)\b", lower):
            time_bit = None
            m2 = re.search(r"\bto\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", lower)
            if m2:
                time_bit = m2.group(1)
            if time_bit:
                result = await update_reminder(reminder_time=time_bit)
                events.append({"type": "tool_result", "name": "update_reminder", "response": result})
                if result.get("success"):
                    return AgentResult(
                        text=f"Done. I've moved {result.get('title', 'that reminder')} to {result.get('when')}.",
                        tool_events=events,
                    )
                return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)

        appt = re.search(
            r"\b(appointment|doctor|dentist|meeting|clinic|hospital)\b",
            lower,
        )
        offset_m = re.search(r"(\d+)\s+(minute|hour)s?\s+before", lower)
        one_hour = bool(re.search(r"one hour before", lower))
        if appt:
            title = "Doctor Appointment" if "doctor" in lower else (
                "Dentist Appointment" if "dentist" in lower else (
                    "Meeting" if "meeting" in lower else "Appointment"
                )
            )
            offset = 60 if one_hour else 0
            if offset_m:
                offset = int(offset_m.group(1)) * (60 if "hour" in offset_m.group(2) else 1)
            result = await create_appointment(
                title=title,
                appointment_time=text,
                reminder_offset_minutes=offset,
                phone_call_enabled=True,
            )
            events.append({"type": "tool_result", "name": "create_appointment", "response": result})
            if not result.get("success"):
                return AgentResult(text=result.get("error") or FRIENDLY_DB_ERROR, tool_events=events)
            call_at = result.get("will_call_at") or result.get("when")
            reply = f"Done! I've added your {title.lower()} for {result.get('when')} IST, and I'll call you then."
            if offset:
                reply = f"Done! I've added your {title.lower()} for {result.get('when')} IST, and I'll call you at {call_at}."
            if result.get("needs_phone"):
                reply += " What's your Indian mobile number so I can call you?"
            return AgentResult(
                text=reply,
                confirmation={
                    "kind": "appointment",
                    "title": title,
                    "when_label": result.get("when") or "",
                    "phone_call_enabled": True,
                    "extra": f"I'll call you at {call_at}" if call_at else None,
                },
                tool_events=events,
            )

        if re.search(r"\b(remind|reminder|call me)\b", lower):
            if re.search(r"\bremind me tomorrow\b", lower) and not re.search(r"\d|noon|morning|evening|night|am|pm", lower):
                return AgentResult(text="What would you like me to remind you about?")
            title = _infer_title(text)
            if not title:
                return AgentResult(text="What would you like me to remind you about?")
            result = await create_reminder(title=title, reminder_time=text, phone_call_enabled=True)
            events.append({"type": "tool_result", "name": "create_reminder", "response": result})
            if not result.get("success"):
                err = result.get("error") or FRIENDLY_DB_ERROR
                if result.get("code") == "UNCLEAR_TIME":
                    return AgentResult(text="Sure. What time should I remind you?")
                return AgentResult(text=err, tool_events=events)
            reply = f"Done! I'll remind you {result.get('when')} to {title[0].lower() + title[1:] if title else 'do that'}."
            if "call" in title.lower():
                reply = f"Done! I'll remind you {result.get('when')} to {title.lower()}."
            return AgentResult(
                text=reply,
                confirmation={
                    "kind": "reminder",
                    "title": title,
                    "when_label": result.get("when") or "",
                    "phone_call_enabled": True,
                },
                tool_events=events,
            )

        return AgentResult(
            text="I can help with reminders, appointments, and bookings. Try: “Remind me tomorrow at 12 PM to call Rahul.”"
        )


def _infer_title(text: str) -> str:
    patterns = [
        r"(?:to|about)\s+(.+)$",
        r"remind me\s+(?:that\s+)?(.+)$",
    ]
    cleaned = re.sub(r"^\s*pavi[,:]?\s*", "", text, flags=re.I).strip()
    for pat in patterns:
        m = re.search(pat, cleaned, re.I)
        if m:
            title = m.group(1).strip().rstrip(".")
            title = re.sub(r"^(tomorrow|today|tonight|at\s+\d.*)\s+", "", title, flags=re.I)
            if title and not re.fullmatch(r"(tomorrow|today|tonight|please)", title, re.I):
                return title[:1].upper() + title[1:]
    if "call" in cleaned.lower():
        m = re.search(r"call\s+([A-Za-z][\w\s]{1,40})", cleaned, re.I)
        if m:
            return f"Call {m.group(1).strip().title()}"
    return ""


def _confirmation_from_events(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("type") != "tool_result":
            continue
        resp = event.get("response") or {}
        if not isinstance(resp, dict) or not resp.get("success"):
            continue
        name = event.get("name") or ""
        if "create_reminder" in name or name == "create_reminder":
            return {
                "kind": "reminder",
                "title": resp.get("title") or "Reminder",
                "when_label": resp.get("when") or "",
                "phone_call_enabled": True,
            }
        if "create_appointment" in name:
            return {
                "kind": "appointment",
                "title": resp.get("title") or "Appointment",
                "when_label": resp.get("when") or "",
                "phone_call_enabled": True,
                "extra": f"Reminder {resp['reminder_when']}" if resp.get("reminder_when") else None,
            }
    return None

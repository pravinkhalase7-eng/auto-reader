from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.database import get_db
from app.main import app
from app.providers.pavi_tts.mock import MockTTSProvider
from app.providers.voice.mock import MockVoiceProvider
from app.services.twilio_service import TwilioVoiceService
from app.utils.datetime import parse_natural_datetime, to_utc, from_utc, format_local
from app.utils.phone import mask_phone, normalize_phone, validate_phone
from app.services.reminder_message import generate_reminder_speech
from app.workers.reminder_tasks import _schedule_retry_or_fail


@pytest.fixture
def now_kolkata():
    return datetime(2026, 8, 13, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_parse_4pm_today_ist(now_kolkata):
    parsed = parse_natural_datetime("create an appointment for 4pm", timezone_name="Asia/Kolkata", now=now_kolkata)
    assert parsed is not None
    assert parsed.local_dt.hour == 16
    assert parsed.local_dt.day == 13


def test_parse_4pm_rolls_to_tomorrow():
    now = datetime(2026, 8, 13, 17, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    parsed = parse_natural_datetime("4pm", timezone_name="Asia/Kolkata", now=now)
    assert parsed is not None
    assert parsed.local_dt.hour == 16
    assert parsed.local_dt.day == 14


def test_parse_tomorrow_noon(now_kolkata):
    parsed = parse_natural_datetime("tomorrow noon", timezone_name="Asia/Kolkata", now=now_kolkata)
    assert parsed is not None
    local = parsed.local_dt
    assert local.day == 14
    assert local.hour == 12


def test_parse_in_two_hours(now_kolkata):
    parsed = parse_natural_datetime("in 2 hours", timezone_name="Asia/Kolkata", now=now_kolkata)
    assert parsed is not None
    assert parsed.local_dt.hour == 12


def test_parse_next_monday(now_kolkata):
    parsed = parse_natural_datetime("next Monday at 9 AM", timezone_name="Asia/Kolkata", now=now_kolkata)
    assert parsed is not None
    assert parsed.local_dt.weekday() == 0
    assert parsed.local_dt.hour == 9


def test_parse_every_day():
    parsed = parse_natural_datetime("every day at 8 AM", timezone_name="Asia/Kolkata")
    assert parsed is not None
    assert parsed.recurrence_rule == "FREQ=DAILY"


def test_timezone_roundtrip(now_kolkata):
    utc = to_utc(now_kolkata)
    local = from_utc(utc, "Asia/Kolkata")
    assert local.hour == 10
    assert "10:00" in format_local(utc, "Asia/Kolkata")


def test_phone_e164_and_mask():
    assert normalize_phone("9876543210") == "+919876543210"
    assert mask_phone("+919876543210") == "+91******3210"
    assert validate_phone("+919876543210") == "+919876543210"
    with pytest.raises(ValueError):
        validate_phone("123")


@pytest.mark.asyncio
async def test_mock_tts():
    audio = await MockTTSProvider().synthesize("Hello, this is Pavi.")
    assert audio.provider == "mock"
    assert audio.audio_bytes.startswith(b"RIFF")


def test_mock_voice_and_twiml():
    result = MockVoiceProvider().make_call(to="+919876543210", twiml_url="http://x/twiml", status_callback_url="http://x/status")
    assert result.status == "completed"
    assert result.call_sid
    xml = TwilioVoiceService().generate_twiml(spoken_text="Hello, this is Pavi.", audio_url=None)
    assert "Hello, this is Pavi." in xml
    assert "<Response>" in xml or "Response>" in xml


def test_reminder_speech_english():
    class R:
        title = "Doctor Appointment"
        language = "en"
        tzname = "Asia/Kolkata"
        reminder_time_utc = datetime(2026, 8, 14, 4, 30, tzinfo=timezone.utc)

        @property
        def timezone(self) -> str:
            return self.tzname

    text = generate_reminder_speech(R())  # type: ignore[arg-type]
    assert "Pavi" in text
    assert "Doctor Appointment" in text


def test_retry_then_fail():
    class R:
        retry_count = 0
        status = "processing"
        last_error = None
        reminder_time_utc = datetime.now(timezone.utc)
        next_retry_at = None
        id = "x"

    reminder = R()
    _schedule_retry_or_fail(None, reminder, "busy")  # type: ignore[arg-type]
    assert reminder.status == "scheduled"
    reminder.retry_count = 2
    _schedule_retry_or_fail(None, reminder, "busy")  # type: ignore[arg-type]
    assert reminder.status == "failed"


@pytest.fixture
async def pavi_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PAVI_AGENT_MODE", "mock")
    monkeypatch.setenv("VOICE_CALL_MODE", "mock")
    monkeypatch.setenv("PAVI_TTS_PROVIDER", "mock")
    from app.core.config import get_settings

    get_settings.cache_clear()
    db_path = tmp_path / "pavi.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    await engine.dispose()


async def _auth(client: AsyncClient) -> dict[str, str]:
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "pavi@example.com", "password": "secret12", "full_name": "Pavi User", "class_level": 4},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_update_cancel_reminder(pavi_client):
    headers = await _auth(pavi_client)
    await pavi_client.patch(
        "/api/v1/pavi/preferences",
        headers=headers,
        json={"phone_number": "+919876543210", "timezone": "Asia/Kolkata"},
    )
    created = await pavi_client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Call Rahul", "reminder_time": "tomorrow at 12 PM", "phone_call_enabled": True},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["title"] == "Call Rahul"
    assert body["status"] == "scheduled"
    rid = body["id"]

    dup = await pavi_client.post(
        "/api/v1/reminders",
        headers=headers,
        json={"title": "Call Rahul", "reminder_time": "tomorrow at 12 PM", "phone_call_enabled": True},
    )
    assert dup.json()["id"] == rid

    updated = await pavi_client.patch(f"/api/v1/reminders/{rid}", headers=headers, json={"reminder_time": "2 PM"})
    assert updated.status_code == 200
    cancelled = await pavi_client.delete(f"/api/v1/reminders/{rid}", headers=headers)
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_appointment_with_offset(pavi_client):
    headers = await _auth(pavi_client)
    res = await pavi_client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "title": "Doctor Appointment",
            "appointment_time": "tomorrow at 10 AM",
            "reminder_offset_minutes": 60,
            "phone_call_enabled": True,
        },
    )
    assert res.status_code == 200, res.text
    reminders = await pavi_client.get("/api/v1/reminders", headers=headers)
    assert reminders.status_code == 200
    assert len(reminders.json()) >= 1


@pytest.mark.asyncio
async def test_pavi_chat_create_and_list(pavi_client):
    headers = await _auth(pavi_client)
    chat = await pavi_client.post(
        "/api/v1/pavi/chat",
        headers=headers,
        json={"message": "Pavi, remind me tomorrow at 12 PM to call Rahul."},
    )
    assert chat.status_code == 200, chat.text
    assert "rahul" in chat.json()["message"].lower()
    listed = await pavi_client.post(
        "/api/v1/pavi/chat",
        headers=headers,
        json={"message": "What reminders do I have tomorrow?", "conversation_id": chat.json()["conversation_id"]},
    )
    assert listed.status_code == 200
    assert "Rahul" in listed.json()["message"] or "reminder" in listed.json()["message"].lower()


@pytest.mark.asyncio
async def test_pavi_chat_appointment_calls_at_time(pavi_client):
    headers = await _auth(pavi_client)
    await pavi_client.patch(
        "/api/v1/pavi/preferences",
        headers=headers,
        json={"phone_number": "+917219584184", "timezone": "Asia/Kolkata"},
    )
    chat = await pavi_client.post(
        "/api/v1/pavi/chat",
        headers=headers,
        json={"message": "Create an appointment for 4pm"},
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert "4:00" in body["message"] or "4:00" in (body.get("confirmation") or {}).get("when_label", "")
    assert "call" in body["message"].lower()
    appts = await pavi_client.get("/api/v1/appointments", headers=headers)
    assert appts.status_code == 200
    assert len(appts.json()) >= 1
    reminders = await pavi_client.get("/api/v1/reminders", headers=headers)
    assert reminders.status_code == 200
    assert reminders.json()[0]["phone_call_enabled"] is True


@pytest.mark.asyncio
async def test_voice_transcript_and_twilio_webhook(pavi_client):
    headers = await _auth(pavi_client)
    res = await pavi_client.post(
        "/api/v1/pavi/voice/transcript",
        headers=headers,
        json={"message": "Remind me tomorrow at 9 AM to drink water", "transcript": "Remind me tomorrow at 9 AM to drink water"},
    )
    assert res.status_code == 200, res.text
    twiml = await pavi_client.post("/api/v1/voice/twilio/twiml/missing-id")
    assert twiml.status_code == 200
    assert "Pavi" in twiml.text
    status = await pavi_client.post("/api/v1/voice/twilio/status", data={"CallSid": "CA_TEST", "CallStatus": "completed"})
    assert status.status_code == 200


def test_resolved_twilio_webhook_from_public_api():
    from app.core.config import Settings

    s = Settings.model_construct(
        twilio_webhook_base_url="",
        next_public_api_url="http://187.127.138.86:8000/api/v1",
    )
    assert s.resolved_twilio_webhook_base == "http://187.127.138.86:8000"

    local = Settings.model_construct(twilio_webhook_base_url="", next_public_api_url="http://localhost:8000/api/v1")
    assert local.resolved_twilio_webhook_base == "http://localhost:8000"

    explicit = Settings.model_construct(
        twilio_webhook_base_url="http://187.127.138.86:8000",
        next_public_api_url="http://localhost:8000/api/v1",
    )
    assert explicit.resolved_twilio_webhook_base == "http://187.127.138.86:8000"

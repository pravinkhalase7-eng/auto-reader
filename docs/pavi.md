# Pavi — Personal AI Assistant

Pavi is a voice + chat assistant inside AI Teacher. It creates reminders and appointments, then (optionally) places a phone call when they are due.

Open it at **[/pavi](http://localhost:3000/pavi)** after signing in.

---

## 1. Files created

### Backend

- `apps/api/app/models/pavi.py`
- `apps/api/app/schemas/pavi.py`, `reminder.py`, `appointment.py`, `voice.py`
- `apps/api/app/repositories/`
- `apps/api/app/services/reminder_service.py`, `appointment_service.py`, `preference_service.py`, `pavi_service.py`, `tts_service.py`, `twilio_service.py`, `reminder_message.py`, `speech_service.py`
- `apps/api/app/agents/` (`pavi_agent.py`, `tools.py`, `prompts.py`)
- `apps/api/app/providers/pavi_tts/`, `providers/voice/`
- `apps/api/app/workers/celery_app.py`, `reminder_tasks.py`, `beat_tasks.py`
- `apps/api/app/api/v1/pavi.py`, `reminders.py`, `appointments.py`, `voice.py`
- `apps/api/app/utils/datetime.py`, `phone.py`
- `apps/api/alembic/`
- `apps/api/tests/test_pavi.py`

### Frontend

- `apps/web/src/components/pavi/*`
- `apps/web/src/app/pavi/page.tsx`
- `apps/web/src/app/pavi/dashboard/page.tsx`
- `apps/web/src/app/pavi/reminders/new/page.tsx`
- `apps/web/src/lib/pavi-api.ts`, `speech-providers.ts`, `pavi-format.ts`
- `apps/web/src/types/pavi.ts`

## 2. Files modified

- `apps/api/app/core/config.py`, `models/__init__.py`, `api/v1/__init__.py`, `providers/factory.py`, `Dockerfile`, `requirements.txt`
- `apps/web/src/components/app-shell.tsx`, `app/globals.css`, `app/dashboard/page.tsx`, `app/settings/page.tsx`
- `docker-compose.yml`, `Jenkinsfile`, `.env.example`, `aiteacher.env.example`, `README.md`

## 3. Environment variables

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `GEMINI_API_KEY` or `GOOGLE_AI_API_KEY` | Gemini / ADK | empty |
| `GEMINI_MODEL` | Pavi LLM | `gemini-flash-latest` |
| `PAVI_AGENT_MODE` | `adk` or `mock` | `adk` (falls back to mock without a key) |
| `PAVI_TTS_PROVIDER` | `gemini` or `mock` | `mock` |
| `GEMINI_TTS_VOICE` | Gemini voice | `Kore` |
| `VOICE_CALL_MODE` | `mock` or `live` | `mock` |
| `TWILIO_ACCOUNT_SID` / `AUTH_TOKEN` / `PHONE_NUMBER` | Outbound calls | empty |
| `TWILIO_WEBHOOK_BASE_URL` | Public API origin Twilio can reach | empty |
| `CELERY_BROKER_URL` | Redis broker | `redis://localhost:6379/0` |
| `DEFAULT_TIMEZONE` | Fallback tz | `Asia/Kolkata` |
| `ENABLE_DEV_TOOLS` | Allows `POST /api/v1/dev/test-call` | `false` in prod |
| `ENVIRONMENT` | `development` / `production` | `development` |

Lesson-reader `TTS_PROVIDER=browser` is unchanged. Pavi uses `PAVI_TTS_PROVIDER`.

## 4. Database migration

Pavi tables are created on API startup (`create_all`), same as lessons.

Optional Alembic:

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
```

## 5. Docker

```bash
docker compose up --build
```

Services: `frontend` (`web`), `api`, `postgres`, `redis`, `celery-worker`, `celery-beat`.

## 6. Local development

```bash
# Redis (required for Celery)
docker run -d --name pavi-redis -p 6379:6379 redis:7-alpine

# API
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env
uvicorn app.main:app --reload --port 8000

# Celery (second and third terminals)
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info

# Web
cd apps/web
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm install
npm run dev
```

Sign in, then open http://localhost:3000/pavi

Save your E.164 number under **Settings** (e.g. `+9198XXXXXXXX`).

## 7. Google Gemini

1. Create an API key in Google AI Studio.
2. Set `GEMINI_API_KEY` (or keep using `GOOGLE_AI_API_KEY`).
3. Optional: `GEMINI_MODEL=gemini-flash-latest`.

## 8. Google ADK

Pavi uses the official [`google-adk`](https://github.com/google/adk-python) package.

- Tools are Python functions with type hints; ADK wraps them as `FunctionTool`.
- The agent is created in `app/agents/pavi_agent.py` with `from google.adk import Agent` (ADK 1.x `google.adk.agents.Agent` is also accepted).
- Set `PAVI_AGENT_MODE=adk` and a Gemini key. Without a key, Pavi uses the built-in mock agent so CRUD still works.

## 9. Twilio

1. Buy/verify a Twilio number.
2. Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
3. Expose the API with HTTPS (ngrok or your VPS) and set `TWILIO_WEBHOOK_BASE_URL=https://your-host`.
4. Set `VOICE_CALL_MODE=live`.
5. Keep `VOICE_CALL_MODE=mock` until you are ready — mock logs `[MOCK CALL] Calling +91******XXXX` and never dials.

Twilio webhooks:

- `POST /api/v1/voice/twilio/twiml/{reminder_id}`
- `POST /api/v1/voice/twilio/status`

Signatures are validated when `VOICE_CALL_MODE=live`.

## 10. Test a reminder

1. Open Pavi and say or type: `Pavi, remind me tomorrow at 12 PM to call Rahul.`
2. Confirm it appears under Upcoming.
3. Or create one due in two minutes: `Remind me in 2 minutes to stretch.`
4. Watch Celery logs for `[REMINDER] id=... status=processing`.

## 11. Test a phone call

With `ENABLE_DEV_TOOLS=true` and `ENVIRONMENT=development`:

```bash
TOKEN=...
curl -X POST http://localhost:8000/api/v1/dev/test-call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"+91XXXXXXXXXX","message":"Hello, this is a test call from Pavi."}'
```

`VOICE_CALL_MODE=mock` simulates queued → ringing → completed.  
`VOICE_CALL_MODE=live` places a real Twilio call.

## 12. Known limitations

- Browser Web Speech API is Chrome/Edge/Safari; Firefox support is limited.
- Microphone audio stays in the browser. Only the transcript is sent to the API.
- Real-time two-way phone conversations (Twilio Media Streams) are not in this MVP.
- Hindi/Marathi replies are designed in; English is the default until the user preference is `hi`/`mr`.
- Celery Beat scans every ~20s; sub-minute precision is not guaranteed.
- Public Twilio webhooks need a reachable HTTPS URL.

## 13. Production checklist

- [ ] Strong `SECRET_KEY`
- [ ] Postgres `DATABASE_URL`
- [ ] Redis + celery-worker + celery-beat running
- [ ] `GEMINI_API_KEY` set; `PAVI_AGENT_MODE=adk`
- [ ] `PAVI_TTS_PROVIDER=gemini` once TTS quality is verified
- [ ] Twilio credentials + `TWILIO_WEBHOOK_BASE_URL` over HTTPS
- [ ] `VOICE_CALL_MODE=live` only after a successful test call
- [ ] `ENABLE_DEV_TOOLS=false` and `ENVIRONMENT=production`
- [ ] User phone numbers stored in E.164; never logged in full
- [ ] CORS limited to the real web origin

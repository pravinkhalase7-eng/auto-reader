# AI Teacher

A production-oriented **AI Teacher** web app for students: upload textbook pages, understand them, listen with word-level highlighting, take quizzes in the source language, and track progress.

> Upload → Understand → Read / Listen → Highlight → Quiz → Feedback → Progress

This is **not** an OCR utility. The product voice is a friendly teacher.

---

## Quick start (local)

### Prerequisites

- Node.js 20+
- Python 3.11+
- (Optional) Docker + Docker Compose for full stack with Postgres

### 1. Backend

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../../.env.example .env  # optional
uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Demo user (seeded on startup):

- Email: `demo@example.com`
- Password: `demo1234`

### 2. Frontend

```bash
cd apps/web
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 3. Docker Compose

```bash
docker compose up --build
```

- Web: http://localhost:3000  
- API: http://localhost:8000  
- Postgres: localhost:5432  
- Redis: localhost:6379 (architecture-ready; MVP queue is in-process)

---

## Architecture

See:

- [docs/architecture.md](docs/architecture.md)
- [docs/database-design.md](docs/database-design.md)
- [docs/api-design.md](docs/api-design.md)
- [docs/implementation-plan.md](docs/implementation-plan.md)

```
apps/web (Next.js)  ──REST──►  apps/api (FastAPI)
                                  ├── providers/ (AI, OCR, TTS, Storage)
                                  ├── services/ + workers/
                                  └── PostgreSQL / SQLite + local/S3 files
```

---

## Providers

| Concern | Env var | Defaults | Notes |
|---------|---------|----------|-------|
| AI | `AI_PROVIDER` | `local` | `gemini`, `openai` when keys set |
| OCR | `OCR_PROVIDER` | `local` | Uses pytesseract if installed; else demo text / Vision APIs |
| TTS | `TTS_PROVIDER` | `browser` | Browser Speech Synthesis + server word timings |
| Storage | `STORAGE_PROVIDER` | `local` | `s3` adapter stub for production |

Never hard-code API keys. Use `.env`.

### Word synchronization

1. Content is stored as Section → Paragraph → Sentence → Word with stable UUIDs.
2. TTS service returns (or estimates) `start_ms` / `end_ms` per word.
3. Frontend `ReadingPlayer` uses `requestAnimationFrame` + timing map to set `activeWordId` in Zustand (avoids re-rendering the whole lesson tree unnecessarily; words are memoized).
4. Fallback estimator: `app/utils/word_timing.py` (isolated, replaceable).

---

## Core user flows

1. **Register / login**
2. **Upload** one or more page images → processing steps with teacher-friendly messages
3. **Lesson hub** → Read / Quiz / View original / Edit text
4. **Reader** — Listen, Read, or Listen+Read with play/pause/speed/paragraph nav
5. **Quiz** — mixed question types in lesson language → semantic short-answer eval
6. **Results + Dashboard** — score, topics, streak, continue learning

Demo lessons (EN story, HI story, MR story, EN poem) are seeded automatically.

---

## Example API requests

```bash
# Register
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@school.com","password":"secret12","full_name":"Asha","class_level":3}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo1234"}' | jq -r .access_token)

# List lessons
curl -s http://localhost:8000/api/v1/lessons -H "Authorization: Bearer $TOKEN"

# Lesson content
curl -s http://localhost:8000/api/v1/lessons/<LESSON_ID>/content -H "Authorization: Bearer $TOKEN"
```

---

## Testing

```bash
cd apps/api
source .venv/bin/activate
pytest -q
```

Critical coverage: auth, segmentation, language detection, word timing fallback, quiz generation/evaluation.

---

## Production deployment notes

See **[docs/deploy.md](docs/deploy.md)** for the Jenkins + VPS flow (same pattern as Option-Trading).

Quick summary:

1. Create Jenkins credential Secret file ID: `aiteacher-env-file` (from `aiteacher.env.example`)
2. Pipeline uses root `Jenkinsfile` → builds API/Web images → `docker compose up -d`
3. UI on port **3000**, API on **8000**

1. Set strong `SECRET_KEY`, disable default demo seed (`SEED_ON_STARTUP=false`) for real production if desired.
2. Use managed Postgres or the compose `postgres` service (`DATABASE_URL=postgresql+asyncpg://...@postgres:5432/...`).
3. Set `STORAGE_PROVIDER=s3` and wire boto3 + signed URLs when ready.
4. Set `AI_PROVIDER=gemini` or `openai` with keys; prefer cloud OCR/TTS for quality.
5. Put API behind HTTPS; configure `CORS_ORIGINS` to your web origin only.
6. Replace in-process `TaskQueue` with Celery/SQS/Cloud Tasks when load requires it.
7. Build web with `NEXT_PUBLIC_API_URL` pointing at the public API (Jenkins does this each deploy).

---

## Repository layout

```
apps/web          Next.js App Router frontend
apps/api          FastAPI backend
docs/             Architecture & design
packages/         Reserved for shared types/UI
docker-compose.yml
.env.example
```

---

## License

Educational project — adapt freely for your school or product.

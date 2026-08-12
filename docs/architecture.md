# AI Teacher — Architecture

## Product Vision

AI Teacher is a digital learning companion for students. A student uploads textbook pages; the system understands the content, narrates it with word-level highlighting, quizzes the student in the source language, and tracks progress.

**Core loop:** Upload → Understand → Read/Listen → Highlight → Quiz → Feedback → Progress

This is **not** an OCR utility. Every UX message should feel like an encouraging AI teacher.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        apps/web (Next.js)                        │
│  Landing · Auth · Dashboard · Upload · Reader · Quiz · Progress │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST / JSON
┌────────────────────────────▼────────────────────────────────────┐
│                      apps/api (FastAPI)                          │
│  api/ → services/ → repositories/ → models/                      │
│  providers/ (AI, OCR, TTS, Storage) · workers/ (background jobs) │
└──────┬──────────────┬──────────────┬──────────────┬─────────────┘
       │              │              │              │
   PostgreSQL      Local/S3        Redis*       AI Providers
   (primary DB)   (media files)   (optional)   (Gemini/OpenAI/Google)
```

\* Redis is architecture-ready; MVP uses an in-process `TaskQueue`.

---

## Monorepo Layout

```
ai-teacher/
├── apps/
│   ├── web/                 # Next.js App Router frontend
│   └── api/                 # FastAPI backend
├── packages/
│   └── shared-types/        # Shared TypeScript types / OpenAPI client hints
├── docs/                    # Architecture & design docs
├── docker/                  # Extra Docker assets
├── scripts/                 # Seed, migrate, bootstrap helpers
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Backend Layering

| Layer | Responsibility |
|-------|----------------|
| `api/` | HTTP routes, dependency injection, auth guards |
| `schemas/` | Pydantic request/response models |
| `services/` | Business logic (lessons, quiz, progress, processing) |
| `repositories/` | SQLAlchemy data access |
| `models/` | ORM entities |
| `providers/` | Pluggable AI / OCR / TTS / Storage adapters |
| `prompts/` | Centralized LLM prompt templates |
| `workers/` | Background job runners |
| `core/` | Config, security, logging, exceptions |
| `utils/` | Image helpers, language metadata, timing |

**Rule:** Route handlers stay thin. No AI prompts or provider SDK calls inside routes.

---

## Provider Abstraction

Providers are selected via environment variables:

```
AI_PROVIDER=gemini|openai|local
OCR_PROVIDER=google|openai|local
TTS_PROVIDER=google|openai|browser|local
STORAGE_PROVIDER=local|s3
```

Interfaces:

- `AIProvider` — content structuring, quiz generation, answer evaluation
- `OCRProvider` — image → raw text
- `TTSProvider` — text → audio + optional word timings
- `StorageProvider` — store/retrieve blobs; signed URLs for private assets
- `TaskQueue` — enqueue long-running jobs (local → Celery/SQS later)

Adapters implement these interfaces. Switching providers never requires changing service code.

---

## Processing Pipeline

```
Upload pages
    → validate & store originals
    → enqueue AIProcessingJob
        → preprocess images (deskew, contrast; keep originals)
        → OCR each page
        → merge pages in order
        → AI content processor (structure, language, type)
        → segment sections / paragraphs / sentences / words
        → persist Learning Content Object
        → (optional) generate TTS + word timings
        → (optional) generate quiz
    → frontend polls job status with friendly teacher messages
```

Long work never blocks the upload response.

---

## Content Model (Learning Content Object)

Stable UUIDs for Document → Section → Paragraph → Sentence → Word enable synchronized highlighting without re-parsing HTML.

Word timings come from TTS word boundaries when available; otherwise a fallback estimator (`FallbackWordTimer`) based on word length and speech rate. Fallback is isolated and replaceable.

---

## Frontend Architecture

- **Next.js App Router** + TypeScript + Tailwind + shadcn/ui
- **TanStack Query** for server state
- **Zustand** for reader player state (active word, mode, speed) — avoids full-tree re-renders
- Word highlighter uses `data-word-id` + `requestAnimationFrame` sync against audio `currentTime`
- Paragraph-level rendering for long chapters; architecture ready for virtualization

### Routes

| Route | Purpose |
|-------|---------|
| `/` | Landing |
| `/login`, `/register` | Auth |
| `/dashboard` | Student home |
| `/upload` | Multi-page upload |
| `/lessons` | Lesson library |
| `/lessons/[id]` | Lesson hub |
| `/lessons/[id]/read` | Reader player |
| `/lessons/[id]/quiz` | Quiz |
| `/lessons/[id]/result` | Results |
| `/profile`, `/settings` | Account |

---

## Multilingual Design

- **UI language** ≠ **lesson language**
- Lesson language drives TTS voice, quiz text, feedback
- Language metadata: `{ code, name, native_name, tts_code }`
- Day-one support: `en`, `hi`, `mr` (+ extensible to other Indian languages)

---

## Auth & Roles

- JWT email/password for MVP
- Roles: `STUDENT`, `PARENT`, `TEACHER`, `ADMIN` (MVP focuses on STUDENT)
- Extensible for OAuth (Google/Apple) and parent/teacher dashboards

---

## Security

- File type + size validation
- AuthZ on every lesson/quiz resource
- Secrets only via env
- CORS from configured origins
- Rate-limit abstraction (noop or simple in-memory for MVP)
- Never treat OCR/AI text as executable

---

## Observability

Structured JSON logs with `request_id`, `user_id`, `lesson_id`, providers, duration, error type. Never log API keys, passwords, or sensitive student PII.

---

## Future Extensions (architecture-ready, not built now)

Ask AI Teacher, explain word/paragraph, pronunciation practice, parent/teacher dashboards, adaptive quizzes, flashcards, fluency scoring.

---

## Design Principles

1. Teacher personality in every student-facing string
2. Providers isolated behind interfaces
3. Prompts centralized
4. Background jobs for expensive work
5. Stable content IDs for highlighting
6. Simple, maintainable code over premature infrastructure

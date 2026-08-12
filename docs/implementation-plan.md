# AI Teacher — Implementation Plan

## Strategy

Ship a **functional MVP** end-to-end: upload → process → read with highlighting → quiz → results → dashboard. Prefer working local/mock providers so the app runs without paid API keys, while real Gemini/OpenAI/Google adapters are wired and selectable via env.

---

## Phase 1 — Foundation ✅ target first

- [x] Docs (architecture, DB, API, plan)
- Monorepo: `apps/web`, `apps/api`
- FastAPI app skeleton + config + logging + JWT auth
- SQLAlchemy models + Alembic-ready migrations (or `create_all` for MVP)
- Next.js App Router + Tailwind + core UI components
- Landing, login, register, dashboard shell
- Docker Compose: web, api, postgres
- `.env.example` + README skeleton

## Phase 2 — Upload + Understanding

- Upload UI (drag/drop, multi-page, camera capture attr)
- Storage provider (local)
- Image validation + preprocessing service
- OCR provider interface + local/heuristic + optional Google/OpenAI
- Content processor + language detection + classification
- Segmentation into section/paragraph/sentence/word with stable UUIDs
- Background `TaskQueue` (asyncio local)
- Processing screen with teacher-friendly steps
- Job polling API

## Phase 3 — Reader + TTS + Highlighting

- Lesson content API
- Reader UI (Listen / Read / Listen+Read)
- TTS provider (browser Web Speech fallback + server stub with timings)
- `FallbackWordTimer` for estimated boundaries
- Zustand player store + rAF word sync
- Paragraph navigation, speed, volume, progress
- View original page modal
- Edit lesson text → re-segment

## Phase 4 — Quiz

- Quiz generation prompts + AI provider (local deterministic + LLM adapters)
- Quiz UI (MCQ, T/F, fill, short)
- Semantic answer evaluation (local fuzzy + LLM)
- Result page with score, topics, CTAs

## Phase 5 — Dashboard & Progress

- Learning progress writes on read/quiz complete
- Dashboard stats, streak, subjects, continue learning
- Lesson library cards

## Phase 6 — Polish

- Seed demo lessons (EN story, HI story, MR story, EN poem)
- Animations (Framer Motion), responsive, a11y
- Tests for critical paths (auth, segmentation, timing, quiz eval)
- Full README + deployment notes

---

## Provider MVP Matrix

| Concern | Default (dev) | Production-ready adapter |
|---------|---------------|--------------------------|
| AI | `local` (rules + templates) | `gemini` / `openai` |
| OCR | `local` (optional pytesseract if installed; else demo/mock from filename) | `google` / `openai` vision |
| TTS | `browser` (Web Speech API) + estimated timings | `google` / `openai` |
| Storage | `local` | `s3` |
| Queue | in-process asyncio | Celery / SQS later |

Local providers ensure the product is demoable offline. When API keys are present, set `AI_PROVIDER=gemini` etc.

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| No OCR API key | Local OCR or paste/demo text path; seed lessons |
| No word timestamps | Isolated fallback timer |
| Long chapters | Paragraph-scoped highlight updates; avoid full re-render |
| Over-scoping | Ship core loop first; stub future features |

---

## Definition of Done (MVP)

1. User can register/login
2. User can upload image(s) and see processing steps
3. Lesson content displays structured text
4. Play narrates with active word highlight + auto-scroll
5. Quiz generates in lesson language (local or AI)
6. Answers evaluated with friendly feedback
7. Dashboard shows recent lessons and scores
8. Docker Compose brings stack up
9. Docs explain architecture and setup

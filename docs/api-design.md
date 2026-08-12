# AI Teacher — API Design

Base URL: `/api/v1`  
Auth: `Authorization: Bearer <JWT>` unless noted  
OpenAPI: served at `/docs` by FastAPI

Friendly error body:

```json
{
  "detail": "I couldn't read this page clearly. Let's try another photo.",
  "code": "OCR_FAILED",
  "request_id": "..."
}
```

---

## Auth

### POST `/auth/register`
```json
{ "email": "...", "password": "...", "full_name": "...", "class_level": 3 }
```
→ `{ user, access_token }`

### POST `/auth/login`
```json
{ "email": "...", "password": "..." }
```
→ `{ user, access_token }`

### GET `/auth/me`
→ current user + student profile

---

## Lessons

### POST `/lessons/upload`
`multipart/form-data`
- `files`: one or more images (ordered)
- `class_level` (optional)
- `subject` (optional)

→ `{ lesson_id, job_id, status, message: "I'm reading your page..." }`

### GET `/lessons`
Query: `status`, `language`, `subject`, `page`, `limit`  
→ paginated lesson cards

### GET `/lessons/{id}`
→ lesson metadata + pages summary + progress

### GET `/lessons/{id}/content`
→ structured Learning Content Object (sections → … → words)

### POST `/lessons/{id}/process`
Re-run / continue processing pipeline  
→ `{ job_id }`

### GET `/lessons/{id}/jobs/{job_id}`
→ `{ status, current_step, progress_percent, message }`

### PATCH `/lessons/{id}/text`
```json
{ "edited_text": "..." }
```
Regenerates segmentation (and optionally TTS/quiz). Keeps `original_text`.

### GET `/lessons/{id}/pages/{page_id}/image`
Redirect or signed URL to original/processed image

---

## Audio / TTS

### POST `/lessons/{id}/generate-audio`
```json
{ "speed": "slow" | "normal" | "very_slow", "voice": "optional" }
```
→ `{ job_id }` or `{ audio_asset }`

### GET `/lessons/{id}/audio`
→ audio metadata + word timings list

### GET `/audio/{asset_id}/file`
Stream or signed URL

---

## Quiz

### POST `/lessons/{id}/generate-quiz`
```json
{ "difficulty": "easy" | "medium" | "hard", "class_level": 3, "count": 10 }
```
→ `{ quiz_id, job_id }`

### GET `/lessons/{id}/quiz`
→ quiz + questions (options without revealing correctness until attempt submit for MCQ UX — MVP may include `is_correct` only in evaluation response)

### POST `/quizzes/{id}/attempt`
```json
{
  "answers": [
    { "question_id": "...", "selected_option_id": "..." },
    { "question_id": "...", "text_answer": "..." }
  ]
}
```
→ attempt result with per-answer feedback + summary

### GET `/quizzes/attempts/{attempt_id}`
→ stored result

---

## Progress & Dashboard

### GET `/dashboard`
```json
{
  "greeting": "Great to see you again!",
  "streak": 5,
  "average_score": 82,
  "reading_time_minutes": 120,
  "quiz_accuracy": 0.8,
  "recent_lessons": [...],
  "continue_learning": [...],
  "subjects": [...]
}
```

### GET `/progress`
→ detailed progress rows

---

## Demo / Health

### GET `/health`
→ `{ status: "ok" }`

### POST `/demo/seed` (dev only)
Seed demo lessons

---

## Notes

- All IDs are UUIDs
- Upload max size & MIME validated server-side
- Processing is async; clients poll job endpoints
- Teacher personality strings live in service layer / i18n maps, not raw provider errors

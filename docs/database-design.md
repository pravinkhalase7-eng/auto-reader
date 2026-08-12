# AI Teacher — Database Design

## Conventions

- All primary keys are UUID (`uuid4`)
- Soft-delete via `deleted_at` where useful (lessons)
- Timestamps: `created_at`, `updated_at` (timezone-aware UTC)
- Status enums stored as strings for readability
- PostgreSQL via SQLAlchemy 2.x async

---

## Entity Relationship Overview

```
User 1──1 StudentProfile
User 1──* Lesson
Lesson 1──* LessonPage
Lesson 1──* LessonSection
LessonSection 1──* LessonParagraph
LessonParagraph 1──* LessonSentence
LessonSentence 1──* LessonWord
Lesson 1──* AudioAsset
AudioAsset 1──* TTSWordTiming
Lesson 1──* Quiz
Quiz 1──* Question
Question 1──* QuestionOption
Quiz 1──* QuizAttempt
QuizAttempt 1──* Answer
User 1──* LearningProgress
Lesson 1──* AIProcessingJob
```

---

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| email | VARCHAR unique | |
| hashed_password | VARCHAR | |
| full_name | VARCHAR | |
| role | ENUM | STUDENT, PARENT, TEACHER, ADMIN |
| ui_language | VARCHAR(8) | default `en` |
| is_active | BOOLEAN | |
| created_at / updated_at | TIMESTAMPTZ | |

### student_profiles
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users | unique |
| class_level | INT | 1–10 |
| preferred_subjects | JSONB | |
| learning_streak | INT | consecutive days |
| last_study_date | DATE | |
| total_reading_seconds | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### lessons
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | owner |
| title | VARCHAR | |
| language | VARCHAR(8) | en, hi, mr, … |
| content_type | VARCHAR | story, poem, lesson, paragraph, worksheet, qa, other |
| subject | VARCHAR | nullable |
| class_level | INT | nullable |
| summary | TEXT | |
| original_text | TEXT | raw OCR merge |
| edited_text | TEXT | nullable; corrections |
| status | VARCHAR | draft, processing, ready, failed |
| progress_percent | FLOAT | 0–100 |
| last_score | FLOAT | nullable |
| last_studied_at | TIMESTAMPTZ | |
| page_count | INT | |
| word_count | INT | |
| error_message | TEXT | friendly |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | |

### lesson_pages
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lesson_id | UUID FK | |
| page_number | INT | 1-based order |
| original_storage_key | VARCHAR | |
| processed_storage_key | VARCHAR | nullable |
| ocr_raw_text | TEXT | |
| width / height | INT | nullable |
| created_at / updated_at | TIMESTAMPTZ | |

### lesson_sections
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lesson_id | UUID FK | |
| heading | VARCHAR | nullable |
| position | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### lesson_paragraphs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| section_id | UUID FK | |
| text | TEXT | |
| position | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### lesson_sentences
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| paragraph_id | UUID FK | |
| text | TEXT | |
| position | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### lesson_words
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| sentence_id | UUID FK | |
| text | VARCHAR | |
| index | INT | global or sentence-local index |
| position | INT | within sentence |
| created_at / updated_at | TIMESTAMPTZ | |

### audio_assets
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lesson_id | UUID FK | |
| storage_key | VARCHAR | |
| language | VARCHAR | |
| voice | VARCHAR | |
| speed | FLOAT | 0.7 / 1.0 / 1.2 mapped to slow tiers |
| duration_ms | INT | |
| provider | VARCHAR | |
| created_at / updated_at | TIMESTAMPTZ | |

### tts_word_timings
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audio_asset_id | UUID FK | |
| word_id | UUID FK → lesson_words | |
| start_ms | INT | |
| end_ms | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### quizzes
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lesson_id | UUID FK | |
| difficulty | VARCHAR | easy, medium, hard |
| class_level | INT | |
| language | VARCHAR | |
| question_count | INT | |
| status | VARCHAR | generating, ready, failed |
| created_at / updated_at | TIMESTAMPTZ | |

### questions
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| quiz_id | UUID FK | |
| question_type | VARCHAR | mcq, true_false, fill_blank, short_answer, vocabulary, sequence |
| prompt | TEXT | |
| explanation | TEXT | |
| expected_answer | TEXT | for short/fill |
| position | INT | |
| points | FLOAT | default 1 |
| created_at / updated_at | TIMESTAMPTZ | |

### question_options
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| question_id | UUID FK | |
| label | VARCHAR | A, B, C, D |
| text | TEXT | |
| is_correct | BOOLEAN | |
| position | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### quiz_attempts
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| quiz_id | UUID FK | |
| user_id | UUID FK | |
| score | FLOAT | |
| max_score | FLOAT | |
| accuracy | FLOAT | |
| topics_understood | JSONB | |
| needs_practice | JSONB | |
| completed_at | TIMESTAMPTZ | |
| created_at / updated_at | TIMESTAMPTZ | |

### answers
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| attempt_id | UUID FK | |
| question_id | UUID FK | |
| selected_option_id | UUID | nullable |
| text_answer | TEXT | nullable |
| is_correct | BOOLEAN | |
| score | FLOAT | |
| feedback | TEXT | |
| created_at / updated_at | TIMESTAMPTZ | |

### learning_progress
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | |
| lesson_id | UUID FK | |
| subject | VARCHAR | |
| reading_seconds | INT | |
| quiz_accuracy | FLOAT | |
| completion_percent | FLOAT | |
| last_activity_at | TIMESTAMPTZ | |
| created_at / updated_at | TIMESTAMPTZ | |
| UNIQUE(user_id, lesson_id) | | |

### ai_processing_jobs
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lesson_id | UUID FK | |
| job_type | VARCHAR | ocr, content, tts, quiz, full |
| status | VARCHAR | queued, running, completed, failed |
| current_step | VARCHAR | friendly step key |
| progress_percent | FLOAT | |
| provider_meta | JSONB | which providers used |
| error_message | TEXT | friendly |
| started_at / finished_at | TIMESTAMPTZ | |
| created_at / updated_at | TIMESTAMPTZ | |

---

## Indexes

- `users.email` unique
- `lessons(user_id, created_at DESC)`
- `lesson_pages(lesson_id, page_number)`
- `lesson_words(sentence_id, position)`
- `quizzes(lesson_id)`
- `quiz_attempts(user_id, created_at DESC)`
- `learning_progress(user_id, last_activity_at DESC)`
- `ai_processing_jobs(lesson_id, status)`

---

## Status Lifecycles

**Lesson:** `draft` → `processing` → `ready` | `failed`

**Job:** `queued` → `running` → `completed` | `failed`

**Quiz:** `generating` → `ready` | `failed`

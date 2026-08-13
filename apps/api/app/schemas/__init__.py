from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StudentProfileOut(BaseModel):
    class_level: int
    learning_streak: int
    last_study_date: Optional[date] = None
    total_reading_seconds: int = 0

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    ui_language: str
    profile: Optional[StudentProfileOut] = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)
    class_level: int = Field(default=3, ge=1, le=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: UserOut
    access_token: str
    token_type: str = "bearer"


class LessonCard(BaseModel):
    id: str
    title: str
    language: str
    content_type: str
    subject: Optional[str] = None
    class_level: Optional[int] = None
    status: str
    progress_percent: float
    last_score: Optional[float] = None
    last_studied_at: Optional[datetime] = None
    page_count: int
    word_count: int
    summary: Optional[str] = None
    is_demo: bool = False

    model_config = {"from_attributes": True}


class LessonPageOut(BaseModel):
    id: str
    page_number: int
    original_storage_key: str
    width: Optional[int] = None
    height: Optional[int] = None

    model_config = {"from_attributes": True}


class LessonDetail(LessonCard):
    original_text: Optional[str] = None
    edited_text: Optional[str] = None
    error_message: Optional[str] = None
    pages: list[LessonPageOut] = []


class WordOut(BaseModel):
    id: str
    text: str
    index: int
    position: int


class SentenceOut(BaseModel):
    id: str
    text: str
    position: int
    words: list[WordOut]


class ParagraphOut(BaseModel):
    id: str
    text: str
    position: int
    sentences: list[SentenceOut]


class SectionOut(BaseModel):
    id: str
    heading: Optional[str] = None
    position: int
    paragraphs: list[ParagraphOut]


class LessonContentOut(BaseModel):
    lesson_id: str
    title: str
    language: str
    content_type: str
    summary: Optional[str] = None
    sections: list[SectionOut]


class IllustrationOut(BaseModel):
    id: str
    position: int
    caption: str
    storage_key: str
    provider: str

    model_config = {"from_attributes": True}


class IllustrationsOut(BaseModel):
    scenes: list[IllustrationOut] = []
    status: str
    message: str = ""
    gemini_ready: int = 0


class JobOut(BaseModel):
    id: str
    lesson_id: str
    job_type: str
    status: str
    current_step: str
    progress_percent: float
    message: str
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    lesson_id: str
    job_id: str
    status: str
    message: str


class CreateFromTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=80_000)
    title: Optional[str] = Field(default=None, max_length=200)
    class_level: Optional[int] = Field(default=None, ge=1, le=10)
    subject: Optional[str] = Field(default=None, max_length=128)


class EditTextRequest(BaseModel):
    edited_text: str
    title: Optional[str] = None


class CleanTextOut(BaseModel):
    cleaned_text: str


class GenerateAudioRequest(BaseModel):
    speed: str = "slow"
    voice: Optional[str] = None


class WordTimingOut(BaseModel):
    word_id: str
    start_ms: int
    end_ms: int


class AudioOut(BaseModel):
    id: str
    lesson_id: str
    language: str
    voice: str
    speed: float
    duration_ms: int
    provider: str
    timings: list[WordTimingOut]


class GenerateQuizRequest(BaseModel):
    difficulty: str = "easy"
    class_level: int = 3
    count: int = Field(default=6, ge=3, le=15)


class QuestionOptionOut(BaseModel):
    id: str
    label: str
    text: str
    position: int


class QuestionOut(BaseModel):
    id: str
    question_type: str
    prompt: str
    position: int
    points: float
    options: list[QuestionOptionOut]


class QuizOut(BaseModel):
    id: str
    lesson_id: str
    difficulty: str
    class_level: int
    language: str
    question_count: int
    status: str
    questions: list[QuestionOut]


class AnswerSubmit(BaseModel):
    question_id: str
    selected_option_id: Optional[str] = None
    text_answer: Optional[str] = None


class AttemptSubmitRequest(BaseModel):
    answers: list[AnswerSubmit]


class AnswerResultOut(BaseModel):
    question_id: str
    is_correct: bool
    score: float
    feedback: str
    expected_answer: Optional[str] = None
    explanation: Optional[str] = None


class AttemptResultOut(BaseModel):
    id: str
    quiz_id: str
    score: float
    max_score: float
    accuracy: float
    topics_understood: list[str]
    needs_practice: list[str]
    answers: list[AnswerResultOut]
    message: str


class DashboardOut(BaseModel):
    greeting: str
    streak: int
    average_score: float
    reading_time_minutes: int
    quiz_accuracy: float
    recent_lessons: list[LessonCard]
    continue_learning: list[LessonCard]
    subjects: list[dict[str, Any]]
    completed_count: int


class ProgressOut(BaseModel):
    lesson_id: str
    subject: Optional[str]
    reading_seconds: int
    quiz_accuracy: Optional[float]
    completion_percent: float
    last_activity_at: Optional[datetime]

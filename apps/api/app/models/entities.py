from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="STUDENT")
    ui_language: Mapped[str] = mapped_column(String(8), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    profile: Mapped[Optional["StudentProfile"]] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="user", lazy="selectin")


class StudentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    class_level: Mapped[int] = mapped_column(Integer, default=3)
    preferred_subjects: Mapped[list] = mapped_column(JSON, default=list)
    learning_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_study_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    total_reading_seconds: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="profile")


class Lesson(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lessons"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(500), default="Untitled Lesson")
    language: Mapped[str] = mapped_column(String(8), default="en")
    content_type: Mapped[str] = mapped_column(String(64), default="other")
    subject: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    class_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    edited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    last_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_studied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="lessons", lazy="selectin")
    pages: Mapped[list["LessonPage"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonPage.page_number",
        lazy="selectin",
    )
    sections: Mapped[list["LessonSection"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LessonSection.position",
        lazy="select",
    )
    audio_assets: Mapped[list["AudioAsset"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", lazy="selectin"
    )
    jobs: Mapped[list["AIProcessingJob"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", lazy="selectin"
    )


class LessonPage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_pages"

    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    original_storage_key: Mapped[str] = mapped_column(String(512))
    processed_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ocr_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    lesson: Mapped["Lesson"] = relationship(back_populates="pages")


class LessonSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_sections"

    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    lesson: Mapped["Lesson"] = relationship(back_populates="sections", lazy="selectin")
    paragraphs: Mapped[list["LessonParagraph"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LessonParagraph.position",
        lazy="selectin",
    )


class LessonParagraph(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_paragraphs"

    section_id: Mapped[str] = mapped_column(ForeignKey("lesson_sections.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped["LessonSection"] = relationship(back_populates="paragraphs", lazy="selectin")
    sentences: Mapped[list["LessonSentence"]] = relationship(
        back_populates="paragraph",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LessonSentence.position",
        lazy="selectin",
    )


class LessonSentence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_sentences"

    paragraph_id: Mapped[str] = mapped_column(ForeignKey("lesson_paragraphs.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)

    paragraph: Mapped["LessonParagraph"] = relationship(back_populates="sentences", lazy="selectin")
    words: Mapped[list["LessonWord"]] = relationship(
        back_populates="sentence",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LessonWord.position",
        lazy="selectin",
    )


class LessonWord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_words"

    sentence_id: Mapped[str] = mapped_column(ForeignKey("lesson_sentences.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))
    index: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)

    sentence: Mapped["LessonSentence"] = relationship(back_populates="words")
    timings: Mapped[list["TTSWordTiming"]] = relationship(
        back_populates="word",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AudioAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audio_assets"

    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    voice: Mapped[str] = mapped_column(String(64), default="default")
    speed: Mapped[float] = mapped_column(Float, default=0.9)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(32), default="browser")

    lesson: Mapped["Lesson"] = relationship(back_populates="audio_assets", lazy="selectin")
    timings: Mapped[list["TTSWordTiming"]] = relationship(
        back_populates="audio_asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class TTSWordTiming(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tts_word_timings"

    audio_asset_id: Mapped[str] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="CASCADE"), index=True
    )
    word_id: Mapped[str] = mapped_column(
        ForeignKey("lesson_words.id", ondelete="CASCADE"), index=True
    )
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)

    audio_asset: Mapped["AudioAsset"] = relationship(back_populates="timings")
    word: Mapped["LessonWord"] = relationship(back_populates="timings")


class Quiz(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quizzes"

    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    difficulty: Mapped[str] = mapped_column(String(16), default="easy")
    class_level: Mapped[int] = mapped_column(Integer, default=3)
    language: Mapped[str] = mapped_column(String(8), default="en")
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="generating")

    lesson: Mapped["Lesson"] = relationship(back_populates="quizzes", lazy="selectin")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.position",
        lazy="selectin",
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", lazy="selectin"
    )


class Question(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "questions"

    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(32))
    prompt: Mapped[str] = mapped_column(Text)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[float] = mapped_column(Float, default=1.0)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions", lazy="selectin")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.position",
        lazy="selectin",
    )


class QuestionOption(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "question_options"

    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    label: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["Question"] = relationship(back_populates="options")


class QuizAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_attempts"

    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    topics_understood: Mapped[list] = mapped_column(JSON, default=list)
    needs_practice: Mapped[list] = mapped_column(JSON, default=list)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts", lazy="selectin")
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan", lazy="selectin"
    )


class Answer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "answers"

    attempt_id: Mapped[str] = mapped_column(ForeignKey("quiz_attempts.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    selected_option_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    text_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")


class LearningProgress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reading_seconds: Mapped[int] = mapped_column(Integer, default=0)
    quiz_accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completion_percent: Mapped[float] = mapped_column(Float, default=0)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AIProcessingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_processing_jobs"

    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="full")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    current_step: Mapped[str] = mapped_column(String(64), default="queued")
    progress_percent: Mapped[float] = mapped_column(Float, default=0)
    provider_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    lesson: Mapped["Lesson"] = relationship(back_populates="jobs")

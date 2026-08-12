from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO


@dataclass
class OCRResult:
    text: str
    confidence: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredContent:
    title: str
    language: str
    content_type: str
    summary: str
    cleaned_text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedQuestion:
    question_type: str
    prompt: str
    explanation: str
    expected_answer: str | None
    options: list[dict[str, Any]]  # {label, text, is_correct}
    points: float = 1.0


@dataclass
class EvaluationResult:
    correct: bool
    score: float
    feedback: str
    expected_answer: str | None = None


@dataclass
class TTSResult:
    audio_bytes: bytes | None
    duration_ms: int
    provider: str
    voice: str
    word_timings: list[dict[str, Any]] = field(default_factory=list)
    # If audio_bytes is None, client should use browser TTS with estimated timings


class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image_path: Path, language_hint: str | None = None) -> OCRResult:
        raise NotImplementedError


class AIProvider(ABC):
    @abstractmethod
    async def structure_content(self, raw_text: str, language_hint: str | None = None) -> StructuredContent:
        raise NotImplementedError

    @abstractmethod
    async def generate_questions(
        self,
        source_text: str,
        language: str,
        *,
        difficulty: str,
        class_level: int,
        count: int,
    ) -> list[GeneratedQuestion]:
        raise NotImplementedError

    @abstractmethod
    async def evaluate_answer(
        self,
        question: str,
        expected: str,
        student_answer: str,
        language: str,
    ) -> EvaluationResult:
        raise NotImplementedError


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        speed: str = "slow",
        voice: str | None = None,
        words: list[tuple[str, str]] | None = None,
    ) -> TTSResult:
        raise NotImplementedError


class StorageProvider(ABC):
    @abstractmethod
    async def save(self, key: str, data: bytes | BinaryIO, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError

    @abstractmethod
    async def open_path(self, key: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    async def url_for(self, key: str, expires_seconds: int = 3600) -> str:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        raise NotImplementedError

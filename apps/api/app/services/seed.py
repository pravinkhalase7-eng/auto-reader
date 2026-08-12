"""Seed demo lessons for development."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lesson, StudentProfile, User
from app.core.security import hash_password
from app.providers.ocr import DEMO_TEXTS
from app.services.lesson_processing import LessonProcessingService
from app.utils.segmentation import reconstruct_from_text
from app.providers.ai import LocalAIProvider

logger = logging.getLogger(__name__)


DEMOS = [
    {
        "key": "en-story",
        "title": "The Lion and the Mouse",
        "language": "en",
        "content_type": "story",
        "subject": "English",
        "class_level": 3,
        "text": DEMO_TEXTS["lion"],
    },
    {
        "key": "hi-story",
        "title": "शेर और चूहा",
        "language": "hi",
        "content_type": "story",
        "subject": "Hindi",
        "class_level": 3,
        "text": DEMO_TEXTS["hindi"],
    },
    {
        "key": "mr-story",
        "title": "सिंह आणि उंदीर",
        "language": "mr",
        "content_type": "story",
        "subject": "Marathi",
        "class_level": 3,
        "text": DEMO_TEXTS["marathi"],
    },
    {
        "key": "en-poem",
        "title": "Twinkle Little Star",
        "language": "en",
        "content_type": "poem",
        "subject": "English",
        "class_level": 2,
        "text": DEMO_TEXTS["poem"],
    },
]


async def ensure_demo_user(db: AsyncSession) -> User:
    user = await db.scalar(select(User).where(User.email == "demo@example.com"))
    if user:
        return user
    user = User(
        email="demo@example.com",
        hashed_password=hash_password("demo1234"),
        full_name="Demo Student",
        role="STUDENT",
    )
    db.add(user)
    await db.flush()
    db.add(StudentProfile(user_id=user.id, class_level=3, learning_streak=3))
    await db.commit()
    user = await db.scalar(select(User).where(User.id == user.id))
    assert user
    return user


async def seed_demo_lessons(db: AsyncSession) -> None:
    user = await ensure_demo_user(db)
    existing = await db.scalar(select(Lesson).where(Lesson.is_demo.is_(True)).limit(1))
    if existing:
        logger.info("demo_lessons_already_seeded")
        return

    ai = LocalAIProvider()
    svc = LessonProcessingService(db)

    for demo in DEMOS:
        structured = await ai.structure_content(demo["text"], language_hint=demo["language"])
        lesson = Lesson(
            user_id=user.id,
            title=demo["title"],
            language=demo["language"],
            content_type=demo["content_type"],
            subject=demo["subject"],
            class_level=demo["class_level"],
            summary=structured.summary,
            original_text=demo["text"],
            edited_text=demo["text"],
            status="ready",
            page_count=1,
            is_demo=True,
            progress_percent=0,
        )
        db.add(lesson)
        await db.flush()
        tree = reconstruct_from_text(
            demo["text"],
            title=demo["title"],
            language=demo["language"],
            content_type=demo["content_type"],
            summary=structured.summary,
        )
        await svc.persist_content_tree(lesson, tree)
        await svc.ensure_audio(lesson, speed="slow")
        logger.info("seeded_demo title=%s", demo["title"])

    await db.commit()

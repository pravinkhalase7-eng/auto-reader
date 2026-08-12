from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import LearningProgress, Lesson, User
from app.schemas import DashboardOut, LessonCard, ProgressOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    lessons = list(
        await db.scalars(
            select(Lesson)
            .where(Lesson.deleted_at.is_(None))
            .where((Lesson.user_id == user.id) | (Lesson.is_demo.is_(True)))
            .order_by(Lesson.updated_at.desc())
        )
    )
    recent = [LessonCard.model_validate(l) for l in lessons[:6]]
    continue_learning = [
        LessonCard.model_validate(l)
        for l in lessons
        if l.status == "ready" and l.progress_percent < 100
    ][:4]
    completed = [l for l in lessons if l.progress_percent >= 100 and l.user_id == user.id]
    scores = [l.last_score for l in lessons if l.last_score is not None and l.user_id == user.id]
    avg = sum(scores) / len(scores) if scores else 0.0
    streak = user.profile.learning_streak if user.profile else 0
    reading_minutes = (user.profile.total_reading_seconds // 60) if user.profile else 0
    accuracies = [s / 100 for s in scores] if scores else []
    quiz_acc = sum(accuracies) / len(accuracies) if accuracies else 0.0

    subject_map: dict[str, list[Lesson]] = defaultdict(list)
    for l in lessons:
        key = l.subject or l.language.upper()
        subject_map[key].append(l)

    subjects = [
        {
            "name": name,
            "count": len(items),
            "avg_progress": sum(i.progress_percent for i in items) / len(items) if items else 0,
        }
        for name, items in subject_map.items()
    ]

    greeting = f"Great to see you, {user.full_name.split()[0]}! Let's learn something wonderful today."

    return DashboardOut(
        greeting=greeting,
        streak=streak,
        average_score=round(avg, 1),
        reading_time_minutes=reading_minutes,
        quiz_accuracy=round(quiz_acc, 2),
        recent_lessons=recent,
        continue_learning=continue_learning,
        subjects=subjects,
        completed_count=len(completed),
    )


@router.get("/progress", response_model=list[ProgressOut])
async def progress(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(LearningProgress)
        .where(LearningProgress.user_id == user.id)
        .order_by(LearningProgress.last_activity_at.desc())
    )
    return [
        ProgressOut(
            lesson_id=r.lesson_id,
            subject=r.subject,
            reading_seconds=r.reading_seconds,
            quiz_accuracy=r.quiz_accuracy,
            completion_percent=r.completion_percent,
            last_activity_at=r.last_activity_at,
        )
        for r in rows
    ]

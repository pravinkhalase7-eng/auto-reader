from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.exceptions import FRIENDLY_MESSAGES, AppError, ForbiddenError, NotFoundError, to_http_exception
from app.models import AIProcessingJob, AudioAsset, Lesson, LessonPage, LessonParagraph, LessonSection, LessonSentence, TTSWordTiming, User
from app.providers.factory import get_storage_provider
from app.schemas import (
    AudioOut,
    CleanTextOut,
    EditTextRequest,
    GenerateAudioRequest,
    GenerateQuizRequest,
    JobOut,
    LessonCard,
    LessonContentOut,
    LessonDetail,
    LessonPageOut,
    ParagraphOut,
    QuizOut,
    QuestionOptionOut,
    QuestionOut,
    SectionOut,
    SentenceOut,
    UploadResponse,
    WordOut,
    WordTimingOut,
)
from app.services.lesson_processing import LessonProcessingService
from app.services.teacher_voice import message_for_step
from app.workers.queue import task_queue

router = APIRouter(prefix="/lessons", tags=["lessons"])
settings = get_settings()


async def _get_owned_lesson(db: AsyncSession, user: User, lesson_id: str) -> Lesson:
    lesson = await db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id, Lesson.deleted_at.is_(None))
        .options(
            selectinload(Lesson.pages),
            noload(Lesson.sections),
            noload(Lesson.audio_assets),
        )
    )
    if not lesson:
        raise NotFoundError()
    if lesson.user_id != user.id and not lesson.is_demo:
        raise ForbiddenError()
    return lesson


@router.post("/upload", response_model=UploadResponse)
async def upload_lesson(
    files: list[UploadFile] = File(...),
    class_level: int | None = Form(default=None),
    subject: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise to_http_exception(AppError("Please upload at least one photo.", code="NO_FILES"))

    storage = get_storage_provider()
    lesson = Lesson(
        user_id=user.id,
        title="New Lesson",
        status="processing",
        class_level=class_level or (user.profile.class_level if user.profile else 3),
        subject=subject,
        page_count=len(files),
    )
    db.add(lesson)
    await db.flush()

    for i, upload in enumerate(files, start=1):
        content_type = upload.content_type or "application/octet-stream"
        if content_type not in settings.allowed_image_type_list and not content_type.startswith("image/"):
            raise to_http_exception(AppError(FRIENDLY_MESSAGES["INVALID_IMAGE"], code="INVALID_IMAGE"))
        data = await upload.read()
        if len(data) > settings.max_upload_bytes:
            raise to_http_exception(AppError(FRIENDLY_MESSAGES["IMAGE_TOO_LARGE"], code="IMAGE_TOO_LARGE"))
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        key = f"originals/{lesson.id}/page_{i}.{ext}"
        await storage.save(key, data, content_type)
        db.add(
            LessonPage(
                lesson_id=lesson.id,
                page_number=i,
                original_storage_key=key,
            )
        )

    job = AIProcessingJob(lesson_id=lesson.id, job_type="full", status="queued", current_step="queued")
    db.add(job)
    await db.commit()

    lesson_id, job_id = lesson.id, job.id

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            svc = LessonProcessingService(session)
            await svc.run_full_pipeline(lesson_id, job_id)

    task_queue.enqueue(_run(), name=f"process-{lesson_id}")

    return UploadResponse(
        lesson_id=lesson_id,
        job_id=job_id,
        status="processing",
        message=message_for_step("uploaded"),
    )


@router.get("", response_model=list[LessonCard])
async def list_lessons(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(Lesson)
        .where(Lesson.deleted_at.is_(None))
        .where((Lesson.user_id == user.id) | (Lesson.is_demo.is_(True)))
        .order_by(Lesson.updated_at.desc())
    )
    return [LessonCard.model_validate(r) for r in rows]


@router.get("/{lesson_id}", response_model=LessonDetail)
async def get_lesson(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    return LessonDetail(
        **LessonCard.model_validate(lesson).model_dump(),
        original_text=lesson.original_text,
        edited_text=lesson.edited_text,
        error_message=lesson.error_message,
        pages=[LessonPageOut.model_validate(p) for p in lesson.pages],
    )


@router.get("/{lesson_id}/content", response_model=LessonContentOut)
async def get_content(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc

    lesson = await db.scalar(
        select(Lesson)
        .where(Lesson.id == lesson.id)
        .options(
            selectinload(Lesson.sections)
            .selectinload(LessonSection.paragraphs)
            .selectinload(LessonParagraph.sentences)
            .selectinload(LessonSentence.words)
        )
    )
    assert lesson
    sections = [
        SectionOut(
            id=s.id,
            heading=s.heading,
            position=s.position,
            paragraphs=[
                ParagraphOut(
                    id=p.id,
                    text=p.text,
                    position=p.position,
                    sentences=[
                        SentenceOut(
                            id=sent.id,
                            text=sent.text,
                            position=sent.position,
                            words=[WordOut(id=w.id, text=w.text, index=w.index, position=w.position) for w in sent.words],
                        )
                        for sent in p.sentences
                    ],
                )
                for p in s.paragraphs
            ],
        )
        for s in lesson.sections
    ]
    return LessonContentOut(
        lesson_id=lesson.id,
        title=lesson.title,
        language=lesson.language,
        content_type=lesson.content_type,
        summary=lesson.summary,
        sections=sections,
    )


@router.get("/{lesson_id}/jobs/{job_id}", response_model=JobOut)
async def get_job(lesson_id: str, job_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    job = await db.get(AIProcessingJob, job_id)
    if not job or job.lesson_id != lesson_id:
        raise to_http_exception(NotFoundError("I couldn't find that update."))
    return JobOut(
        id=job.id,
        lesson_id=job.lesson_id,
        job_type=job.job_type,
        status=job.status,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        message=message_for_step(job.current_step),
        error_message=job.error_message,
    )


@router.post("/{lesson_id}/clean-text", response_model=CleanTextOut)
async def clean_lesson_text(
    lesson_id: str,
    body: EditTextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    from app.utils.ocr_clean import clean_ocr_text

    return CleanTextOut(cleaned_text=clean_ocr_text(body.edited_text))


@router.patch("/{lesson_id}/text", response_model=LessonDetail)
async def edit_text(
    lesson_id: str,
    body: EditTextRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    if lesson.is_demo and lesson.user_id != user.id:
        # Allow demo edits as a personal copy path — for MVP just process
        pass
    svc = LessonProcessingService(db)
    await svc.regenerate_from_edited_text(
        lesson,
        body.edited_text,
        title=body.title,
    )
    await db.refresh(lesson)
    return await get_lesson(lesson_id, user, db)


@router.post("/{lesson_id}/generate-audio", response_model=AudioOut)
async def generate_audio(
    lesson_id: str,
    body: GenerateAudioRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    svc = LessonProcessingService(db)
    asset = await svc.ensure_audio(lesson, speed=body.speed)
    return await get_audio(lesson_id, user, db, asset_id=asset.id)


@router.get("/{lesson_id}/audio", response_model=AudioOut)
async def get_audio(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    asset_id: str | None = None,
):
    try:
        await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc

    q = select(AudioAsset).where(AudioAsset.lesson_id == lesson_id).options(selectinload(AudioAsset.timings))
    if asset_id:
        q = q.where(AudioAsset.id == asset_id)
    else:
        q = q.order_by(AudioAsset.created_at.desc())
    asset = await db.scalar(q)
    if not asset:
        # Generate on demand
        lesson = await db.get(Lesson, lesson_id)
        assert lesson
        svc = LessonProcessingService(db)
        asset = await svc.ensure_audio(lesson)
        asset = await db.scalar(
            select(AudioAsset).where(AudioAsset.id == asset.id).options(selectinload(AudioAsset.timings))
        )
    assert asset
    return AudioOut(
        id=asset.id,
        lesson_id=asset.lesson_id,
        language=asset.language,
        voice=asset.voice,
        speed=asset.speed,
        duration_ms=asset.duration_ms,
        provider=asset.provider,
        timings=[WordTimingOut(word_id=t.word_id, start_ms=t.start_ms, end_ms=t.end_ms) for t in asset.timings],
    )


@router.post("/{lesson_id}/generate-quiz", response_model=QuizOut)
async def generate_quiz(
    lesson_id: str,
    body: GenerateQuizRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    svc = LessonProcessingService(db)
    quiz = await svc.generate_quiz(
        lesson,
        difficulty=body.difficulty,
        class_level=body.class_level,
        count=body.count,
    )
    return await get_quiz(lesson_id, user, db, quiz_id=quiz.id)


@router.get("/{lesson_id}/quiz", response_model=QuizOut)
async def get_quiz(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    quiz_id: str | None = None,
):
    from app.models import Question, QuestionOption, Quiz

    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc

    q = (
        select(Quiz)
        .where(Quiz.lesson_id == lesson_id)
        .options(selectinload(Quiz.questions).selectinload(Question.options))
        .order_by(Quiz.created_at.desc())
    )
    if quiz_id:
        q = q.where(Quiz.id == quiz_id)
    quiz = await db.scalar(q)
    if not quiz:
        svc = LessonProcessingService(db)
        quiz = await svc.generate_quiz(
            lesson,
            difficulty="easy",
            class_level=lesson.class_level or 3,
            count=6,
        )
        quiz = await db.scalar(
            select(Quiz)
            .where(Quiz.id == quiz.id)
            .options(selectinload(Quiz.questions).selectinload(Question.options))
        )
    assert quiz
    return QuizOut(
        id=quiz.id,
        lesson_id=quiz.lesson_id,
        difficulty=quiz.difficulty,
        class_level=quiz.class_level,
        language=quiz.language,
        question_count=quiz.question_count,
        status=quiz.status,
        questions=[
            QuestionOut(
                id=qq.id,
                question_type=qq.question_type,
                prompt=qq.prompt,
                position=qq.position,
                points=qq.points,
                options=[
                    QuestionOptionOut(id=o.id, label=o.label, text=o.text, position=o.position)
                    for o in qq.options
                ],
            )
            for qq in quiz.questions
        ],
    )


@router.post("/{lesson_id}/process", response_model=UploadResponse)
async def reprocess(lesson_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        lesson = await _get_owned_lesson(db, user, lesson_id)
    except AppError as exc:
        raise to_http_exception(exc) from exc
    job = AIProcessingJob(lesson_id=lesson.id, job_type="full", status="queued", current_step="queued")
    lesson.status = "processing"
    db.add(job)
    await db.commit()
    lid, jid = lesson.id, job.id

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            await LessonProcessingService(session).run_full_pipeline(lid, jid)

    task_queue.enqueue(_run(), name=f"reprocess-{lid}")
    return UploadResponse(lesson_id=lid, job_id=jid, status="processing", message=message_for_step("queued"))

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import FRIENDLY_MESSAGES, AppError
from app.models import (
    AIProcessingJob,
    AudioAsset,
    Lesson,
    LessonPage,
    LessonParagraph,
    LessonSection,
    LessonSentence,
    LessonWord,
    Question,
    QuestionOption,
    Quiz,
    TTSWordTiming,
)
from app.providers.factory import get_ai_provider, get_ocr_provider, get_storage_provider, get_tts_provider
from app.services.image_preprocess import ImagePreprocessService
from app.services.teacher_voice import message_for_step
from app.utils.segmentation import ContentTree, flatten_words, reconstruct_from_text

logger = logging.getLogger(__name__)
settings = get_settings()


class LessonProcessingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_provider()
        self.ocr = get_ocr_provider()
        self.ai = get_ai_provider()
        self.tts = get_tts_provider()
        self.preprocess = ImagePreprocessService()

    async def _set_job(self, job: AIProcessingJob, *, step: str, progress: float, status: str = "running") -> None:
        job.current_step = step
        job.progress_percent = progress
        job.status = status
        if status == "running" and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        if status in {"completed", "failed"}:
            job.finished_at = datetime.now(timezone.utc)
        await self.db.commit()

    def _expunge_content_rows(self, *types: type) -> None:
        for obj in list(self.db.identity_map.values()):
            if isinstance(obj, types):
                self.db.expunge(obj)

    async def _wipe_lesson_tree(self, lesson_id: str) -> None:
        """Delete timings first, then words. ORM cascade cannot see this FK."""
        params = {"lesson_id": lesson_id}
        await self.db.execute(
            text(
                """
                DELETE FROM tts_word_timings
                 WHERE word_id IN (
                    SELECT lw.id FROM lesson_words lw
                    JOIN lesson_sentences ls ON ls.id = lw.sentence_id
                    JOIN lesson_paragraphs lp ON lp.id = ls.paragraph_id
                    JOIN lesson_sections lsec ON lsec.id = lp.section_id
                    WHERE lsec.lesson_id = :lesson_id
                 )
                    OR audio_asset_id IN (
                    SELECT id FROM audio_assets WHERE lesson_id = :lesson_id
                 )
                """
            ),
            params,
        )
        await self.db.execute(
            text("DELETE FROM audio_assets WHERE lesson_id = :lesson_id"),
            params,
        )
        await self.db.execute(
            text(
                """
                DELETE FROM lesson_words
                 WHERE sentence_id IN (
                    SELECT ls.id FROM lesson_sentences ls
                    JOIN lesson_paragraphs lp ON lp.id = ls.paragraph_id
                    JOIN lesson_sections lsec ON lsec.id = lp.section_id
                    WHERE lsec.lesson_id = :lesson_id
                 )
                """
            ),
            params,
        )
        await self.db.execute(
            text(
                """
                DELETE FROM lesson_sentences
                 WHERE paragraph_id IN (
                    SELECT lp.id FROM lesson_paragraphs lp
                    JOIN lesson_sections lsec ON lsec.id = lp.section_id
                    WHERE lsec.lesson_id = :lesson_id
                 )
                """
            ),
            params,
        )
        await self.db.execute(
            text(
                """
                DELETE FROM lesson_paragraphs
                 WHERE section_id IN (
                    SELECT id FROM lesson_sections WHERE lesson_id = :lesson_id
                 )
                """
            ),
            params,
        )
        await self.db.execute(
            text("DELETE FROM lesson_sections WHERE lesson_id = :lesson_id"),
            params,
        )
        logger.info("wipe_lesson_tree sql_ok lesson_id=%s", lesson_id)

    async def persist_content_tree(self, lesson: Lesson, tree: ContentTree) -> None:
        # Detach loaded words/timings FIRST. A later flush must not ORM-delete them
        # while tts_word_timings still points at lesson_words.
        self._expunge_content_rows(
            TTSWordTiming,
            AudioAsset,
            LessonWord,
            LessonSentence,
            LessonParagraph,
            LessonSection,
        )
        self.db.expire(lesson, ["sections", "audio_assets"])
        logger.info("wipe_lesson_tree start lesson_id=%s", lesson.id)
        await self._wipe_lesson_tree(lesson.id)
        logger.info("wipe_lesson_tree done lesson_id=%s", lesson.id)

        lesson.title = tree.title
        lesson.language = tree.language
        lesson.content_type = tree.content_type
        lesson.summary = tree.summary
        lesson.word_count = tree.word_count
        lesson.edited_text = tree.full_text

        for section_node in tree.sections:
            section = LessonSection(
                id=section_node.id,
                lesson_id=lesson.id,
                heading=section_node.heading,
                position=section_node.position,
            )
            self.db.add(section)
            await self.db.flush()
            for para_node in section_node.paragraphs:
                para = LessonParagraph(
                    id=para_node.id,
                    section_id=section.id,
                    text=para_node.text,
                    position=para_node.position,
                )
                self.db.add(para)
                await self.db.flush()
                for sent_node in para_node.sentences:
                    sent = LessonSentence(
                        id=sent_node.id,
                        paragraph_id=para.id,
                        text=sent_node.text,
                        position=sent_node.position,
                    )
                    self.db.add(sent)
                    await self.db.flush()
                    for word_node in sent_node.words:
                        self.db.add(
                            LessonWord(
                                id=word_node.id,
                                sentence_id=sent.id,
                                text=word_node.text,
                                index=word_node.index,
                                position=word_node.position,
                            )
                        )
        await self.db.flush()

    async def run_full_pipeline(self, lesson_id: str, job_id: str) -> None:
        job = await self.db.get(AIProcessingJob, job_id)
        lesson = await self.db.scalar(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.pages), selectinload(Lesson.sections))
        )
        if not job or not lesson:
            return

        try:
            lesson.status = "processing"
            job.provider_meta = {
                "ai": settings.ai_provider,
                "ocr": settings.ocr_provider,
                "tts": settings.tts_provider,
            }
            await self._set_job(job, step="uploaded", progress=10)

            await self._set_job(job, step="preprocessing", progress=20)
            page_texts: list[str] = []
            for page in sorted(lesson.pages, key=lambda p: p.page_number):
                original = await self.storage.open_path(page.original_storage_key)
                processed_key = f"processed/{lesson.id}/page_{page.page_number}.png"
                processed_path = await self.storage.open_path(processed_key)
                w, h = self.preprocess.process_file(original, processed_path)
                page.processed_storage_key = processed_key
                page.width, page.height = w, h

                await self._set_job(job, step="ocr", progress=35 + page.page_number)
                ocr = await self.ocr.extract_text(processed_path)
                page.ocr_raw_text = ocr.text
                page_texts.append(ocr.text.strip())

            merged = "\n\n".join(t for t in page_texts if t)
            if not merged.strip():
                raise AppError(FRIENDLY_MESSAGES["EMPTY_CONTENT"], code="EMPTY_CONTENT")

            lesson.original_text = merged

            await self._set_job(job, step="understanding", progress=55)
            structured = await self.ai.structure_content(merged)

            await self._set_job(job, step="language", progress=65)
            await self._set_job(job, step="preparing_lesson", progress=75)

            tree = reconstruct_from_text(
                structured.cleaned_text,
                title=structured.title,
                language=structured.language,
                content_type=structured.content_type,
                summary=structured.summary,
            )
            await self.persist_content_tree(lesson, tree)

            await self._set_job(job, step="preparing_teacher", progress=88)
            await self.ensure_audio(lesson, speed="slow")

            lesson.status = "ready"
            lesson.error_message = None
            await self._set_job(job, step="completed", progress=100, status="completed")
            logger.info("lesson_ready lesson_id=%s words=%s", lesson.id, lesson.word_count)
        except AppError as exc:
            lesson.status = "failed"
            lesson.error_message = exc.message
            job.error_message = exc.message
            await self._set_job(job, step="failed", progress=job.progress_percent, status="failed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("pipeline_failed lesson_id=%s", lesson_id)
            lesson.status = "failed"
            lesson.error_message = FRIENDLY_MESSAGES["AI_FAILED"]
            job.error_message = FRIENDLY_MESSAGES["AI_FAILED"]
            await self._set_job(job, step="failed", progress=job.progress_percent, status="failed")
            _ = exc

    async def ensure_audio(self, lesson: Lesson, speed: str = "slow") -> AudioAsset:
        params = {"lesson_id": lesson.id}
        await self.db.execute(
            text(
                """
                DELETE FROM tts_word_timings
                 WHERE audio_asset_id IN (
                    SELECT id FROM audio_assets WHERE lesson_id = :lesson_id
                 )
                """
            ),
            params,
        )
        await self.db.execute(text("DELETE FROM audio_assets WHERE lesson_id = :lesson_id"), params)
        self._expunge_content_rows(TTSWordTiming, AudioAsset)
        # Query words directly to avoid stale identity-map collections
        sections = list(
            await self.db.scalars(
                select(LessonSection)
                .where(LessonSection.lesson_id == lesson.id)
                .options(
                    selectinload(LessonSection.paragraphs)
                    .selectinload(LessonParagraph.sentences)
                    .selectinload(LessonSentence.words)
                )
                .order_by(LessonSection.position)
            )
        )

        tree_words: list[tuple[str, str]] = []
        texts: list[str] = []
        for section in sections:
            for para in section.paragraphs:
                texts.append(para.text)
                for sent in para.sentences:
                    for w in sent.words:
                        tree_words.append((w.id, w.text))

        full_text = "\n\n".join(texts)
        tts_result = await self.tts.synthesize(
            full_text,
            lesson.language,
            speed=speed,
            words=tree_words,
        )

        asset = AudioAsset(
            lesson_id=lesson.id,
            storage_key="",
            language=lesson.language,
            voice=tts_result.voice,
            speed={"very_slow": 0.7, "slow": 0.85, "normal": 1.0}.get(speed, 0.85),
            duration_ms=tts_result.duration_ms,
            provider=tts_result.provider,
        )
        self.db.add(asset)
        await self.db.flush()

        for t in tts_result.word_timings:
            self.db.add(
                TTSWordTiming(
                    audio_asset_id=asset.id,
                    word_id=t["word_id"],
                    start_ms=t["start_ms"],
                    end_ms=t["end_ms"],
                )
            )
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def regenerate_from_edited_text(
        self,
        lesson: Lesson,
        edited_text: str,
        *,
        title: str | None = None,
    ) -> None:
        from app.utils.ocr_clean import clean_ocr_text

        edited_text = clean_ocr_text(edited_text)
        structured = await self.ai.structure_content(edited_text, language_hint=lesson.language)
        tree = reconstruct_from_text(
            structured.cleaned_text,
            title=title or structured.title or lesson.title,
            language=structured.language,
            content_type=structured.content_type,
            summary=structured.summary,
        )
        lesson.edited_text = edited_text
        if title and title.strip():
            tree.title = title.strip()
        await self.persist_content_tree(lesson, tree)
        await self.ensure_audio(lesson, speed="slow")
        lesson.status = "ready"
        await self.db.commit()

    async def generate_quiz(
        self,
        lesson: Lesson,
        *,
        difficulty: str,
        class_level: int,
        count: int,
    ) -> Quiz:
        source = lesson.edited_text or lesson.original_text or ""
        questions = await self.ai.generate_questions(
            source,
            lesson.language,
            difficulty=difficulty,
            class_level=class_level,
            count=count,
        )
        quiz = Quiz(
            lesson_id=lesson.id,
            difficulty=difficulty,
            class_level=class_level,
            language=lesson.language,
            question_count=len(questions),
            status="ready",
        )
        self.db.add(quiz)
        await self.db.flush()
        for i, q in enumerate(questions):
            question = Question(
                quiz_id=quiz.id,
                question_type=q.question_type,
                prompt=q.prompt,
                explanation=q.explanation,
                expected_answer=q.expected_answer,
                position=i,
                points=q.points,
            )
            self.db.add(question)
            await self.db.flush()
            for j, opt in enumerate(q.options):
                self.db.add(
                    QuestionOption(
                        question_id=question.id,
                        label=opt.get("label", chr(65 + j)),
                        text=opt["text"],
                        is_correct=bool(opt.get("is_correct")),
                        position=j,
                    )
                )
        await self.db.commit()
        return quiz

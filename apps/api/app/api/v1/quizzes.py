from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError, to_http_exception
from app.models import Answer, LearningProgress, Lesson, Question, QuestionOption, Quiz, QuizAttempt, StudentProfile, User
from app.providers.factory import get_ai_provider
from app.schemas import AnswerResultOut, AttemptResultOut, AttemptSubmitRequest

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _topics_for(language: str, accuracy: float) -> tuple[list[str], list[str]]:
    if language == "hi":
        understood = ["कहानी के पात्र", "मुख्य घटना"] if accuracy >= 0.6 else ["मुख्य घटना"]
        practice = ["शब्दावली"] if accuracy < 0.8 else []
        if accuracy < 0.6:
            practice.append("घटना क्रम")
        return understood, practice
    if language == "mr":
        understood = ["पात्रे", "मुख्य प्रसंग"] if accuracy >= 0.6 else ["मुख्य प्रसंग"]
        practice = ["शब्दसंग्रह"] if accuracy < 0.8 else []
        if accuracy < 0.6:
            practice.append("क्रमाने घटना")
        return understood, practice
    understood = ["Story characters", "Main event"] if accuracy >= 0.6 else ["Main event"]
    practice = ["Vocabulary"] if accuracy < 0.8 else []
    if accuracy < 0.6:
        practice.append("Sequence of events")
    return understood, practice


@router.post("/{quiz_id}/attempt", response_model=AttemptResultOut)
async def submit_attempt(
    quiz_id: str,
    body: AttemptSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quiz = await db.scalar(
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.questions).selectinload(Question.options), selectinload(Quiz.lesson))
    )
    if not quiz:
        raise to_http_exception(NotFoundError("I couldn't find that quiz."))
    lesson = quiz.lesson
    if lesson.user_id != user.id and not lesson.is_demo:
        raise to_http_exception(ForbiddenError())

    ai = get_ai_provider()
    answers_by_q = {a.question_id: a for a in body.answers}
    results: list[AnswerResultOut] = []
    score = 0.0
    max_score = 0.0

    attempt = QuizAttempt(quiz_id=quiz.id, user_id=user.id)
    db.add(attempt)
    await db.flush()

    for question in quiz.questions:
        max_score += question.points
        submitted = answers_by_q.get(question.id)
        is_correct = False
        points = 0.0
        feedback = ""
        expected = question.expected_answer

        if question.question_type in {"mcq", "true_false", "vocabulary", "sequence"}:
            selected = None
            if submitted and submitted.selected_option_id:
                selected = next((o for o in question.options if o.id == submitted.selected_option_id), None)
            correct_opt = next((o for o in question.options if o.is_correct), None)
            expected = correct_opt.text if correct_opt else expected
            if selected and selected.is_correct:
                is_correct = True
                points = question.points
                feedback = {
                    "en": "Correct! Well done!",
                    "hi": "सही! बहुत बढ़िया!",
                    "mr": "बरोबर! छान!",
                }.get(quiz.language, "Correct!")
            else:
                feedback = question.explanation or {
                    "en": f"Nice try! The answer is: {expected}",
                    "hi": f"अच्छा प्रयास! सही उत्तर: {expected}",
                    "mr": f"चांगला प्रयत्न! उत्तर: {expected}",
                }.get(quiz.language, f"Answer: {expected}")
            db.add(
                Answer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    selected_option_id=submitted.selected_option_id if submitted else None,
                    is_correct=is_correct,
                    score=points,
                    feedback=feedback,
                )
            )
        else:
            text = (submitted.text_answer if submitted else "") or ""
            evaluation = await ai.evaluate_answer(
                question.prompt,
                question.expected_answer or "",
                text,
                quiz.language,
            )
            is_correct = evaluation.correct
            points = question.points * evaluation.score
            feedback = evaluation.feedback
            expected = evaluation.expected_answer
            db.add(
                Answer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    text_answer=text,
                    is_correct=is_correct,
                    score=points,
                    feedback=feedback,
                )
            )

        score += points
        results.append(
            AnswerResultOut(
                question_id=question.id,
                is_correct=is_correct,
                score=points,
                feedback=feedback,
                expected_answer=expected,
                explanation=question.explanation,
            )
        )

    accuracy = (score / max_score) if max_score else 0
    understood, practice = _topics_for(quiz.language, accuracy)
    attempt.score = score
    attempt.max_score = max_score
    attempt.accuracy = accuracy
    attempt.topics_understood = understood
    attempt.needs_practice = practice
    attempt.completed_at = datetime.now(timezone.utc)

    lesson.last_score = accuracy * 100
    lesson.progress_percent = max(lesson.progress_percent, 100.0)
    lesson.last_studied_at = datetime.now(timezone.utc)

    progress = await db.scalar(
        select(LearningProgress).where(
            LearningProgress.user_id == user.id, LearningProgress.lesson_id == lesson.id
        )
    )
    if not progress:
        progress = LearningProgress(user_id=user.id, lesson_id=lesson.id, subject=lesson.subject)
        db.add(progress)
    progress.quiz_accuracy = accuracy
    progress.completion_percent = 100
    progress.last_activity_at = datetime.now(timezone.utc)

    if user.profile:
        profile = user.profile
        today = date.today()
        if profile.last_study_date == today:
            pass
        elif profile.last_study_date and (today - profile.last_study_date).days == 1:
            profile.learning_streak += 1
        else:
            profile.learning_streak = 1
        profile.last_study_date = today

    await db.commit()

    message = {
        "en": "Great job! Let's look at your results.",
        "hi": "बहुत बढ़िया! आइए परिणाम देखें।",
        "mr": "छान काम! चला निकाल पाहूया.",
    }.get(quiz.language, "Great job!")

    return AttemptResultOut(
        id=attempt.id,
        quiz_id=quiz.id,
        score=score,
        max_score=max_score,
        accuracy=accuracy,
        topics_understood=understood,
        needs_practice=practice,
        answers=results,
        message=message,
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptResultOut)
async def get_attempt(attempt_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    attempt = await db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .options(selectinload(QuizAttempt.answers), selectinload(QuizAttempt.quiz).selectinload(Quiz.questions))
    )
    if not attempt or attempt.user_id != user.id:
        raise to_http_exception(NotFoundError())
    qmap = {q.id: q for q in attempt.quiz.questions}
    return AttemptResultOut(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        score=attempt.score,
        max_score=attempt.max_score,
        accuracy=attempt.accuracy,
        topics_understood=attempt.topics_understood or [],
        needs_practice=attempt.needs_practice or [],
        answers=[
            AnswerResultOut(
                question_id=a.question_id,
                is_correct=a.is_correct,
                score=a.score,
                feedback=a.feedback or "",
                expected_answer=qmap.get(a.question_id).expected_answer if qmap.get(a.question_id) else None,
                explanation=qmap.get(a.question_id).explanation if qmap.get(a.question_id) else None,
            )
            for a in attempt.answers
        ],
        message="Here are your results!",
    )

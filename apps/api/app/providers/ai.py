"""AI providers for content structuring, quiz generation, and evaluation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.prompts import answer_evaluation as eval_prompts
from app.prompts import content_extraction as content_prompts
from app.prompts import quiz_generation as quiz_prompts
from app.providers.base import (
    AIProvider,
    EvaluationResult,
    GeneratedQuestion,
    StructuredContent,
)
from app.utils.languages import detect_script_language
from app.utils.segmentation import split_sentences, tokenize_words

logger = logging.getLogger(__name__)


def _classify_content(text: str) -> str:
    lower = text.lower()
    if "twinkle" in lower or text.count("\n") >= 4 and all(len(l) < 70 for l in text.splitlines() if l.strip()):
        lines = [l for l in text.splitlines() if l.strip()]
        if len(lines) >= 4 and sum(1 for l in lines if len(l) < 60) >= 3:
            return "poem"
    if any(m in lower for m in ("moral", "नीति", "once upon", "story")):
        return "story"
    if "?" in text and text.count("?") >= 3:
        return "worksheet"
    if re.search(r"^\s*\d+[\).]", text, re.M):
        return "lesson"
    return "story" if len(text) > 200 else "paragraph"


def _title_from_text(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) < 80:
            return line
    return "Your Lesson"


def _summary(text: str, language: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return ""
    first = sentences[0][:180]
    if language == "hi":
        return f"यह पाठ हमें सिखाता है: {first}"
    if language == "mr":
        return f"हा धडा शिकवतो: {first}"
    return f"This lesson is about: {first}"


class LocalAIProvider(AIProvider):
    async def structure_content(self, raw_text: str, language_hint: str | None = None) -> StructuredContent:
        language = language_hint or detect_script_language(raw_text)
        cleaned = raw_text.strip()
        content_type = _classify_content(cleaned)
        return StructuredContent(
            title=_title_from_text(cleaned),
            language=language,
            content_type=content_type,
            summary=_summary(cleaned, language),
            cleaned_text=cleaned,
            meta={"provider": "local"},
        )

    async def generate_questions(
        self,
        source_text: str,
        language: str,
        *,
        difficulty: str,
        class_level: int,
        count: int,
    ) -> list[GeneratedQuestion]:
        sentences = [s for s in split_sentences(source_text) if len(tokenize_words(s)) >= 4]
        words = tokenize_words(source_text)
        significant = [w for w in words if len(w.strip(".,!?;:\"'()।")) > 3]
        questions: list[GeneratedQuestion] = []

        # MCQ from first substantial sentence
        if sentences:
            s = sentences[0]
            tokens = tokenize_words(s)
            answer = tokens[min(3, len(tokens) - 1)].strip(".,!?;:\"'()।")
            distractors = [w.strip(".,!?;:\"'()।") for w in significant if w != answer][:3]
            while len(distractors) < 3:
                distractors.append(f"Option{len(distractors)+1}")
            options = [
                {"label": "A", "text": answer, "is_correct": True},
                {"label": "B", "text": distractors[0], "is_correct": False},
                {"label": "C", "text": distractors[1], "is_correct": False},
                {"label": "D", "text": distractors[2], "is_correct": False},
            ]
            prompt = {
                "en": f"According to the lesson, which word fits: \"{' '.join(tokens[:4])} ___ ...\"?",
                "hi": "पाठ के अनुसार सही विकल्प चुनें। पहला वाक्य किस बारे में है?",
                "mr": "धड्यानुसार योग्य पर्याय निवडा. पहिले वाक्य कशाबद्दल आहे?",
            }.get(language, "What is mentioned in the first sentence?")
            if language == "hi":
                prompt = f"पाठ के अनुसार सही शब्द चुनें जो यहाँ आता है: {answer} ?"
                options = [
                    {"label": "A", "text": answer, "is_correct": True},
                    {"label": "B", "text": distractors[0], "is_correct": False},
                    {"label": "C", "text": distractors[1], "is_correct": False},
                    {"label": "D", "text": distractors[2], "is_correct": False},
                ]
            elif language == "mr":
                prompt = f"धड्यानुसार योग्य शब्द निवडा: {answer} ?"

            questions.append(
                GeneratedQuestion(
                    question_type="mcq",
                    prompt=prompt if language == "en" else prompt,
                    explanation={
                        "en": f"The lesson says: {s}",
                        "hi": f"पाठ में लिखा है: {s}",
                        "mr": f"धड्यात म्हटले आहे: {s}",
                    }.get(language, s),
                    expected_answer=answer,
                    options=options,
                )
            )

        # True/False
        if sentences:
            s = sentences[min(1, len(sentences) - 1)]
            questions.append(
                GeneratedQuestion(
                    question_type="true_false",
                    prompt={
                        "en": f"True or False: {s}",
                        "hi": f"सही या गलत: {s}",
                        "mr": f"खरे किंवा खोटे: {s}",
                    }.get(language, f"True or False: {s}"),
                    explanation={
                        "en": "This is stated in the lesson.",
                        "hi": "यह पाठ में लिखा है।",
                        "mr": "हे धड्यात दिले आहे.",
                    }.get(language, "From the lesson."),
                    expected_answer="true",
                    options=[
                        {"label": "A", "text": {"en": "True", "hi": "सही", "mr": "खरे"}.get(language, "True"), "is_correct": True},
                        {"label": "B", "text": {"en": "False", "hi": "गलत", "mr": "खोटे"}.get(language, "False"), "is_correct": False},
                    ],
                )
            )

        # Vocabulary
        if significant:
            word = significant[min(2, len(significant) - 1)].strip(".,!?;:\"'()।")
            questions.append(
                GeneratedQuestion(
                    question_type="vocabulary",
                    prompt={
                        "en": f"Which word appears in the lesson?",
                        "hi": "पाठ में कौन सा शब्द आता है?",
                        "mr": "धड्यात कोणता शब्द येतो?",
                    }.get(language, "Which word appears?"),
                    explanation={
                        "en": f"The word \"{word}\" is in the text.",
                        "hi": f"शब्द \"{word}\" पाठ में है।",
                        "mr": f"शब्द \"{word}\" धड्यात आहे.",
                    }.get(language, word),
                    expected_answer=word,
                    options=[
                        {"label": "A", "text": word, "is_correct": True},
                        {"label": "B", "text": significant[0].strip(".,!?") if significant else "apple", "is_correct": False},
                        {"label": "C", "text": "xyz123", "is_correct": False},
                        {"label": "D", "text": "qqq", "is_correct": False},
                    ],
                )
            )
            # Fix distractor B if same as answer
            if questions[-1].options[1]["text"] == word and len(significant) > 1:
                questions[-1].options[1]["text"] = significant[1].strip(".,!?")

        # Short answer
        if sentences:
            target = sentences[min(len(sentences) - 1, 2)]
            questions.append(
                GeneratedQuestion(
                    question_type="short_answer",
                    prompt={
                        "en": "In your own words, what is one important idea from this lesson?",
                        "hi": "अपने शब्दों में बताओ: इस पाठ की एक महत्वपूर्ण बात क्या है?",
                        "mr": "तुमच्या शब्दांत सांगा: या धड्यातील एक महत्त्वाची गोष्ट काय आहे?",
                    }.get(language, "What is one important idea?"),
                    explanation={
                        "en": "Any answer that reflects the lesson content is great!",
                        "hi": "पाठ से जुड़ा कोई भी सही उत्तर बहुत अच्छा है!",
                        "mr": "धड्याशी संबंधित कोणतेही उत्तर छान आहे!",
                    }.get(language, "Good try!"),
                    expected_answer=target,
                    options=[],
                )
            )

        # Fill blank
        if sentences and len(tokenize_words(sentences[0])) > 5:
            tokens = tokenize_words(sentences[0])
            blank = tokens[2].strip(".,!?;:\"'()।")
            filled = " ".join("_" if i == 2 else t for i, t in enumerate(tokens))
            questions.append(
                GeneratedQuestion(
                    question_type="fill_blank",
                    prompt={
                        "en": f"Fill in the blank: {filled}",
                        "hi": f"रिक्त स्थान भरें: {filled}",
                        "mr": f"रिकाम्या जागी भरा: {filled}",
                    }.get(language, f"Fill: {filled}"),
                    explanation={
                        "en": f"The missing word is \"{blank}\".",
                        "hi": f"सही शब्द है \"{blank}\"।",
                        "mr": f"योग्य शब्द आहे \"{blank}\".",
                    }.get(language, blank),
                    expected_answer=blank,
                    options=[],
                )
            )

        # Who/what style MCQ from title-ish content
        title = _title_from_text(source_text)
        questions.append(
            GeneratedQuestion(
                question_type="mcq",
                prompt={
                    "en": "What is this lesson mainly about?",
                    "hi": "यह पाठ मुख्य रूप से किस बारे में है?",
                    "mr": "हा धडा मुख्यतः कशाबद्दल आहे?",
                }.get(language, "What is this about?"),
                explanation={
                    "en": f"The title/theme is: {title}",
                    "hi": f"विषय है: {title}",
                    "mr": f"विषय आहे: {title}",
                }.get(language, title),
                expected_answer=title,
                options=[
                    {"label": "A", "text": title[:60], "is_correct": True},
                    {"label": "B", "text": {"en": "Cooking recipes", "hi": "खाना पकाना", "mr": " स्वयंपाक"}.get(language, "Cooking"), "is_correct": False},
                    {"label": "C", "text": {"en": "Sports scores", "hi": "खेल स्कोर", "mr": "खेळाचे गुण"}.get(language, "Sports"), "is_correct": False},
                    {"label": "D", "text": {"en": "Weather report", "hi": "मौसम", "mr": "हवामान"}.get(language, "Weather"), "is_correct": False},
                ],
            )
        )

        return questions[:count]

    async def evaluate_answer(
        self,
        question: str,
        expected: str,
        student_answer: str,
        language: str,
    ) -> EvaluationResult:
        exp = (expected or "").strip().lower()
        ans = (student_answer or "").strip().lower()
        if not ans:
            return EvaluationResult(
                correct=False,
                score=0,
                feedback={
                    "en": "Try writing an answer — I believe in you!",
                    "hi": "एक उत्तर लिखने की कोशिश करो — तुम कर सकते हो!",
                    "mr": "उत्तर लिहिण्याचा प्रयत्न करा — तुम्ही करू शकता!",
                }.get(language, "Try again!"),
                expected_answer=expected,
            )

        if ans == exp or exp in ans or ans in exp:
            return EvaluationResult(
                correct=True,
                score=1,
                feedback={
                    "en": "Excellent! That matches the lesson.",
                    "hi": "बहुत बढ़िया! यह पाठ से मेल खाता है।",
                    "mr": "उत्तम! हे धड्याशी जुळते.",
                }.get(language, "Great!"),
                expected_answer=expected,
            )

        exp_tokens = set(tokenize_words(exp))
        ans_tokens = set(tokenize_words(ans))
        if not exp_tokens:
            return EvaluationResult(correct=True, score=1, feedback="Nice effort!", expected_answer=expected)

        overlap = len(exp_tokens & ans_tokens) / len(exp_tokens)
        if overlap >= 0.4:
            return EvaluationResult(
                correct=True,
                score=1,
                feedback={
                    "en": "Great thinking! Your answer shows you understood.",
                    "hi": "शानदार! तुम्हें समझ आ गया।",
                    "mr": "छान! तुम्हाला समजले आहे.",
                }.get(language, "Great!"),
                expected_answer=expected,
            )

        return EvaluationResult(
            correct=False,
            score=0,
            feedback={
                "en": f"Almost! A good answer is: {expected}",
                "hi": f"लगभग सही! अच्छा उत्तर है: {expected}",
                "mr": f"जवळजवळ! चांगले उत्तर आहे: {expected}",
            }.get(language, f"Try: {expected}"),
            expected_answer=expected,
        )


async def _openai_json(messages: list[dict[str, str]], api_key: str) -> Any:
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "gpt-4o-mini", "messages": messages, "response_format": {"type": "json_object"}},
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)


async def _gemini_json(prompt: str, api_key: str) -> Any:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}})
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


def _questions_from_payload(payload: dict[str, Any]) -> list[GeneratedQuestion]:
    out: list[GeneratedQuestion] = []
    for q in payload.get("questions", []):
        out.append(
            GeneratedQuestion(
                question_type=q.get("question_type", "mcq"),
                prompt=q["prompt"],
                explanation=q.get("explanation", ""),
                expected_answer=q.get("expected_answer"),
                options=q.get("options") or [],
                points=float(q.get("points", 1)),
            )
        )
    return out


class OpenAIProvider(AIProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._local = LocalAIProvider()

    async def structure_content(self, raw_text: str, language_hint: str | None = None) -> StructuredContent:
        if not self.settings.openai_api_key:
            return await self._local.structure_content(raw_text, language_hint)
        try:
            data = await _openai_json(
                [
                    {"role": "system", "content": content_prompts.SYSTEM},
                    {"role": "user", "content": content_prompts.user_prompt(raw_text, language_hint)},
                ],
                self.settings.openai_api_key,
            )
            return StructuredContent(
                title=data.get("title") or _title_from_text(raw_text),
                language=data.get("language") or detect_script_language(raw_text),
                content_type=data.get("content_type") or _classify_content(raw_text),
                summary=data.get("summary") or "",
                cleaned_text=data.get("cleaned_text") or raw_text,
                meta={"provider": "openai"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("openai_structure_failed err=%s", exc)
            return await self._local.structure_content(raw_text, language_hint)

    async def generate_questions(self, source_text: str, language: str, *, difficulty: str, class_level: int, count: int) -> list[GeneratedQuestion]:
        if not self.settings.openai_api_key:
            return await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)
        try:
            data = await _openai_json(
                [
                    {"role": "system", "content": quiz_prompts.SYSTEM},
                    {
                        "role": "user",
                        "content": quiz_prompts.user_prompt(
                            source_text, language, difficulty=difficulty, class_level=class_level, count=count
                        ),
                    },
                ],
                self.settings.openai_api_key,
            )
            qs = _questions_from_payload(data)
            return qs or await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)
        except Exception as exc:  # noqa: BLE001
            logger.exception("openai_quiz_failed err=%s", exc)
            return await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)

    async def evaluate_answer(self, question: str, expected: str, student_answer: str, language: str) -> EvaluationResult:
        if not self.settings.openai_api_key:
            return await self._local.evaluate_answer(question, expected, student_answer, language)
        try:
            data = await _openai_json(
                [
                    {"role": "system", "content": eval_prompts.SYSTEM},
                    {"role": "user", "content": eval_prompts.user_prompt(question, expected, student_answer, language)},
                ],
                self.settings.openai_api_key,
            )
            return EvaluationResult(
                correct=bool(data.get("correct")),
                score=float(data.get("score", 0)),
                feedback=data.get("feedback") or "",
                expected_answer=data.get("expected_answer") or expected,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("openai_eval_failed err=%s", exc)
            return await self._local.evaluate_answer(question, expected, student_answer, language)


class GeminiProvider(AIProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._local = LocalAIProvider()

    async def structure_content(self, raw_text: str, language_hint: str | None = None) -> StructuredContent:
        if not self.settings.google_ai_api_key:
            return await self._local.structure_content(raw_text, language_hint)
        try:
            prompt = content_prompts.SYSTEM + "\n\n" + content_prompts.user_prompt(raw_text, language_hint)
            data = await _gemini_json(prompt, self.settings.google_ai_api_key)
            return StructuredContent(
                title=data.get("title") or _title_from_text(raw_text),
                language=data.get("language") or detect_script_language(raw_text),
                content_type=data.get("content_type") or _classify_content(raw_text),
                summary=data.get("summary") or "",
                cleaned_text=data.get("cleaned_text") or raw_text,
                meta={"provider": "gemini"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("gemini_structure_failed err=%s", exc)
            return await self._local.structure_content(raw_text, language_hint)

    async def generate_questions(self, source_text: str, language: str, *, difficulty: str, class_level: int, count: int) -> list[GeneratedQuestion]:
        if not self.settings.google_ai_api_key:
            return await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)
        try:
            prompt = quiz_prompts.SYSTEM + "\n\n" + quiz_prompts.user_prompt(
                source_text, language, difficulty=difficulty, class_level=class_level, count=count
            )
            data = await _gemini_json(prompt, self.settings.google_ai_api_key)
            qs = _questions_from_payload(data)
            return qs or await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)
        except Exception as exc:  # noqa: BLE001
            logger.exception("gemini_quiz_failed err=%s", exc)
            return await self._local.generate_questions(source_text, language, difficulty=difficulty, class_level=class_level, count=count)

    async def evaluate_answer(self, question: str, expected: str, student_answer: str, language: str) -> EvaluationResult:
        if not self.settings.google_ai_api_key:
            return await self._local.evaluate_answer(question, expected, student_answer, language)
        try:
            prompt = eval_prompts.SYSTEM + "\n\n" + eval_prompts.user_prompt(question, expected, student_answer, language)
            data = await _gemini_json(prompt, self.settings.google_ai_api_key)
            return EvaluationResult(
                correct=bool(data.get("correct")),
                score=float(data.get("score", 0)),
                feedback=data.get("feedback") or "",
                expected_answer=data.get("expected_answer") or expected,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("gemini_eval_failed err=%s", exc)
            return await self._local.evaluate_answer(question, expected, student_answer, language)

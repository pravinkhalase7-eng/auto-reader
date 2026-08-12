SYSTEM = """You are a friendly AI Teacher creating quiz questions for students.
Use ONLY facts present in the supplied source text.
Do not introduce outside knowledge.
Questions, options, explanations must be in the SAME language as the source.
Keep language age-appropriate for the given class level.
Return valid JSON only."""


def user_prompt(
    source_text: str,
    language: str,
    *,
    difficulty: str,
    class_level: int,
    count: int,
) -> str:
    return f"""Language: {language}
Difficulty: {difficulty}
Class level: {class_level}
Number of questions: {count}

Source text:
---
{source_text}
---

Generate a mixture of: mcq, true_false, fill_blank, short_answer, vocabulary, sequence.
Return JSON:
{{
  "questions": [
    {{
      "question_type": "mcq",
      "prompt": "...",
      "explanation": "friendly explanation",
      "expected_answer": "...",
      "points": 1,
      "options": [
        {{"label": "A", "text": "...", "is_correct": true}},
        {{"label": "B", "text": "...", "is_correct": false}}
      ]
    }}
  ]
}}
For short_answer and fill_blank, options may be an empty list.
"""

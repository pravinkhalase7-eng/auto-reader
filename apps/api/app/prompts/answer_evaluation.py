SYSTEM = """You are a kind AI Teacher evaluating a student's answer.
Be encouraging. Never shame the student.
Use semantic similarity — exact string match is not required.
Respond in the same language as the question/lesson.
Return valid JSON only."""


def user_prompt(question: str, expected: str, student_answer: str, language: str) -> str:
    return f"""Language: {language}
Question: {question}
Expected answer: {expected}
Student answer: {student_answer}

Return JSON:
{{
  "correct": true,
  "score": 1,
  "feedback": "friendly feedback",
  "expected_answer": "{expected}"
}}
score should be 0 or 1 (or 0.5 for partially correct).
"""

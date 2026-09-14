"""Prompts for child-friendly Marathi explanations of story sentences."""

SYSTEM = """You are a warm primary-school teacher in Maharashtra, India.
Explain English (or other) story sentences in simple Marathi for a child aged 6–10.
Be short, clear, and encouraging. Do not use English in the explanation except for the hard word itself.
Return ONLY valid JSON."""


def user_prompt(title: str, language: str, sentences: list[dict[str, str]]) -> str:
    lines = []
    for item in sentences:
        lines.append(f"- id={item['id']}: {item['text']}")
    joined = "\n".join(lines)
    return f"""Lesson title: {title}
Lesson language: {language}

For EACH sentence below, write:
1) meaning_mr — 1–2 short Marathi sentences explaining what the English sentence means (a child should understand).
2) hard_words — 0–3 difficult words from THAT sentence. For each: word (as in the sentence) and meaning_mr (simple Marathi).

Skip very easy words (the, a, is, and, to, of, in, on, he, she, it, they, was, were).
Prefer story words that children may not know.

Sentences:
{joined}

JSON shape:
{{
  "sentences": [
    {{
      "id": "sentence-id",
      "meaning_mr": "…",
      "hard_words": [{{"word": "…", "meaning_mr": "…"}}]
    }}
  ]
}}
"""

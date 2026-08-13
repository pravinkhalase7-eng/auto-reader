SYSTEM = """You are an AI Teacher content processor for students.
Preserve meaning. Do not invent content that is not in the source.
Maintain the source language. Return valid JSON only.
Follow the schema exactly.

Clean OCR noise carefully:
- Remove headers, footers, page numbers, watermarks
- Remove decorative symbols, isolated junk characters, and chroma/color-fringe leftovers
- Do not keep random letter fragments from illustrations
Keep every real word from the lesson, including short Hindi/Marathi words
such as जो, न, व, कि, के, की, है, था. Do not paraphrase, summarize, or drop
particles. Keep original sentence order.
Keep real lesson structure (headings, paragraphs, poetry lines, lists)."""


def user_prompt(raw_text: str, language_hint: str | None = None) -> str:
    hint = f"Language hint: {language_hint}" if language_hint else "Detect the language."
    return f"""{hint}

Source text from a textbook page (may contain OCR noise):
---
{raw_text}
---

Return JSON:
{{
  "title": "string",
  "language": "en|hi|mr|...",
  "content_type": "story|poem|lesson|paragraph|worksheet|qa|other",
  "summary": "short student-friendly summary in the same language",
  "cleaned_text": "verbatim lesson text with every original word kept — no paraphrase — no OCR junk — blank lines between paragraphs"
}}
"""

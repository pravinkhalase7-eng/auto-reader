SYSTEM = """Write a short, warm summary for a student about what they just read.
Stay in the source language. Do not invent facts."""


def user_prompt(text: str, language: str) -> str:
    return f"Language: {language}\n\nText:\n{text}\n\nReturn JSON: {{\"summary\": \"...\"}}"

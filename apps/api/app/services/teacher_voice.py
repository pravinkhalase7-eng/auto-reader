STEP_MESSAGES = {
    "queued": "I'm getting ready to look at your page...",
    "uploaded": "I've got your photo!",
    "preprocessing": "I'm making your photo clearer...",
    "ocr": "I'm reading your textbook page...",
    "understanding": "I'm understanding the content...",
    "language": "I'm detecting the language...",
    "preparing_lesson": "I'm preparing your lesson...",
    "preparing_teacher": "I'm preparing your AI Teacher...",
    "tts": "I'm practicing how to read this aloud...",
    "quiz": "I'm preparing some questions for you...",
    "completed": "Your lesson is ready!",
    "failed": "I ran into a problem. Let's try again.",
}


def message_for_step(step: str) -> str:
    return STEP_MESSAGES.get(step, "Working on your lesson...")

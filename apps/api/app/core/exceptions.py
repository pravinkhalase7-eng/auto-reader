from fastapi import HTTPException, status


class AppError(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "I couldn't find that lesson.", code: str = "NOT_FOUND"):
        super().__init__(message, code=code, status_code=404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Please sign in to continue.", code: str = "UNAUTHORIZED"):
        super().__init__(message, code=code, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "You don't have access to this.", code: str = "FORBIDDEN"):
        super().__init__(message, code=code, status_code=403)


def to_http_exception(exc: AppError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"detail": exc.message, "code": exc.code},
    )


FRIENDLY_MESSAGES = {
    "INVALID_IMAGE": "That file doesn't look like a photo I can read. Try a JPG or PNG.",
    "IMAGE_TOO_LARGE": "That photo is a bit too big. Try one under 15 MB.",
    "OCR_FAILED": "I couldn't read this page clearly. Let's try another photo that's brighter and sharper.",
    "EMPTY_CONTENT": "I couldn't find any text on this page. Try a clearer photo of the page.",
    "AI_FAILED": "I had trouble understanding this page. Let's try again in a moment.",
    "TTS_FAILED": "I couldn't prepare the narration right now. You can still read the lesson.",
    "QUIZ_FAILED": "I couldn't prepare questions just yet. Let's try again.",
    "UNSUPPORTED_LANGUAGE": "I'm still learning that language. English, Hindi, and Marathi work best for now.",
}

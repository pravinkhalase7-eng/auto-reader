from app.providers.base import TTSProvider, TTSResult
from app.utils.languages import get_language
from app.utils.word_timing import estimate_word_timings


class LocalTTSProvider(TTSProvider):
    """Server-side stub: returns estimated word timings; client uses browser speech synthesis."""

    async def synthesize(
        self,
        text: str,
        language: str,
        *,
        speed: str = "slow",
        voice: str | None = None,
        words: list[tuple[str, str]] | None = None,
    ) -> TTSResult:
        lang = get_language(language)
        word_list = words or []
        timings = estimate_word_timings(word_list, speed=speed)
        duration = timings[-1].end_ms if timings else max(1000, len(text) * 50)
        return TTSResult(
            audio_bytes=None,
            duration_ms=duration,
            provider="browser",
            voice=voice or lang.tts_code,
            word_timings=[
                {"word_id": t.word_id, "text": t.text, "start_ms": t.start_ms, "end_ms": t.end_ms}
                for t in timings
            ],
        )


class GoogleTTSProvider(LocalTTSProvider):
    """Placeholder for Google Cloud TTS with SSML marks / timepoints."""

    async def synthesize(self, text: str, language: str, *, speed: str = "slow", voice: str | None = None, words: list[tuple[str, str]] | None = None) -> TTSResult:
        result = await super().synthesize(text, language, speed=speed, voice=voice, words=words)
        result.provider = "google-fallback"
        return result


class OpenAITTSProvider(LocalTTSProvider):
    async def synthesize(self, text: str, language: str, *, speed: str = "slow", voice: str | None = None, words: list[tuple[str, str]] | None = None) -> TTSResult:
        result = await super().synthesize(text, language, speed=speed, voice=voice, words=words)
        result.provider = "openai-fallback"
        return result

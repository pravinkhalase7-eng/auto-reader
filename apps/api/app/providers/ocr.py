"""OCR providers — real image text extraction with optional Vision APIs."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import AppError, FRIENDLY_MESSAGES
from app.providers.base import OCRProvider, OCRResult
from app.utils.ocr_clean import clean_ocr_text

logger = logging.getLogger(__name__)


# Used only by seed/demo helpers — never returned for real uploads.
DEMO_TEXTS: dict[str, str] = {
    "lion": """The Lion and the Mouse

One day, a lion was sleeping in the forest. A little mouse ran over his paw.
The lion woke up and caught the mouse. The mouse said, "Please let me go. I may help you someday."
The lion laughed and let the mouse go.

Later, the lion was caught in a hunter's net. The mouse chewed the ropes and set the lion free.
The lion thanked the mouse. They became friends.

Moral: Kindness is never wasted.""",
    "hindi": """शेर और चूहा

एक दिन जंगल में एक शेर सो रहा था। एक छोटा चूहा उसकी पूंछ पर दौड़ गया।
शेर जाग गया और चूहे को पकड़ लिया। चूहे ने कहा, "मुझे छोड़ दो। एक दिन मैं तुम्हारी मदद करूँगा।"
शेर हँसा और चूहे को छोड़ दिया।

बाद में शेर शिकारी के जाल में फँस गया। चूहे ने रस्सियाँ काट दीं और शेर को मुक्त कर दिया।
शेर ने चूहे का धन्यवाद किया। दोनों मित्र बन गए।

नीति: दया कभी व्यर्थ नहीं जाती।""",
    "marathi": """सिंह आणि उंदीर

एक दिवस जंगलात एक सिंह झोपला होता. एक छोटा उंदीर त्याच्या पायावरून पळाला.
सिंह जागा झाला आणि उंदरांना पकडले. उंदीर म्हणाला, "मला सोडून द्या. एक दिवस मी तुमची मदत करेन."
सिंह हसला आणि उंदरांना सोडले.

नंतर सिंह शिकारीच्या जाळ्यात अडकला. उंदीराने दोरी चावून सिंहाला मुक्त केले.
सिंहाने उंदराचे आभार मानले. ते मित्र झाले.

नीति: दया कधीही वाया जात नाही.""",
    "poem": """Twinkle Little Star

Twinkle, twinkle, little star,
How I wonder what you are!
Up above the world so high,
Like a diamond in the sky.

When the blazing sun is gone,
When he nothing shines upon,
Then you show your little light,
Twinkle, twinkle, all the night.""",
}


def _available_tess_langs() -> set[str]:
    try:
        import pytesseract

        langs = pytesseract.get_languages(config="")
        return set(langs)
    except Exception:  # noqa: BLE001
        return set()


def _tess_lang_string(language_hint: str | None = None) -> str:
    available = _available_tess_langs()
    preferred: list[str] = []

    if language_hint == "hi":
        preferred = ["hin", "eng"]
    elif language_hint == "mr":
        preferred = ["mar", "hin", "eng"]
    else:
        # Auto: try Indic + English so mixed textbook pages work
        preferred = ["eng", "hin", "mar"]

    chosen = [lang for lang in preferred if lang in available]
    if not chosen:
        if "eng" in available:
            return "eng"
        return "+".join(sorted(available)[:3]) if available else "eng"
    # Keep order but unique
    seen: list[str] = []
    for lang in preferred:
        if lang in available and lang not in seen:
            seen.append(lang)
    return "+".join(seen)


def _text_from_tesseract_data(data: dict, min_conf: int = 25) -> tuple[str, float]:
    """Rebuild text from confident words only, preserving line breaks."""
    n = len(data.get("text") or [])
    lines: list[str] = []
    current: list[str] = []
    last_key: tuple[int, int, int] | None = None
    confs: list[int] = []

    for i in range(n):
        raw = (data["text"][i] or "").strip()
        try:
            conf = int(float(data["conf"][i]))
        except (TypeError, ValueError):
            conf = -1
        if not raw or conf < min_conf:
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        if last_key is not None and key != last_key:
            if current:
                lines.append(" ".join(current))
            current = []
        current.append(raw)
        confs.append(conf)
        last_key = key

    if current:
        lines.append(" ".join(current))

    text = "\n".join(lines)
    avg = (sum(confs) / len(confs) / 100.0) if confs else 0.0
    return text, avg


def _prepare_ocr_image(image):
    """Sharpen phone photos so small Hindi words are not dropped."""
    from PIL import ImageEnhance, ImageOps

    img = image.convert("RGB")
    width, height = img.size
    shortest = min(width, height)
    if shortest < 1400:
        scale = 1400 / shortest
        img = img.resize((int(width * scale), int(height * scale)))
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img


def _pick_richer_ocr(data_text: str, full_text: str) -> str:
    def score(text: str) -> int:
        return sum(1 for c in text if c.isalpha() or "\u0900" <= c <= "\u097F")

    if score(full_text) > score(data_text) * 1.08:
        return full_text
    return data_text or full_text


class LocalOCRProvider(OCRProvider):
    """Extract text from uploaded images via Tesseract. Never invents demo stories."""

    async def extract_text(self, image_path: Path, language_hint: str | None = None) -> OCRResult:
        if not image_path.exists():
            raise AppError(FRIENDLY_MESSAGES["OCR_FAILED"], code="OCR_FAILED")

        if not shutil.which("tesseract"):
            logger.error("tesseract_binary_missing")
            raise AppError(
                "I couldn't read this page yet. Please install Tesseract OCR on this computer, "
                "or set OCR_PROVIDER=openai with an API key.",
                code="OCR_UNAVAILABLE",
            )

        try:
            from PIL import Image
            import pytesseract
        except ImportError as exc:
            logger.error("pytesseract_missing err=%s", exc)
            raise AppError(
                "I couldn't read this page yet. Please install the pytesseract package.",
                code="OCR_UNAVAILABLE",
            ) from exc

        try:
            lang = _tess_lang_string(language_hint)
            image = _prepare_ocr_image(Image.open(image_path))
            config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
            min_conf = 20 if "hin" in lang or "mar" in lang else 40
            data = pytesseract.image_to_data(
                image,
                lang=lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
            text_data, avg_conf = _text_from_tesseract_data(data, min_conf=min_conf)
            text_full = pytesseract.image_to_string(image, lang=lang, config=config)
            text = _pick_richer_ocr(text_data, text_full)
            cleaned = clean_ocr_text(text)
            logger.info(
                "ocr_complete path=%s lang=%s chars=%s conf=%.2f",
                image_path.name,
                lang,
                len(cleaned),
                avg_conf,
            )
            if not cleaned:
                raise AppError(FRIENDLY_MESSAGES["EMPTY_CONTENT"], code="EMPTY_CONTENT")
            return OCRResult(
                text=cleaned,
                confidence=max(avg_conf, 0.5),
                meta={"engine": "tesseract", "lang": lang, "avg_conf": round(avg_conf, 3)},
            )
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("ocr_failed path=%s", image_path)
            raise AppError(FRIENDLY_MESSAGES["OCR_FAILED"], code="OCR_FAILED") from exc


class OpenAIOCRProvider(OCRProvider):
    async def extract_text(self, image_path: Path, language_hint: str | None = None) -> OCRResult:
        settings = get_settings()
        if not settings.openai_api_key:
            logger.warning("openai_ocr_missing_key falling_back=local")
            return await LocalOCRProvider().extract_text(image_path, language_hint)

        import base64
        import httpx

        data = base64.b64encode(image_path.read_bytes()).decode()
        suffix = image_path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract ONLY the printed educational text from this textbook/worksheet page. "
                                "Copy wording exactly. Preserve headings, paragraphs, poetry line breaks, and lists. "
                                "Ignore illustrations, photos, decorative borders, color bars, watermarks, "
                                "headers/footers, page numbers, and chromatic/color noise. "
                                "Do not invent or replace the story. Return plain text only in the same language."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                    ],
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json=payload,
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
            cleaned = clean_ocr_text(text or "")
            if not cleaned:
                raise AppError(FRIENDLY_MESSAGES["EMPTY_CONTENT"], code="EMPTY_CONTENT")
            return OCRResult(text=cleaned, confidence=0.9, meta={"engine": "openai"})
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("openai_ocr_failed")
            raise AppError(FRIENDLY_MESSAGES["OCR_FAILED"], code="OCR_FAILED") from exc


class GoogleOCRProvider(OCRProvider):
    async def extract_text(self, image_path: Path, language_hint: str | None = None) -> OCRResult:
        logger.warning("google_ocr_not_configured falling_back=local")
        return await LocalOCRProvider().extract_text(image_path, language_hint)

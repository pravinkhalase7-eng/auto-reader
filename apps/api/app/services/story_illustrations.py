"""Plan story scenes and draw them with Gemini in parallel (or a local placeholder)."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import time
from dataclasses import dataclass

import httpx
from PIL import Image, ImageDraw
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Lesson, LessonIllustration
from app.providers.factory import get_storage_provider
from app.utils.segmentation import split_sentences

logger = logging.getLogger(__name__)

STYLE_PREFIX = (
    "Children's storybook watercolor, bright and kind, no text in the image."
)

TEXT_MODELS = (
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
)

IMAGE_MODELS = (
    "gemini-2.5-flash-image",  # Nano Banana — fastest / most available
    "gemini-3.1-flash-lite-image",
    "gemini-3.1-flash-image",
)
DRAW_CONCURRENCY = 2
IMAGE_TIMEOUT = httpx.Timeout(connect=10.0, read=50.0, write=20.0, pool=10.0)


@dataclass
class ScenePlan:
    position: int
    caption: str
    visual: str
    characters: str = ""


def plan_scenes_local(text: str, title: str, language: str, max_scenes: int = 4) -> list[ScenePlan]:
    """Split the story into an even sequence of picture moments."""
    sentences = [s.strip() for s in split_sentences(text or "") if s.strip()]
    if not sentences:
        chunk = (text or title or "A story").strip()[:180]
        sentences = [chunk] if chunk else ["A kind story for children."]

    count = min(max_scenes, max(3, min(len(sentences), 6)))
    groups: list[list[str]] = [[] for _ in range(count)]
    for i, sentence in enumerate(sentences):
        groups[min(count - 1, i * count // max(len(sentences), 1))].append(sentence)
    groups = [g or [sentences[min(i, len(sentences) - 1)]] for i, g in enumerate(groups)]

    scenes: list[ScenePlan] = []
    for i, group in enumerate(groups):
        caption = " ".join(group)
        if len(caption) > 220:
            caption = caption[:217].rsplit(" ", 1)[0] + "…"
        scenes.append(
            ScenePlan(
                position=i,
                caption=caption,
                visual=f"Scene {i + 1} of {count} from the story '{title}': {caption}",
                characters="the same story characters in every picture",
            )
        )
    return scenes


def _extract_json_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    return json.loads(raw)


def _gemini_headers(api_key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "x-goog-api-key": api_key}


def _gemini_url(model: str, action: str = "generateContent") -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}"


async def plan_scenes_gemini(text: str, title: str, language: str, api_key: str) -> list[ScenePlan]:
    prompt = f"""You illustrate a children's textbook story as a short picture sequence.

Return JSON only:
{{
  "characters": "one sentence describing the main characters so every picture matches",
  "scenes": [
    {{"caption": "1-2 sentences in the story language ({language}) that this picture shows",
      "visual": "English visual description of what to draw, no text in the image"}}
  ]
}}

Rules:
- Exactly 4 scenes, in story order, beginning to end.
- Captions must follow the plot so a child can relate picture to text.
- Keep characters consistent.
- Kind, age 6-10, no scary or violent images.

Title: {title}
Story:
{text[:4000]}
"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    raw = ""
    timeout = httpx.Timeout(connect=8.0, read=12.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in TEXT_MODELS[:2]:
            try:
                resp = await client.post(
                    _gemini_url(model),
                    headers=_gemini_headers(api_key),
                    json=body,
                )
            except httpx.TimeoutException:
                logger.warning("scene_plan_timeout model=%s", model)
                break
            if resp.status_code >= 400:
                logger.warning("scene_plan_http model=%s status=%s", model, resp.status_code)
                continue
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            break
    if not raw:
        return plan_scenes_local(text, title, language)
    data = _extract_json_object(raw)
    characters = str(data.get("characters") or "the same friendly story characters")
    scenes: list[ScenePlan] = []
    for i, item in enumerate((data.get("scenes") or [])[:4]):
        caption = str(item.get("caption") or "").strip()
        visual = str(item.get("visual") or caption).strip()
        if not caption and not visual:
            continue
        scenes.append(
            ScenePlan(
                position=i,
                caption=caption or visual,
                visual=visual or caption,
                characters=characters,
            )
        )
    return scenes or plan_scenes_local(text, title, language)


def _blob(draw, box: tuple[int, int, int, int], fill: tuple[int, int, int], outline=None):
    draw.ellipse(box, fill=fill, outline=outline)


def render_placeholder_png(
    caption: str,
    position: int,
    total: int,
    title: str,
    visual: str = "",
) -> bytes:
    """Story-shaped picture so each scene looks different when Gemini image quota is unavailable."""
    text = f"{title} {caption} {visual}".lower()
    width, height = 1024, 640
    night = any(w in text for w in ("night", "dark", "moon", "रात", "रात्री"))
    sunset = any(w in text for w in ("sunset", "evening", "angry", "fire", "शाम"))
    sky = (28, 49, 94) if night else ((255, 176, 96) if sunset else (135, 206, 235))
    ground = (46, 89, 56) if "river" in text or "sea" in text else (120, 176, 86)
    img = Image.new("RGB", (width, height), sky)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 430, width, height), fill=ground)
    if night:
        _blob(draw, (780, 40, 920, 180), (245, 245, 210))
    else:
        _blob(draw, (760, 30, 930, 200), (255, 220, 90))

    if any(w in text for w in ("tree", "forest", "jungle", "पेड़", "झाड")):
        draw.rectangle((120, 300, 160, 470), fill=(110, 70, 40))
        draw.ellipse((50, 160, 230, 360), fill=(46, 130, 70))
        draw.rectangle((860, 320, 900, 470), fill=(110, 70, 40))
        draw.ellipse((790, 180, 970, 380), fill=(40, 120, 65))

    if any(w in text for w in ("house", "school", "village", "घर", "शाळा")):
        draw.rectangle((700, 280, 940, 470), fill=(244, 211, 150))
        draw.polygon([(680, 280), (820, 160), (960, 280)], fill=(196, 80, 70))
        draw.rectangle((790, 360, 850, 470), fill=(120, 70, 40))

    if any(w in text for w in ("net", "trap", "cage", "rope", "जाल")):
        for x in range(380, 700, 28):
            draw.line((x, 220, x, 500), fill=(90, 90, 90), width=4)
        for y in range(220, 500, 28):
            draw.line((380, y, 700, y), fill=(90, 90, 90), width=4)

    # Main character
    cx = 280 + position * 70
    if any(w in text for w in ("lion", "tiger", "शेर", "सिंह")):
        _blob(draw, (cx, 300, cx + 220, 520), (230, 150, 50))
        _blob(draw, (cx + 40, 210, cx + 180, 360), (210, 120, 40))
        _blob(draw, (cx + 70, 250, cx + 110, 290), (40, 30, 20))
        _blob(draw, (cx + 130, 250, cx + 170, 290), (40, 30, 20))
    elif any(w in text for w in ("elephant", "हाथी", "हत्ती")):
        _blob(draw, (cx, 280, cx + 260, 520), (170, 170, 180))
        _blob(draw, (cx + 160, 220, cx + 250, 330), (170, 170, 180))
        draw.rectangle((cx + 230, 300, cx + 255, 480), fill=(150, 150, 160))
    else:
        _blob(draw, (cx, 320, cx + 160, 520), (80, 140, 200) if position % 2 else (200, 90, 90))
        _blob(draw, (cx + 30, 230, cx + 130, 340), (255, 214, 170))

    if any(w in text for w in ("mouse", "rat", "चूहा", "उंदीर")):
        mx = 620 + position * 20
        _blob(draw, (mx, 470, mx + 90, 530), (160, 160, 165))
        _blob(draw, (mx + 70, 455, mx + 115, 500), (160, 160, 165))
        draw.arc((mx - 40, 500, mx + 20, 560), 0, 180, fill=(120, 120, 125), width=4)

    if any(w in text for w in ("bird", "पक्षी", "चिड़िया")):
        _blob(draw, (500, 120, 580, 170), (240, 90, 90))
        draw.polygon([(580, 145), (640, 120), (580, 160)], fill=(220, 70, 70))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _inline_image_bytes(payload: dict) -> bytes | None:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return None
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data") or {}
        data = inline.get("data")
        if data:
            return base64.b64decode(data)
    return None


async def generate_gemini_image(
    prompt: str,
    api_key: str,
    preferred_model: str,
    reference_png: bytes | None = None,
    client: httpx.AsyncClient | None = None,
) -> bytes | None:
    del reference_png  # keep callsites stable; extra images make requests slow
    models: list[str] = []
    for name in (*IMAGE_MODELS, preferred_model):
        if name and name not in models:
            models.append(name)
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=IMAGE_TIMEOUT)
    try:
        for model in models:
            for attempt in range(2):
                try:
                    resp = await client.post(
                        _gemini_url(model),
                        headers=_gemini_headers(api_key),
                        json=body,
                    )
                except httpx.TimeoutException:
                    logger.warning("gemini_image_timeout model=%s attempt=%s", model, attempt + 1)
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.warning("gemini_image_failed model=%s err=%r", model, exc)
                    break
                if resp.status_code in {429, 503}:
                    logger.warning(
                        "gemini_image_busy model=%s status=%s attempt=%s",
                        model,
                        resp.status_code,
                        attempt + 1,
                    )
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                if resp.status_code in {400, 404}:
                    detail = ""
                    try:
                        detail = str(resp.json().get("error", {}).get("message") or "")[:180]
                    except Exception:
                        detail = ""
                    logger.warning(
                        "gemini_image_http model=%s status=%s detail=%s",
                        model,
                        resp.status_code,
                        detail,
                    )
                    break
                if resp.status_code >= 400:
                    logger.warning("gemini_image_http model=%s status=%s", model, resp.status_code)
                    break
                image = _inline_image_bytes(resp.json())
                if image:
                    logger.info("gemini_image_ok model=%s bytes=%s", model, len(image))
                    return image
                logger.warning("gemini_image_no_bytes model=%s", model)
                break
    finally:
        if owns_client:
            await client.aclose()
    return None


def image_prompt(scene: ScenePlan, title: str, total: int, has_previous: bool = False) -> str:
    continuity = (
        " Keep the same characters, clothing, faces, and watercolor style as the previous picture. "
        "Draw the next moment, not a copy of the last picture."
        if has_previous
        else ""
    )
    return (
        f"{STYLE_PREFIX} "
        f"Story title: {title}. "
        f"Keep these characters identical in every frame: {scene.characters}. "
        f"This is picture {scene.position + 1} of {total}, in sequence.{continuity} "
        f"Draw: {scene.visual}"
    )


async def _prepare_illustration_files(
    lesson_id: str,
    title: str,
    language: str,
    story: str,
    *,
    prefer_gemini: bool,
    persist_each: bool = False,
    skip_positions: set[int] | None = None,
) -> list[tuple[ScenePlan, str, str, str]]:
    settings = get_settings()
    story = (story or "").strip()
    if not story:
        return []

    use_gemini = prefer_gemini and bool(settings.google_ai_api_key)
    logger.info(
        "illustration_draw_start lesson_id=%s gemini=%s model=%s",
        lesson_id,
        use_gemini,
        settings.gemini_image_model,
    )
    if prefer_gemini and not use_gemini:
        logger.warning("gemini_key_missing lesson_id=%s", lesson_id)
        return []

    scenes: list[ScenePlan] = []
    if use_gemini:
        try:
            scenes = await plan_scenes_gemini(story, title, language, settings.google_ai_api_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scene_plan_gemini_failed err=%s", exc)
    if not scenes:
        scenes = plan_scenes_local(story, title, language)

    skip = skip_positions or set()
    total = len(scenes)
    pending = [scene for scene in scenes if scene.position not in skip]
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
    gate = asyncio.Semaphore(DRAW_CONCURRENCY)

    async def _draw_limited(scene: ScenePlan):
        async with gate:
            return await _draw_one_scene(
                lesson_id,
                scene,
                title,
                total,
                use_gemini=use_gemini,
                persist_each=persist_each,
                client=client,
            )

    async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, limits=limits) as client:
        logger.info(
            "illustration_draw_parallel lesson_id=%s scenes=%s concurrency=%s",
            lesson_id,
            len(pending),
            DRAW_CONCURRENCY,
        )
        results = await asyncio.gather(
            *[_draw_limited(scene) for scene in pending],
            return_exceptions=True,
        )
    prepared: list[tuple[ScenePlan, str, str, str]] = []
    for item in results:
        if isinstance(item, Exception):
            logger.warning("illustration_scene_failed err=%r", item)
            continue
        if item:
            prepared.append(item)
    prepared.sort(key=lambda row: row[0].position)
    return prepared


_persist_lock = asyncio.Lock()


async def _draw_one_scene(
    lesson_id: str,
    scene: ScenePlan,
    title: str,
    total: int,
    *,
    use_gemini: bool,
    persist_each: bool,
    client: httpx.AsyncClient | None = None,
) -> tuple[ScenePlan, str, str, str] | None:
    settings = get_settings()
    storage = get_storage_provider()
    prompt = image_prompt(scene, title, total)
    png: bytes | None = None
    provider = "local"
    if use_gemini:
        png = await generate_gemini_image(
            prompt,
            settings.google_ai_api_key,
            settings.gemini_image_model,
            client=client,
        )
        if png:
            provider = "gemini"
        else:
            logger.warning(
                "gemini_image_unavailable lesson_id=%s scene=%s",
                lesson_id,
                scene.position + 1,
            )
            return None
    if not png:
        png = render_placeholder_png(scene.caption, scene.position, total, title, scene.visual)
    key = f"illustrations/{lesson_id}/scene_{scene.position + 1}.png"
    await storage.save(key, png, "image/png")
    logger.info(
        "illustration_saved lesson_id=%s scene=%s provider=%s",
        lesson_id,
        scene.position + 1,
        provider,
    )
    if persist_each:
        from app.core.database import AsyncSessionLocal

        async with _persist_lock:
            async with AsyncSessionLocal() as db:
                await _upsert_illustration(db, lesson_id, scene, prompt, key, provider)
    return (scene, prompt, key, provider)


async def _upsert_illustration(
    db: AsyncSession,
    lesson_id: str,
    scene: ScenePlan,
    prompt: str,
    key: str,
    provider: str,
) -> LessonIllustration:
    await db.execute(
        delete(LessonIllustration).where(
            LessonIllustration.lesson_id == lesson_id,
            LessonIllustration.position == scene.position,
        )
    )
    row = LessonIllustration(
        lesson_id=lesson_id,
        position=scene.position,
        caption=scene.caption,
        prompt=prompt,
        storage_key=key,
        provider=provider,
    )
    db.add(row)
    for attempt in range(6):
        try:
            await db.commit()
            await db.refresh(row)
            return row
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            logger.warning("illustration_db_locked attempt=%s", attempt + 1)
            await db.rollback()
            db.add(row)
            await asyncio.sleep(0.4 * (attempt + 1))
    raise RuntimeError("Could not save story pictures.")


async def _persist_illustrations(
    db: AsyncSession,
    lesson_id: str,
    prepared: list[tuple[ScenePlan, str, str, str]],
    *,
    commit: bool = False,
) -> list[LessonIllustration]:
    attempts = 8 if commit else 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            await db.execute(delete(LessonIllustration).where(LessonIllustration.lesson_id == lesson_id))
            rows: list[LessonIllustration] = []
            for scene, prompt, key, provider in prepared:
                row = LessonIllustration(
                    lesson_id=lesson_id,
                    position=scene.position,
                    caption=scene.caption,
                    prompt=prompt,
                    storage_key=key,
                    provider=provider,
                )
                db.add(row)
                rows.append(row)
            await db.flush()
            if commit:
                await db.commit()
            return rows
        except OperationalError as exc:
            last_error = exc
            if not commit or "locked" not in str(exc).lower():
                raise
            logger.warning("illustration_db_locked attempt=%s", attempt + 1)
            await db.rollback()
            await asyncio.sleep(0.4 * (attempt + 1))
    raise last_error or RuntimeError("Could not save story pictures.")


async def generate_lesson_illustrations(
    db: AsyncSession,
    lesson: Lesson,
    *,
    prefer_gemini: bool = True,
) -> list[LessonIllustration]:
    prepared = await _prepare_illustration_files(
        lesson.id,
        lesson.title,
        lesson.language,
        lesson.edited_text or lesson.original_text or "",
        prefer_gemini=prefer_gemini,
    )
    if not prepared:
        return []
    return await _persist_illustrations(db, lesson.id, prepared)


_draw_locks: dict[str, asyncio.Lock] = {}
_draw_status: dict[str, dict[str, object]] = {}

DRAWING_STALE_SECONDS = 180
MSG_DRAWING = "Drawing all four pictures at once — they usually appear in about 20 seconds."
MSG_NO_KEY = (
    "I can't draw story pictures on this server yet. "
    "Add a Google AI key, then tap Draw the story now."
)
MSG_FAILED = (
    "I couldn't draw the pictures this time. "
    "Gemini may be busy or out of quota. Try again in a bit."
)


def _draw_lock(lesson_id: str) -> asyncio.Lock:
    lock = _draw_locks.get(lesson_id)
    if lock is None:
        lock = asyncio.Lock()
        _draw_locks[lesson_id] = lock
    return lock


def illustration_in_progress(lesson_id: str) -> bool:
    lock = _draw_locks.get(lesson_id)
    return bool(lock and lock.locked())


def set_illustration_status(lesson_id: str, status: str, message: str = "") -> None:
    _draw_status[lesson_id] = {
        "status": status,
        "message": message,
        "updated_at": time.time(),
    }


def public_illustration_status(lesson_id: str, gemini_count: int) -> tuple[str, str]:
    """Tell the UI whether pictures are ready, still drawing, or cannot be drawn."""
    has_key = bool(get_settings().google_ai_api_key)
    in_progress = illustration_in_progress(lesson_id)
    state = _draw_status.get(lesson_id) or {}
    status = str(state.get("status") or "")
    updated = float(state.get("updated_at") or 0)
    stale_drawing = (
        status == "drawing"
        and not in_progress
        and updated > 0
        and (time.time() - updated) > DRAWING_STALE_SECONDS
    )

    if in_progress or (status == "drawing" and not stale_drawing):
        return "drawing", str(state.get("message") or MSG_DRAWING)
    if gemini_count >= 4:
        return "ready", ""
    if not has_key:
        return "unavailable", MSG_NO_KEY
    if status == "failed" or stale_drawing:
        return "failed", str(state.get("message") or MSG_FAILED)
    if status == "unavailable":
        return "unavailable", str(state.get("message") or MSG_NO_KEY)
    return "idle", MSG_DRAWING


async def draw_lesson_illustrations(
    lesson_id: str,
    *,
    prefer_gemini: bool = True,
    force: bool = False,
) -> list[LessonIllustration]:
    """Draw pictures without holding a long-lived DB connection (avoids SQLite locks)."""
    from app.core.database import AsyncSessionLocal

    async with _draw_lock(lesson_id):
        set_illustration_status(lesson_id, "drawing", MSG_DRAWING)
        skip_positions: set[int] = set()
        async with AsyncSessionLocal() as db:
            lesson = await db.get(Lesson, lesson_id)
            if not lesson:
                set_illustration_status(lesson_id, "failed", MSG_FAILED)
                return []
            existing = await list_lesson_illustrations(db, lesson_id)
            gemini_rows = [row for row in existing if row.provider == "gemini"]
            if not force and len(gemini_rows) >= 4:
                set_illustration_status(lesson_id, "ready", "")
                return existing
            if not force:
                skip_positions = {row.position for row in gemini_rows}
            title = lesson.title
            language = lesson.language
            story = lesson.edited_text or lesson.original_text or ""

        try:
            prepared = await _prepare_illustration_files(
                lesson_id,
                title,
                language,
                story,
                prefer_gemini=prefer_gemini,
                persist_each=True,
                skip_positions=skip_positions,
            )
        except Exception:
            set_illustration_status(lesson_id, "failed", MSG_FAILED)
            raise
        if not prepared and not skip_positions:
            if prefer_gemini and not get_settings().google_ai_api_key:
                set_illustration_status(lesson_id, "unavailable", MSG_NO_KEY)
            else:
                set_illustration_status(lesson_id, "failed", MSG_FAILED)
            return []

        async with AsyncSessionLocal() as db:
            rows = await list_lesson_illustrations(db, lesson_id)
        gemini_count = sum(1 for row in rows if row.provider == "gemini")
        if gemini_count >= 4:
            set_illustration_status(lesson_id, "ready", "")
        elif gemini_count:
            set_illustration_status(
                lesson_id,
                "failed",
                "I drew some pictures, but the rest didn't finish. Try again.",
            )
        elif prefer_gemini and not get_settings().google_ai_api_key:
            set_illustration_status(lesson_id, "unavailable", MSG_NO_KEY)
        else:
            set_illustration_status(lesson_id, "failed", MSG_FAILED)
        return rows


async def list_lesson_illustrations(db: AsyncSession, lesson_id: str) -> list[LessonIllustration]:
    rows = await db.scalars(
        select(LessonIllustration)
        .where(LessonIllustration.lesson_id == lesson_id)
        .order_by(LessonIllustration.position)
    )
    return list(rows)

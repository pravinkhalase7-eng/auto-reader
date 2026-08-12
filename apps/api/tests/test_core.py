from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.database import get_db
from app.main import app
from app.utils.segmentation import reconstruct_from_text, tokenize_words
from app.utils.word_timing import estimate_word_timings
from app.providers.ai import LocalAIProvider


@pytest_asyncio.fixture
async def client(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_health(client):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_login(client):
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "student@example.com",
            "password": "secret12",
            "full_name": "Test Student",
            "class_level": 4,
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"


def test_segmentation_preserves_paragraphs():
    text = "The Lion and the Mouse\n\nOne day a lion slept.\n\nA mouse ran by."
    tree = reconstruct_from_text(text, title="The Lion and the Mouse", language="en", content_type="story")
    assert tree.word_count > 5
    assert len(tree.sections) >= 1
    assert all(w.id for s in tree.sections for p in s.paragraphs for sent in p.sentences for w in sent.words)


def test_word_timing_fallback():
    words = [("1", "The"), ("2", "lion"), ("3", "slept.")]
    timings = estimate_word_timings(words, speed="slow")
    assert len(timings) == 3
    assert timings[0].start_ms < timings[0].end_ms
    assert timings[-1].end_ms > timings[0].end_ms


@pytest.mark.asyncio
async def test_local_quiz_and_eval():
    ai = LocalAIProvider()
    text = "The lion and the mouse became friends after the mouse helped the lion."
    qs = await ai.generate_questions(text, "en", difficulty="easy", class_level=3, count=4)
    assert len(qs) >= 3
    result = await ai.evaluate_answer(
        "Why did they become friends?",
        "The mouse helped the lion",
        "because the mouse helped him later",
        "en",
    )
    assert result.correct is True


def test_tokenize():
    assert tokenize_words("Hello, world!") == ["Hello,", "world!"]


def test_ocr_clean_drops_noise_keeps_story():
    from app.utils.ocr_clean import clean_ocr_text

    raw = """The Lion and the Mouse

    ||| ~~ ©
    12
    ~ | • • •
    rn cl

    One day, a lion was sleeping in the forest.
    • • •
    """
    cleaned = clean_ocr_text(raw)
    assert "Lion" in cleaned
    assert "sleeping" in cleaned
    assert "|||" not in cleaned
    assert "~~" not in cleaned
    assert "rn" not in cleaned.split()
    assert cleaned.splitlines()[-1].strip() != "12"


def test_ocr_clean_keeps_devanagari():
    from app.utils.ocr_clean import clean_ocr_text

    text = "एक दिन जंगल में एक शेर सो रहा था।"
    assert "शेर" in clean_ocr_text(text)


def test_merge_page_texts_stitches_mid_sentence_breaks():
    from app.utils.ocr_clean import merge_page_texts

    merged = merge_page_texts(
        [
            "The lion slept under a tree and dreamed of",
            "the forest. A mouse ran by.",
            "Later they became friends.",
        ]
    )
    assert "dreamed of the forest." in merged
    assert "A mouse ran by." in merged
    assert "Later they became friends." in merged


def test_merge_page_texts_skips_empty_pages():
    from app.utils.ocr_clean import merge_page_texts

    assert merge_page_texts(["Hello.", "", "  ", "World."]) == "Hello.\n\nWorld."


def test_plan_scenes_local_keeps_story_order():
    from app.services.story_illustrations import plan_scenes_local

    text = (
        "The lion slept under a tree. A mouse ran over his paw. "
        "The lion woke up angry. The mouse promised to help. "
        "Later the lion was caught in a net. The mouse chewed the ropes and set him free."
    )
    scenes = plan_scenes_local(text, "The Lion and the Mouse", "en")
    assert 3 <= len(scenes) <= 6
    assert scenes[0].position == 0
    assert "lion" in scenes[0].caption.lower() or "lion" in scenes[0].visual.lower()
    assert scenes[-1].position == len(scenes) - 1


def test_placeholder_illustration_is_png():
    from app.services.story_illustrations import render_placeholder_png

    png = render_placeholder_png(
        "The lion slept under a tree. A mouse ran over his paw.",
        0,
        4,
        "The Lion and the Mouse",
        "lion sleeping under a tree with a mouse",
    )
    assert png.startswith(b"\x89PNG")
    assert len(png) > 200


def test_tesseract_data_filters_low_confidence():
    from app.providers.ocr import _text_from_tesseract_data

    data = {
        "text": ["The", "lion", "@@@", "slept"],
        "conf": ["90", "88", "12", "80"],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }
    text, avg = _text_from_tesseract_data(data)
    assert "lion" in text
    assert "@@@" not in text
    assert avg > 0.7


def test_preprocess_bleaches_bright_chroma():
    import io

    from PIL import Image

    from app.services.image_preprocess import ImagePreprocessService

    img = Image.new("RGB", (1600, 400), (255, 255, 255))
    img.paste((15, 15, 15), (50, 50, 150, 200))
    img.paste((255, 230, 40), (900, 50, 1400, 350))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    processed, _, _ = ImagePreprocessService().process_bytes(buf.getvalue())
    out = Image.open(io.BytesIO(processed))
    assert out.mode == "L"
    assert out.getpixel((90, 120)) < 60
    assert out.getpixel((1150, 180)) > 200


@pytest.mark.asyncio
async def test_persist_content_tree_replaces_words_with_timings(tmp_path):
    """Editing a lesson must drop TTS timings before replacing words (Postgres FK)."""
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool

    from app.models import Lesson, User
    from app.services.lesson_processing import LessonProcessingService
    from app.utils.segmentation import reconstruct_from_text

    db_path = tmp_path / "fk.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            email="editor@example.com",
            hashed_password="x",
            full_name="Editor",
        )
        session.add(user)
        await session.flush()
        lesson = Lesson(user_id=user.id, title="Story", status="ready")
        session.add(lesson)
        await session.flush()

        svc = LessonProcessingService(session)
        tree1 = reconstruct_from_text(
            "The lion slept.\n\nThe mouse ran.",
            title="Story",
            language="en",
            content_type="story",
        )
        await svc.persist_content_tree(lesson, tree1)
        await svc.ensure_audio(lesson, speed="slow")

        tree2 = reconstruct_from_text(
            "The lion woke up.\n\nThe mouse helped him.",
            title="Story",
            language="en",
            content_type="story",
        )
        await svc.persist_content_tree(lesson, tree2)
        await svc.ensure_audio(lesson, speed="slow")
        await session.commit()

        assert "woke" in (lesson.edited_text or "")

    await engine.dispose()


@pytest.mark.asyncio
async def test_upload_multiple_pages_then_delete_lesson(client):
    from io import BytesIO

    from PIL import Image

    def png_bytes() -> bytes:
        buf = BytesIO()
        Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
        return buf.getvalue()

    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pages@example.com",
            "password": "secret12",
            "full_name": "Page Student",
            "class_level": 3,
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    blob = png_bytes()
    up = await client.post(
        "/api/v1/lessons/upload",
        headers=headers,
        files=[
            ("files", ("p1.png", blob, "image/png")),
            ("files", ("p2.png", blob, "image/png")),
        ],
    )
    assert up.status_code == 200
    lesson_id = up.json()["lesson_id"]
    detail = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["page_count"] == 2
    assert len(body["pages"]) == 2

    deleted = await client.delete(f"/api/v1/lessons/{lesson_id}", headers=headers)
    assert deleted.status_code == 200
    gone = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers)
    assert gone.status_code == 404
    listed = await client.get("/api/v1/lessons", headers=headers)
    assert all(item["id"] != lesson_id for item in listed.json())


@pytest.mark.asyncio
async def test_create_lesson_from_text(client):
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "typed@example.com",
            "password": "secret12",
            "full_name": "Typed Student",
            "class_level": 3,
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    too_short = await client.post(
        "/api/v1/lessons/from-text",
        headers=headers,
        json={"text": "Too short"},
    )
    assert too_short.status_code == 400

    story = (
        "Once upon a time a lion slept in the forest. "
        "A little mouse ran across his paw and woke him up."
    )
    created = await client.post(
        "/api/v1/lessons/from-text",
        headers=headers,
        json={"text": story, "title": "The Lion and the Mouse"},
    )
    assert created.status_code == 200
    body = created.json()
    lesson_id = body["lesson_id"]
    detail = await client.get(f"/api/v1/lessons/{lesson_id}", headers=headers)
    assert detail.status_code == 200
    lesson = detail.json()
    assert lesson["title"] == "The Lion and the Mouse"
    assert lesson["page_count"] == 0
    assert "lion slept" in (lesson["original_text"] or "")
    assert lesson["pages"] == []



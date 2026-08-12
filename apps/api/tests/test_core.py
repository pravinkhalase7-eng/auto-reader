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

    One day, a lion was sleeping in the forest.
    • • •
    """
    cleaned = clean_ocr_text(raw)
    assert "Lion" in cleaned
    assert "sleeping" in cleaned
    assert "|||" not in cleaned
    assert "~~" not in cleaned
    assert cleaned.splitlines()[-1].strip() != "12"


def test_ocr_clean_keeps_devanagari():
    from app.utils.ocr_clean import clean_ocr_text

    text = "एक दिन जंगल में एक शेर सो रहा था।"
    assert "शेर" in clean_ocr_text(text)


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


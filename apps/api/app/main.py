import uuid
from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.api.v1 import api_router
from app.core.base import Base
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, apply_schema_patches, engine
from app.core.exceptions import AppError
from app.core.logging import request_id_ctx, setup_logging
from app.core.security import TokenError
import app.models  # noqa: F401 — register models

settings = get_settings()
setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.getLogger("app.main").info("DATABASE_URL=%s", settings.database_url)
    logging.getLogger("app.pavi.voice").info(
        "voice_call_mode=%s twilio_configured=%s webhook_base=%s",
        settings.voice_call_mode,
        bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number),
        settings.resolved_twilio_webhook_base,
    )
    async with engine.begin() as conn:
        if "sqlite" in settings.database_url:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.run_sync(Base.metadata.create_all)
        await apply_schema_patches(conn)
    if settings.seed_on_startup:
        async with AsyncSessionLocal() as session:
            from app.services.seed import seed_demo_lessons

            await seed_demo_lessons(session)

    stop = asyncio.Event()

    async def reminder_loop() -> None:
        from app.workers.beat_tasks import scan_due_reminders_inline

        interval = max(5, int(settings.reminder_scan_interval_seconds))
        while not stop.is_set():
            try:
                await asyncio.to_thread(scan_due_reminders_inline)
            except Exception:
                logging.getLogger("app.pavi.beat").exception("inline_reminder_scan_failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except TimeoutError:
                continue

    task = asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request_id_ctx.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code, "request_id": request_id_ctx.get()},
    )


@app.exception_handler(TokenError)
async def token_error_handler(_: Request, exc: TokenError):
    return JSONResponse(
        status_code=401,
        content={"detail": "Please sign in to continue.", "code": "UNAUTHORIZED"},
    )


app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"message": "Welcome to AI Teacher API", "docs": "/docs"}

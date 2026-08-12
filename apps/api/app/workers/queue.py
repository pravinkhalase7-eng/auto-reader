"""Simple asyncio task queue — swap for Celery/SQS later without changing callers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

JobFn = Callable[..., Awaitable[Any]]


class TaskQueue:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def enqueue(self, coro: Awaitable[Any], *, name: str = "job") -> None:
        task = asyncio.create_task(self._run(coro, name=name), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, coro: Awaitable[Any], *, name: str) -> None:
        try:
            await coro
        except Exception:  # noqa: BLE001
            logger.exception("background_job_failed name=%s", name)


task_queue = TaskQueue()

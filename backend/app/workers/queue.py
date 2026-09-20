"""Background job execution.

The API layer only ever calls ``job_queue.enqueue(name, **payload)``. Jobs
themselves are plain async functions that receive their own database session,
so moving to Celery/RQ/Arq later means writing one new ``JobQueue``
implementation — the business logic in ``app.services`` does not change.
"""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionFactory
from app.core.logging import get_logger

logger = get_logger(__name__)

JobHandler = Callable[[AsyncSession, dict], Awaitable[None]]

_HANDLERS: dict[str, JobHandler] = {}


def register_job(name: str) -> Callable[[JobHandler], JobHandler]:
    def decorator(handler: JobHandler) -> JobHandler:
        _HANDLERS[name] = handler
        return handler

    return decorator


def get_handler(name: str) -> JobHandler:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"No job handler registered for '{name}'")
    return handler


class JobQueue(abc.ABC):
    @abc.abstractmethod
    async def enqueue(self, name: str, **payload) -> None: ...

    @abc.abstractmethod
    async def shutdown(self) -> None: ...

    @property
    @abc.abstractmethod
    def pending(self) -> int: ...


class InProcessJobQueue(JobQueue):
    """Runs jobs as asyncio tasks inside the API process.

    Adequate for local development and single-instance deployments. A job
    failure is always recorded by the job itself; this class only guarantees
    that a crash cannot take down the request that scheduled it.
    """

    name = "in_process"

    def __init__(self, max_concurrency: int = 2):
        self._tasks: set[asyncio.Task] = set()
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def enqueue(self, name: str, **payload) -> None:
        handler = get_handler(name)
        task = asyncio.create_task(self._run(name, handler, payload))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, name: str, handler: JobHandler, payload: dict) -> None:
        async with self._semaphore:
            logger.info("job started name=%s payload=%s", name, payload)
            try:
                async with SessionFactory() as session:
                    await handler(session, payload)
                logger.info("job finished name=%s payload=%s", name, payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job crashed name=%s payload=%s", name, payload)

    @property
    def pending(self) -> int:
        return len([task for task in self._tasks if not task.done()])

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)


_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = InProcessJobQueue()
    return _queue


async def shutdown_job_queue() -> None:
    global _queue
    if _queue is not None:
        await _queue.shutdown()
        _queue = None

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class BackgroundWorker:

    def __init__(self, limit: int = 10):
        # Limits concurrent executions across all keys
        self._semaphore = asyncio.Semaphore(limit)

        # url/key -> running task
        self._tasks_by_key: dict[str, asyncio.Task] = {}

        # Protects task creation / lookup
        self._lock = asyncio.Lock()

    async def schedule_once(
        self,
        key: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
    ) -> asyncio.Task:
        """
        Ensures only ONE task runs per key at any time.

        If a task already exists for this key and is still running,
        returns the existing task (coro_factory is NOT called).

        If the existing task is already done (completed but the done
        callback hasn't fired yet), it is replaced transparently.

        Accepts a *factory* (callable returning a coroutine) instead
        of a raw coroutine so that we never create an unawaited
        coroutine when a task already exists.
        """

        async with self._lock:

            existing = self._tasks_by_key.get(key)

            if existing and not existing.done():
                # A running task exists — reuse it
                return existing

            # No running task — create one
            task = asyncio.create_task(
                self._run(coro_factory())
            )

            self._tasks_by_key[key] = task

        def _on_done(completed_task: asyncio.Task):

            done_callback_logger = get_logger(
                "app.workers.background_worker._on_done"
            )

            # Only clean up if THIS task is still the current entry.
            # Prevents a race where a replacement task was stored
            # before this callback fires (call_soon scheduling).
            current = self._tasks_by_key.get(key)
            if current is completed_task:
                self._tasks_by_key.pop(key, None)

            try:

                if completed_task.cancelled():
                    done_callback_logger.warning(
                        "Task cancelled for key=%s",
                        key,
                    )
                    return

                exc = completed_task.exception()

                if exc:
                    done_callback_logger.exception(
                        "Task failed for key=%s: %s",
                        key,
                        exc,
                    )

            except Exception:
                done_callback_logger.exception(
                    "Error while handling task cleanup "
                    "for key=%s",
                    key,
                )

        task.add_done_callback(_on_done)

        return task

    async def _run(
        self,
        coro: Coroutine[Any, Any, Any],
    ) -> Any:
        async with self._semaphore:
            return await coro

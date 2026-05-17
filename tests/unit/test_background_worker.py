import asyncio
import pytest
from app.workers.background_worker import BackgroundWorker


@pytest.mark.asyncio
async def test_schedule_once_runs_coroutine():
    worker = BackgroundWorker(limit=5)
    sentinel = []

    async def work():
        sentinel.append("done")

    task = await worker.schedule_once("key-1", lambda: work())
    await task

    assert sentinel == ["done"]


@pytest.mark.asyncio
async def test_schedule_once_returns_task_with_result():
    worker = BackgroundWorker(limit=5)

    async def work():
        return 42

    task = await worker.schedule_once("key-1", lambda: work())
    result = await task

    assert result == 42


@pytest.mark.asyncio
async def test_schedule_once_deduplicates_concurrent():
    worker = BackgroundWorker(limit=5)
    started = asyncio.Event()
    can_finish = asyncio.Event()

    async def work():
        started.set()
        await can_finish.wait()
        return "result"

    task_a = await worker.schedule_once("same-key", lambda: work())
    await started.wait()

    # Second call with same key returns the same running task
    task_b = await worker.schedule_once("same-key", lambda: work())

    assert task_a is task_b

    can_finish.set()
    result = await task_a
    assert result == "result"


@pytest.mark.asyncio
async def test_is_running_true_during_execution():
    worker = BackgroundWorker(limit=5)
    started = asyncio.Event()
    can_finish = asyncio.Event()

    async def work():
        started.set()
        await can_finish.wait()

    task = await worker.schedule_once("key-1", lambda: work())
    await started.wait()

    assert worker._tasks_by_key.get("key-1") is task

    can_finish.set()
    await task


@pytest.mark.asyncio
async def test_cleanup_after_completion():
    worker = BackgroundWorker(limit=5)

    async def work():
        pass

    task = await worker.schedule_once("cleanup-key", lambda: work())
    await task
    await asyncio.sleep(0)

    assert "cleanup-key" not in worker._tasks_by_key


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    worker = BackgroundWorker(limit=2)
    concurrent_max = 0
    concurrent_current = 0
    lock = asyncio.Lock()

    async def work():
        nonlocal concurrent_max, concurrent_current
        async with lock:
            concurrent_current += 1
            concurrent_max = max(concurrent_max, concurrent_current)
        await asyncio.sleep(0.05)
        async with lock:
            concurrent_current -= 1

    tasks = [
        await worker.schedule_once(f"key-{i}", lambda: work())
        for i in range(6)
    ]
    await asyncio.gather(*tasks)

    assert concurrent_max <= 2


@pytest.mark.asyncio
async def test_error_in_task_does_not_crash_worker():
    worker = BackgroundWorker(limit=5)

    async def work():
        raise ValueError("oops")

    task = await worker.schedule_once("error-key", lambda: work())
    await asyncio.sleep(0)

    assert task.done()
    with pytest.raises(ValueError, match="oops"):
        task.result()

    await asyncio.sleep(0)
    assert "error-key" not in worker._tasks_by_key


@pytest.mark.asyncio
async def test_factory_not_called_when_task_exists():
    worker = BackgroundWorker(limit=5)
    started = asyncio.Event()
    can_finish = asyncio.Event()
    factory_calls = []

    async def work():
        factory_calls.append("executed")
        started.set()
        await can_finish.wait()

    task_a = await worker.schedule_once("dedup-key", lambda: work())
    await started.wait()

    # Second call — factory should NOT be called
    task_b = await worker.schedule_once("dedup-key", lambda: work())

    assert task_a is task_b
    assert len(factory_calls) == 1  # factory called only once

    can_finish.set()
    await task_a

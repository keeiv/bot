"""Bounded, serialized storage work outside the Discord event loop."""

import asyncio
import functools
import weakref

from src.utils.document_store import StorageError

_states = weakref.WeakKeyDictionary()


async def run_blocking(function, *args, **kwargs):
    """Wait for an in-flight operation before propagating cancellation."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            break
    if cancelled:
        # Retrieve worker errors as well, so they cannot become unhandled tasks.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    return task.result()


async def run_storage(function, *args, **kwargs):
    """Serialize cached read/modify/write operations with bounded admission."""
    loop = asyncio.get_running_loop()
    if loop not in _states:
        _states[loop] = (asyncio.Semaphore(128), asyncio.Lock())
    slots, lock = _states[loop]
    try:
        await asyncio.wait_for(slots.acquire(), timeout=5)
    except asyncio.TimeoutError as exc:
        raise StorageError("Storage worker queue is full") from exc
    try:
        async with lock:
            return await run_blocking(functools.partial(function, *args, **kwargs))
    finally:
        slots.release()

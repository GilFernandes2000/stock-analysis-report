"""Shared, bounded concurrency primitives for blocking scraper I/O.

Sync FastAPI routes already run on Starlette's ~40-thread pool. Without a bound,
each request that fans out (profile lookups, a report scan) could spin up its
own ``ThreadPoolExecutor`` and multiply that pool; a couple of concurrent
portfolio loads or report generations would exhaust the process.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from fastapi import HTTPException, status

_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def shared_pool() -> ThreadPoolExecutor:
    """Process-wide pool for short blocking fan-out (e.g. per-ticker profile fetches)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="scrape")
    return _pool


# At most this many scraper-heavy report / tearsheet generations run at once;
# further requests get a fast 503 instead of piling up worker threads.
_generation_slots = threading.BoundedSemaphore(2)


@contextmanager
def generation_slot() -> Iterator[None]:
    if not _generation_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The server is busy generating another report. Try again shortly.",
        )
    try:
        yield
    finally:
        _generation_slots.release()

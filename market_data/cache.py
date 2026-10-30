"""Process-wide cache for market data.

Every Streamlit session in this process shares the same entries, so many
users asking for the same ticker reuse one Yahoo response. A request that is
already running is not started again.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

CACHE_TTL_SECONDS = 300
FAILURE_TTL_SECONDS = 60
_MAX_ENTRIES = 512


@dataclass
class _Entry(Generic[T]):
    expires: float
    value: T


_lock = threading.Lock()
_entries: dict[tuple, _Entry] = {}
_inflight: dict[tuple, threading.Event] = {}


def _drop_expired(now: float) -> None:
    expired = [key for key, entry in _entries.items() if entry.expires <= now]
    for key in expired:
        _entries.pop(key, None)


def _trim() -> None:
    if len(_entries) <= _MAX_ENTRIES:
        return
    oldest = sorted(_entries.items(), key=lambda item: item[1].expires)
    for key, _entry in oldest[: len(_entries) - _MAX_ENTRIES]:
        _entries.pop(key, None)


def get_or_load(
    key: tuple,
    loader: Callable[[], tuple[T, bool]],
    wait_seconds: float,
    fallback: Callable[[], T],
) -> T:
    """Return a cached value, or load it once.

    ``loader`` returns ``(value, failed)``. Failed results use the short TTL
    so a temporary Yahoo problem is not requested again immediately, and is
    not kept for the full success TTL. Waiters do not start their own request.
    """
    now = time.monotonic()
    with _lock:
        _drop_expired(now)
        found = _entries.get(key)
        if found is not None and found.expires > now:
            return found.value
        waiting = _inflight.get(key)
        if waiting is None:
            waiting = threading.Event()
            _inflight[key] = waiting
            leader = True
        else:
            leader = False

    if not leader:
        waiting.wait(wait_seconds)
        with _lock:
            found = _entries.get(key)
            if found is not None and found.expires > time.monotonic():
                return found.value
        return fallback()

    try:
        value, failed = loader()
        ttl = FAILURE_TTL_SECONDS if failed else CACHE_TTL_SECONDS
        with _lock:
            _entries[key] = _Entry(time.monotonic() + ttl, value)
            _trim()
        return value
    finally:
        with _lock:
            _inflight.pop(key, None)
        waiting.set()


def cached_history(ticker: str):
    """Return one unexpired history frame for ``ticker``, if any period is cached."""
    now = time.monotonic()
    with _lock:
        matches = [
            entry.value
            for key, entry in _entries.items()
            if len(key) >= 2 and key[0] == "history" and key[1] == ticker and entry.expires > now
        ]
    if not matches:
        return None
    return matches[-1]

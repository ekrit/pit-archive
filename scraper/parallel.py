"""Threaded fetch helper: the single biggest wall-time optimization.

Per-ticker HTTP sources (news RSS, Stocktwits, Wikipedia) were serial with
polite sleeps — ~1s/ticker means ~2 minutes per source per run. A bounded
thread pool with a shared token-bucket rate limiter keeps the same politeness
per host while overlapping wait time across tickers: ~8-10x faster with no
extra load on any endpoint (the rate limit, not the thread count, governs
request pacing).
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

K = TypeVar("K")
V = TypeVar("V")


def thread_local(factory: Callable[[], V]) -> Callable[[], V]:
    """Per-thread lazily-constructed instance (e.g. one requests.Session per
    worker — Session is not documented thread-safe, so sharing one across the
    pool risks corrupted connection state under load)."""
    store = threading.local()

    def get() -> V:
        if not hasattr(store, "obj"):
            store.obj = factory()
        return store.obj

    return get


class RateLimiter:
    """Token bucket: at most `rate` acquisitions per second, thread-safe."""

    def __init__(self, rate: float):
        self.interval = 1.0 / max(rate, 0.01)
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self.interval
        if wait > 0:
            time.sleep(wait)


def fetch_map(
    keys: Iterable[K],
    fn: Callable[[K], V],
    max_workers: int = 8,
    rate_per_sec: float = 4.0,
    retries: int = 2,
    backoff: float = 1.5,
    default: V | None = None,
) -> dict[K, V]:
    """Apply `fn` to each key concurrently with rate limiting and retries.

    Failures (after retries) map to `default` rather than raising — one bad
    ticker or one flaky endpoint must never kill a whole collection run.
    """
    limiter = RateLimiter(rate_per_sec)
    keys = list(keys)
    results: dict[K, V] = {}

    def call(key: K) -> V:
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            limiter.acquire()
            try:
                return fn(key)
            except Exception as e:  # noqa: BLE001 - deliberate catch-all guard
                last_err = e
                if attempt < retries:
                    time.sleep(backoff ** (attempt + 1))
        raise last_err  # type: ignore[misc]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(call, k): k for k in keys}
        for fut in as_completed(futures):
            k = futures[fut]
            try:
                results[k] = fut.result()
            except Exception:  # noqa: BLE001
                if default is not None:
                    results[k] = default
    return results

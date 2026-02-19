"""
Benchmark utilities — thread-safe registry that tracks execution time per function.

Usage
-----
Apply @timed() to any sync or async function:

    from .benchmark import timed

    @timed()
    async def my_func(): ...

    @timed("custom.label")
    def another_func(): ...

Query results at any point:

    from .benchmark import registry
    for stat in registry.all_stats():
        print(stat)
"""

from __future__ import annotations

import inspect
import threading
from collections import defaultdict
from dataclasses import dataclass
from functools import wraps
from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkStats:
    """Aggregated stats for a single tracked function."""

    name: str
    calls: int
    total_s: float
    min_s: float
    max_s: float
    avg_s: float

    def __str__(self) -> str:
        return (
            f"{self.name}: calls={self.calls} "
            f"total={self.total_s:.3f}s  avg={self.avg_s:.3f}s  "
            f"min={self.min_s:.3f}s  max={self.max_s:.3f}s"
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class BenchmarkRegistry:
    """Thread-safe store for per-function timing records."""

    _global: "BenchmarkRegistry | None" = None
    _cls_lock = threading.Lock()

    def __init__(self) -> None:
        self._times: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def global_registry(cls) -> "BenchmarkRegistry":
        """Return the process-wide singleton registry."""
        if cls._global is None:
            with cls._cls_lock:
                if cls._global is None:
                    cls._global = cls()
        return cls._global

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def record(self, name: str, elapsed: float) -> None:
        """Record one timing observation for *name*."""
        with self._lock:
            self._times[name].append(elapsed)

    def reset(self, name: str | None = None) -> None:
        """Clear records — all entries if *name* is None, else just that key."""
        with self._lock:
            if name is None:
                self._times.clear()
            else:
                self._times.pop(name, None)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def stats(self, name: str) -> BenchmarkStats | None:
        """Return aggregated stats for a single function, or None if never called."""
        with self._lock:
            times = list(self._times.get(name, []))
        if not times:
            return None
        return _make_stats(name, times)

    def all_stats(self) -> list[BenchmarkStats]:
        """Return stats for every tracked function, sorted by total time descending."""
        with self._lock:
            snapshot = {k: list(v) for k, v in self._times.items()}
        return sorted(
            (_make_stats(name, times) for name, times in snapshot.items()),
            key=lambda s: s.total_s,
            reverse=True,
        )

    def summary_table(self) -> str:
        """Render a plain-text table of all stats (useful for logging)."""
        stats = self.all_stats()
        if not stats:
            return "(no benchmarks recorded)"

        col_w = max(len(s.name) for s in stats) + 2
        header = f"{'Function':<{col_w}} {'Calls':>6}  {'Total':>9}  {'Avg':>9}  {'Min':>9}  {'Max':>9}"
        sep = "-" * len(header)
        rows = [header, sep]
        for s in stats:
            rows.append(
                f"{s.name:<{col_w}} {s.calls:>6}  "
                f"{s.total_s:>8.3f}s  {s.avg_s:>8.3f}s  "
                f"{s.min_s:>8.3f}s  {s.max_s:>8.3f}s"
            )
        return "\n".join(rows)


def _make_stats(name: str, times: list[float]) -> BenchmarkStats:
    total = sum(times)
    return BenchmarkStats(
        name=name,
        calls=len(times),
        total_s=total,
        min_s=min(times),
        max_s=max(times),
        avg_s=total / len(times),
    )


# ---------------------------------------------------------------------------
# Global singleton shortcut
# ---------------------------------------------------------------------------

registry = BenchmarkRegistry.global_registry()


# ---------------------------------------------------------------------------
# @timed() decorator
# ---------------------------------------------------------------------------


def timed(label: str | None = None) -> Callable:
    """
    Decorator that records wall-clock execution time in the global registry.

    Parameters
    ----------
    label:
        Human-readable key stored in the registry.  Defaults to
        ``"module.ClassName.method_name"`` (the function's qualified name).

    Examples
    --------
    >>> @timed()
    ... async def upload_file(path: str): ...

    >>> @timed("ffmpeg.clip")
    ... async def _clip_media_async(self, ...): ...
    """

    def decorator(func: Callable) -> Callable:
        fn_label = label or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                t0 = perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    registry.record(fn_label, perf_counter() - t0)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            t0 = perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                registry.record(fn_label, perf_counter() - t0)

        return sync_wrapper

    return decorator

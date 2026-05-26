from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlowKey:
    src: str
    sport: int
    dst: str
    dport: int


class FlowTracker:
    """Счётчик событий на TCP-flow (split/fake можно применить несколько раз)."""

    def __init__(self, max_entries: int = 65536, ttl_sec: float = 300.0) -> None:
        self._max = max_entries
        self._ttl = ttl_sec
        self._counts: dict[FlowKey, tuple[int, float]] = {}

    def count(self, key: FlowKey) -> int:
        now = time.monotonic()
        entry = self._counts.get(key)
        if entry is None:
            return 0
        n, ts = entry
        if now - ts > self._ttl:
            del self._counts[key]
            return 0
        return n

    def increment(self, key: FlowKey) -> int:
        now = time.monotonic()
        if len(self._counts) >= self._max:
            self._evict(now)
        n = self.count(key) + 1
        self._counts[key] = (n, now)
        return n

    def _evict(self, now: float) -> None:
        expired = [k for k, (_, t) in self._counts.items() if now - t > self._ttl]
        for k in expired:
            del self._counts[k]
        if len(self._counts) >= self._max:
            for k in list(self._counts.keys())[: self._max // 2]:
                del self._counts[k]

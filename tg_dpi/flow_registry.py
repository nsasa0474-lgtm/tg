from __future__ import annotations

import time
from dataclasses import dataclass

from tg_dpi.conn_track import FlowKey


@dataclass
class FlowRegistry:
    """Активные TCP-сессии к DC Telegram (для блокировки RST от DPI с любого IP)."""

    max_entries: int = 32768
    ttl_sec: float = 120.0
    _flows: dict[FlowKey, float] | None = None

    def __post_init__(self) -> None:
        self._flows = {}

    def add(self, key: FlowKey) -> None:
        now = time.monotonic()
        assert self._flows is not None
        if len(self._flows) >= self.max_entries:
            self._evict(now)
        self._flows[key] = now

    def contains(self, key: FlowKey) -> bool:
        assert self._flows is not None
        now = time.monotonic()
        ts = self._flows.get(key)
        if ts is None:
            return False
        if now - ts > self.ttl_sec:
            del self._flows[key]
            return False
        return True

    def _evict(self, now: float) -> None:
        assert self._flows is not None
        for k, t in list(self._flows.items()):
            if now - t > self.ttl_sec:
                del self._flows[k]
        if len(self._flows) >= self.max_entries:
            for k in list(self._flows.keys())[: self.max_entries // 2]:
                del self._flows[k]

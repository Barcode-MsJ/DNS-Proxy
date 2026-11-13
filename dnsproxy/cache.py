"""TTL-aware FIFO cache used by the DNS Proxy."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Callable
import time


@dataclass(frozen=True)
class CacheValue:
    ip: str
    ttl: int


@dataclass
class _Entry:
    ip: str
    original_ttl: int
    inserted_at: float


class DNSCache:
    def __init__(self, max_entries: int | None = None, clock: Callable[[], float] = time.monotonic):
        if max_entries is not None and max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = RLock()

    def _remaining(self, entry: _Entry, now: float) -> int:
        return int(entry.original_ttl - (now - entry.inserted_at))

    def get(self, domain: str) -> CacheValue | None:
        with self._lock:
            entry = self._entries.get(domain)
            if entry is None:
                return None
            remaining = self._remaining(entry, self._clock())
            if remaining < 1:
                del self._entries[domain]
                return None
            return CacheValue(entry.ip, remaining)

    def put(self, domain: str, ip: str, ttl: int) -> None:
        if ttl <= 0:
            return
        with self._lock:
            # A refreshed key is a new FIFO insertion.
            self._entries.pop(domain, None)
            if self.max_entries is not None:
                while len(self._entries) >= self.max_entries:
                    self._entries.popitem(last=False)
            self._entries[domain] = _Entry(ip=ip, original_ttl=ttl, inserted_at=self._clock())

    def snapshot(self) -> list[tuple[str, str, int]]:
        with self._lock:
            now = self._clock()
            valid: list[tuple[str, str, int]] = []
            expired: list[str] = []
            for domain, entry in self._entries.items():
                remaining = self._remaining(entry, now)
                if remaining < 1:
                    expired.append(domain)
                else:
                    valid.append((domain, entry.ip, remaining))
            for domain in expired:
                self._entries.pop(domain, None)
            return valid

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

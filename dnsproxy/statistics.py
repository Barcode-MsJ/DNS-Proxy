"""Request statistics for the B1 bonus feature."""
from __future__ import annotations
from threading import RLock


class Statistics:
    FIELDS = ("AD_BLOCK", "SANCTION", "CACHE", "UPSTREAM", "ERRORS")

    def __init__(self):
        self._lock = RLock()
        self._counts = {"Total": 0, **{field: 0 for field in self.FIELDS}}

    def record(self, source: str, status: str) -> None:
        with self._lock:
            self._counts["Total"] += 1
            if source in self._counts and source != "Total":
                self._counts[source] += 1
            if status in {"INVALID_INPUT", "SERVER_ERROR"}:
                self._counts["ERRORS"] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def format(self) -> str:
        counts = self.snapshot()
        return (
            f"Total: {counts['Total']} | AD_BLOCK: {counts['AD_BLOCK']} | "
            f"SANCTION: {counts['SANCTION']} | CACHE: {counts['CACHE']} | "
            f"UPSTREAM: {counts['UPSTREAM']} | ERRORS: {counts['ERRORS']}"
        )

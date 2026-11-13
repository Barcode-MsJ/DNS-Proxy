"""Append-only structured request log for the B4 bonus feature."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from threading import RLock


class RequestLogger:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()

    def log(self, domain: str, source: str, status: str, ip: str, ttl: int | str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} | {domain} | {source} | {status} | {ip} | {ttl}\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="") as file:
                file.write(line)

    def recent(self, limit: int = 30) -> list[str]:
        if not self.path.exists():
            return []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        return lines[-max(1, limit):]

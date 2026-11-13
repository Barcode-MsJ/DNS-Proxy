"""Loading and reloading ad/sanction domain lists."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from .domains import is_valid_domain_input, normalize_domain


@dataclass(frozen=True)
class LoadedLists:
    ads: frozenset[str]
    sanctions: frozenset[str]
    warnings: tuple[str, ...] = ()


def _read_one(path: Path) -> tuple[set[str], list[str]]:
    domains: set[str] = set()
    warnings: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OSError(f"Cannot read {path.name}: {exc}") from exc
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not is_valid_domain_input(line):
            warnings.append(f"Warning: bad line in {path.name}: {line}")
            continue
        domains.add(normalize_domain(line))
    return domains, warnings


class DomainLists:
    def __init__(self, ad_path: Path, sanction_path: Path):
        self.ad_path = ad_path
        self.sanction_path = sanction_path
        self._lock = RLock()
        self._loaded = self._load()

    def _load(self) -> LoadedLists:
        ads, ad_warnings = _read_one(self.ad_path)
        sanctions, sanction_warnings = _read_one(self.sanction_path)
        return LoadedLists(frozenset(ads), frozenset(sanctions), tuple(ad_warnings + sanction_warnings))

    @property
    def warnings(self) -> tuple[str, ...]:
        with self._lock:
            return self._loaded.warnings

    def snapshot(self) -> LoadedLists:
        with self._lock:
            return self._loaded

    def reload(self) -> LoadedLists:
        # Load both files first; publish atomically only if both can be read.
        new_lists = self._load()
        with self._lock:
            self._loaded = new_lists
        return new_lists

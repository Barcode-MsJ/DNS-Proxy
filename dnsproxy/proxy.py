"""Shared DNS Proxy decision engine used by CLI and Web interfaces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable
import time

from .cache import DNSCache
from .config import Config
from .domains import domain_matches, is_valid_domain_input, normalize_domain
from .lists import DomainLists
from .logger import RequestLogger
from .statistics import Statistics
from .upstream import UpstreamClient


@dataclass(frozen=True)
class QueryResult:
    domain: str
    source: str
    status: str
    ip: str
    ttl: int | str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class DNSProxyEngine:
    def __init__(self, config: Config, clock: Callable[[], float] = time.monotonic):
        self.config = config
        self.lists = DomainLists(config.ad_list_file, config.sanction_list_file)
        self.cache = DNSCache(config.cache_max_entries, clock=clock)
        self.statistics = Statistics()
        self.logger = RequestLogger(config.log_file)
        self.upstream = UpstreamClient(config)

    @property
    def startup_warnings(self) -> tuple[str, ...]:
        return self.lists.warnings

    def _finish(self, result: QueryResult) -> QueryResult:
        self.statistics.record(result.source, result.status)
        self.logger.log(result.domain, result.source, result.status, result.ip, result.ttl)
        return result

    def resolve(self, raw_domain: str) -> QueryResult:
        """Resolve one user-supplied domain according to the PDF's fixed order."""
        value = raw_domain.strip()
        if not is_valid_domain_input(value):
            shown = value if value else "(empty)"
            return self._finish(QueryResult(shown, "NONE", "INVALID_INPUT", "-", "-"))

        domain = normalize_domain(value)
        lists = self.lists.snapshot()

        # The PDF's precedence is strict: ad list, sanction list, cache, upstream.
        if any(domain_matches(domain, entry) for entry in lists.ads):
            return self._finish(QueryResult(domain, "AD_BLOCK", "OK", self.config.sinkhole_ip, self.config.local_ttl))

        if any(domain_matches(domain, entry) for entry in lists.sanctions):
            return self._finish(QueryResult(domain, "SANCTION", "OK", self.config.proxy_ip, self.config.local_ttl))

        if self.config.cache_enabled:
            cached = self.cache.get(domain)
            if cached is not None:
                return self._finish(QueryResult(domain, "CACHE", "OK", cached.ip, cached.ttl))

        reply = self.upstream.query(domain)
        if reply.status == "NOT_FOUND":
            return self._finish(QueryResult(domain, "UPSTREAM", "NOT_FOUND", "-", "-"))
        if reply.status != "OK":
            return self._finish(QueryResult(domain, "UPSTREAM", "SERVER_ERROR", "-", "-"))

        if self.config.cache_enabled and isinstance(reply.ttl, int) and reply.ttl > 0:
            self.cache.put(domain, reply.ip, reply.ttl)
        return self._finish(QueryResult(domain, "UPSTREAM", "OK", reply.ip, reply.ttl))

    def reload_lists(self) -> tuple[str, ...]:
        loaded = self.lists.reload()
        return loaded.warnings

    def cache_snapshot(self) -> list[dict[str, str | int]]:
        return [
            {"domain": domain, "ip": ip, "ttl": ttl}
            for domain, ip, ttl in self.cache.snapshot()
        ]

    def stats_snapshot(self) -> dict[str, int]:
        return self.statistics.snapshot()

    def stats_text(self) -> str:
        return self.statistics.format()

    def logs_snapshot(self, limit: int = 30) -> list[str]:
        return self.logger.recent(limit)

    def list_snapshot(self) -> dict[str, list[str]]:
        lists = self.lists.snapshot()
        return {"ads": sorted(lists.ads), "sanctions": sorted(lists.sanctions)}

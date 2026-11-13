"""Text/UDP Upstream client and optional real DNS A-record client (B6)."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class UpstreamReply:
    status: str
    ip: str = "-"
    ttl: int | str = "-"


def parse_text_reply(payload: bytes | str) -> UpstreamReply:
    try:
        text = payload.decode("ascii") if isinstance(payload, bytes) else payload
        parts = text.strip().split()
        if parts == ["NOT_FOUND"]:
            return UpstreamReply("NOT_FOUND")
        if len(parts) == 3 and parts[0] == "OK":
            ip = str(ipaddress.IPv4Address(parts[1]))
            ttl = int(parts[2])
            if ttl < 0:
                return UpstreamReply("SERVER_ERROR")
            return UpstreamReply("OK", ip, ttl)
    except (UnicodeDecodeError, ValueError):
        pass
    return UpstreamReply("SERVER_ERROR")


class UpstreamClient:
    def __init__(self, config: Config):
        self.config = config

    def query(self, domain: str) -> UpstreamReply:
        if self.config.real_dns_enabled:
            return self._query_real_dns(domain)
        return self._query_text_udp(domain)

    def _query_text_udp(self, domain: str) -> UpstreamReply:
        """Send exactly one QUERY line and wait for exactly one text response."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(self.config.upstream_timeout_sec)
                sock.sendto(f"QUERY {domain}".encode("ascii"), (self.config.upstream_ip, self.config.upstream_port))
                payload, _ = sock.recvfrom(2048)
            return parse_text_reply(payload)
        except (OSError, UnicodeError):
            return UpstreamReply("SERVER_ERROR")

    def _query_real_dns(self, domain: str) -> UpstreamReply:
        """B6: issue a real UDP DNS A query to the configured public resolver."""
        try:
            import dns.flags
            import dns.message
            import dns.query
            import dns.rcode
            import dns.rdatatype
        except ImportError:
            return UpstreamReply("SERVER_ERROR")

        try:
            query = dns.message.make_query(domain, dns.rdatatype.A)
            query.flags |= dns.flags.RD
            response = dns.query.udp(
                query,
                self.config.upstream_ip,
                timeout=self.config.upstream_timeout_sec,
                port=self.config.upstream_port,
            )
            response_code = response.rcode()
            if response_code == dns.rcode.NXDOMAIN:
                return UpstreamReply("NOT_FOUND")
            if response_code != dns.rcode.NOERROR:
                return UpstreamReply("SERVER_ERROR")

            for rrset in response.answer:
                if rrset.rdtype == dns.rdatatype.A and len(rrset) > 0:
                    first = rrset[0]
                    ip = str(ipaddress.IPv4Address(first.address))
                    ttl = int(rrset.ttl)
                    return UpstreamReply("OK", ip, ttl)
            return UpstreamReply("NOT_FOUND")
        except Exception:
            # DNS timeouts, socket failures, malformed packets and resolver errors
            # must be represented as SERVER_ERROR without crashing the proxy.
            return UpstreamReply("SERVER_ERROR")

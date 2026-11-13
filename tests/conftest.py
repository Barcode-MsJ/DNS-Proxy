from __future__ import annotations

import pytest

from dnsproxy.config import load_config
from dnsproxy.proxy import DNSProxyEngine
from upstream_mock import UpstreamMockServer


@pytest.fixture

def make_project(tmp_path):
    def factory(*, cache_enabled=True, cache_max_entries=None, timeout=0.25, sinkhole_ip="0.0.0.0", real_dns=False):
        (tmp_path / "ad_list.txt").write_text(
            "# test ads\nads.example.com\ntracker.example.net\nboth.example.com\n", encoding="utf-8"
        )
        (tmp_path / "sanction_list.txt").write_text(
            "# test sanctions\nservice.example.org\nboth.example.com\n", encoding="utf-8"
        )
        mock = None
        if not real_dns:
            mock = UpstreamMockServer("127.0.0.1", 0, ttl=5, verbose=False).start()
            upstream_ip, upstream_port = "127.0.0.1", mock.port
        else:
            upstream_ip, upstream_port = "8.8.8.8", 53
        lines = [
            f"upstream_ip={upstream_ip}", f"upstream_port={upstream_port}",
            f"upstream_timeout_sec={timeout}", f"sinkhole_ip={sinkhole_ip}",
            "proxy_ip=192.0.2.10", "local_ttl=60", "ad_list_file=ad_list.txt",
            "sanction_list_file=sanction_list.txt", f"cache_enabled={'true' if cache_enabled else 'false'}",
            f"real_dns_enabled={'true' if real_dns else 'false'}",
        ]
        if cache_max_entries is not None:
            lines.append(f"cache_max_entries={cache_max_entries}")
        (tmp_path / "config.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        config = load_config(tmp_path)
        engine = DNSProxyEngine(config)
        return engine, mock, tmp_path
    return factory

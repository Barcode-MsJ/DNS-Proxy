"""Dependency-free local Web UI for DNS Proxy.

The assignment's required core remains raw UDP text. This UI uses Python's
standard-library HTTP server so it can be run and tested without extra web
framework installation. It shares the exact DNSProxyEngine with the CLI.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dnsproxy.config import ConfigError, load_config
from dnsproxy.proxy import DNSProxyEngine

WEB_ROOT = Path(__file__).resolve().parent


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(engine: DNSProxyEngine, host: str = "127.0.0.1", port: int = 5000) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "DNSProxyWeb/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            # Keep the terminal output clean; application requests are recorded
            # in log.txt by the shared core engine.
            return

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 8192:
                raise ValueError("Request body is too large")
            raw = self.rfile.read(length)
            if not raw:
                return {}
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            return payload

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._serve_file(WEB_ROOT / "templates" / "index.html", "text/html; charset=utf-8")
            elif path == "/style.css":
                self._serve_file(WEB_ROOT / "static" / "style.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                self._serve_file(WEB_ROOT / "static" / "app.js", "application/javascript; charset=utf-8")
            elif path == "/api/status":
                cfg = engine.config
                self._json(200, {
                    "status": "online",
                    "mode": "real-dns" if cfg.real_dns_enabled else "mock-upstream",
                    "upstream": f"{cfg.upstream_ip}:{cfg.upstream_port}/UDP",
                    "cache_enabled": cfg.cache_enabled,
                    "cache_max_entries": cfg.cache_max_entries,
                    "local_ttl": cfg.local_ttl,
                    "lists": {
                        "ads": len(engine.list_snapshot()["ads"]),
                        "sanctions": len(engine.list_snapshot()["sanctions"]),
                    },
                })
            elif path == "/api/stats":
                self._json(200, engine.stats_snapshot())
            elif path == "/api/cache":
                self._json(200, {"entries": engine.cache_snapshot()})
            elif path == "/api/logs":
                self._json(200, {"entries": engine.logs_snapshot(40)})
            elif path == "/api/lists":
                self._json(200, engine.list_snapshot())
            else:
                self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            try:
                payload = self._read_json()
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})
                return

            if path == "/api/resolve":
                domain = payload.get("domain")
                if not isinstance(domain, str):
                    self._json(400, {"error": "domain must be a string"})
                    return
                result = engine.resolve(domain)
                self._json(200, result.to_dict())
            elif path == "/api/reload":
                try:
                    warnings = engine.reload_lists()
                    self._json(200, {"ok": True, "message": "Lists reloaded.", "warnings": list(warnings), "lists": engine.list_snapshot()})
                except OSError as exc:
                    self._json(500, {"ok": False, "error": str(exc)})
            else:
                self._json(404, {"error": "Not found"})

        def _serve_file(self, path: Path, content_type: str) -> None:
            try:
                body = path.read_bytes()
            except OSError:
                self._send(404, b"Not found", "text/plain; charset=utf-8")
                return
            self._send(200, body, content_type)

    return _ReusableThreadingHTTPServer((host, port), Handler)


def main() -> None:
    try:
        config = load_config(PROJECT_ROOT)
        engine = DNSProxyEngine(config)
    except (ConfigError, OSError) as exc:
        print(f"Config error: {exc}")
        raise SystemExit(1)

    server = create_server(engine, "127.0.0.1", 5000)
    print("DNS Proxy Web UI is running at http://127.0.0.1:5000", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

"""Local UDP text-protocol Upstream simulator required by the assignment."""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from dnsproxy.config import Config, load_config
from dnsproxy.domains import normalize_domain


class UpstreamMockServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5354, ttl: int = 5, verbose: bool = True):
        self.host = host
        self.port = port
        self.ttl = ttl
        self.verbose = verbose
        self.request_count = 0
        self.request_log: list[str] = []
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self) -> "UpstreamMockServer":
        if self._thread and self._thread.is_alive():
            return self
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.settimeout(0.2)
        self._socket = sock
        self.port = sock.getsockname()[1]
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="dns-upstream-mock", daemon=True)
        self._thread.start()
        return self

    def _serve(self) -> None:
        sock = self._socket
        assert sock is not None
        while not self._stop.is_set():
            try:
                payload, address = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                message = payload.decode("ascii").strip()
                parts = message.split()
                if len(parts) == 2 and parts[0] == "QUERY":
                    domain = normalize_domain(parts[1])
                    if domain == "missing.example.net":
                        reply = "NOT_FOUND"
                    else:
                        reply = f"OK 198.51.100.7 {self.ttl}"
                else:
                    domain = "-"
                    reply = "SERVER_ERROR"
                with self._lock:
                    self.request_count += 1
                    line = f"Request #{self.request_count}: {domain} -> {reply}"
                    self.request_log.append(line)
                if self.verbose:
                    print(line, flush=True)
                sock.sendto(reply.encode("ascii"), address)
            except (UnicodeDecodeError, OSError):
                continue

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def __enter__(self) -> "UpstreamMockServer":
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()


def main() -> None:
    root = Path(__file__).resolve().parent
    try:
        config: Config = load_config(root)
    except Exception as exc:
        print(f"Config error: {exc}")
        raise SystemExit(1)
    if config.real_dns_enabled:
        print("Config error: Upstream mock cannot run when real_dns_enabled=true")
        raise SystemExit(1)
    server = UpstreamMockServer(config.upstream_ip, config.upstream_port).start()
    print(f"Upstream ready on UDP {config.upstream_ip}:{config.upstream_port}.", flush=True)
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("Upstream stopped.")
    finally:
        server.stop()


if __name__ == "__main__":
    main()

"""Run CLI and Web UI together, sharing one engine/cache/statistics instance."""
from pathlib import Path
from threading import Thread

from dnsproxy.config import ConfigError, load_config
from dnsproxy.console import ConsoleApp
from dnsproxy.proxy import DNSProxyEngine
from web.app import create_server


def main() -> None:
    root = Path(__file__).resolve().parent
    try:
        config = load_config(root)
        engine = DNSProxyEngine(config)
    except (ConfigError, OSError) as exc:
        print(f"Config error: {exc}")
        raise SystemExit(1)

    server = create_server(engine, host="127.0.0.1", port=5000)
    thread = Thread(target=server.serve_forever, name="dns-proxy-web", daemon=True)
    thread.start()
    print("Web UI: http://127.0.0.1:5000", flush=True)
    try:
        ConsoleApp(engine).run()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()

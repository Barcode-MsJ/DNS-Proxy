"""Run the assignment's command-line DNS Proxy."""
from pathlib import Path

from dnsproxy.config import ConfigError, load_config
from dnsproxy.console import ConsoleApp
from dnsproxy.proxy import DNSProxyEngine


def main() -> None:
    root = Path(__file__).resolve().parent
    try:
        config = load_config(root)
        engine = DNSProxyEngine(config)
    except (ConfigError, OSError) as exc:
        print(f"Config error: {exc}")
        raise SystemExit(1)
    ConsoleApp(engine).run()


if __name__ == "__main__":
    main()

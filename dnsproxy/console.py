"""Console interface matching the five-line output contract in the PDF."""
from __future__ import annotations
import sys
from typing import TextIO

from .proxy import DNSProxyEngine, QueryResult


def format_result(result: QueryResult) -> str:
    return (
        f"Domain : {result.domain}\n"
        f"Source : {result.source}\n"
        f"Status : {result.status}\n"
        f"IP : {result.ip}\n"
        f"TTL : {result.ttl}"
    )


class ConsoleApp:
    def __init__(self, engine: DNSProxyEngine, echo_input: bool = False):
        self.engine = engine
        self.echo_input = echo_input

    def run(self, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> None:
        source = input_stream or sys.stdin
        target = output_stream or sys.stdout
        for warning in self.engine.startup_warnings:
            print(warning, file=target)
        print("DNS Proxy ready.", file=target)

        while True:
            print("Enter domain (or exit): ", end="", file=target, flush=True)
            line = source.readline()
            if line == "":
                # EOF is treated as a clean exit in non-interactive/scripted runs.
                print("Bye.", file=target)
                break
            raw = line.rstrip("\r\n")
            if self.echo_input:
                print(raw, file=target)
            command = raw.strip().lower()

            if command == "exit":
                print("Bye.", file=target)
                break
            if command == "stats":
                print(self.engine.stats_text(), file=target)
                print(file=target)
                continue
            if command == "reload":
                try:
                    warnings = self.engine.reload_lists()
                    for warning in warnings:
                        print(warning, file=target)
                    print("Lists reloaded.", file=target)
                except OSError as exc:
                    print(f"Reload error: {exc}", file=target)
                print(file=target)
                continue
            if command == "cache":
                entries = self.engine.cache_snapshot()
                if not entries:
                    print("Cache is empty.", file=target)
                else:
                    for entry in entries:
                        print(f"{entry['domain']} | {entry['ip']} | {entry['ttl']}", file=target)
                print(file=target)
                continue

            result = self.engine.resolve(raw)
            print(format_result(result), file=target)
            print(file=target)

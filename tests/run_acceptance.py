"""Run the PDF's T1-T13 acceptance scenarios and save their console transcript."""
from __future__ import annotations

from io import StringIO
from pathlib import Path
import tempfile
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dnsproxy.config import load_config
from dnsproxy.console import ConsoleApp
from dnsproxy.proxy import DNSProxyEngine
from upstream_mock import UpstreamMockServer


class FakeClock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now
    def advance(self, seconds: float): self.now += seconds


class ScriptedInput:
    def __init__(self, lines, clock: FakeClock, mock: UpstreamMockServer | None = None):
        self.lines = list(lines)
        self.clock = clock
        self.mock = mock
        self.normal_count = 0

    def readline(self):
        if not self.lines:
            return ""
        line = self.lines.pop(0)
        command = line.strip().lower()
        if command == "normal.example.net":
            self.normal_count += 1
            if self.normal_count == 2:
                self.clock.advance(2)
            elif self.normal_count == 3:
                self.clock.advance(4)
        if command == "other.example.net" and self.mock is not None:
            self.mock.stop()
        return line + "\n"


def write_project(root: Path, upstream_ip: str, upstream_port: int, *, sinkhole="0.0.0.0", cache=True, timeout=2, max_entries=None):
    (root / "ad_list.txt").write_text("ads.example.com\ntracker.example.net\nboth.example.com\n", encoding="utf-8")
    (root / "sanction_list.txt").write_text("service.example.org\nboth.example.com\n", encoding="utf-8")
    lines = [
        f"upstream_ip={upstream_ip}", f"upstream_port={upstream_port}", f"upstream_timeout_sec={timeout}",
        f"sinkhole_ip={sinkhole}", "proxy_ip=192.0.2.10", "local_ttl=60",
        "ad_list_file=ad_list.txt", "sanction_list_file=sanction_list.txt",
        f"cache_enabled={'true' if cache else 'false'}", "real_dns_enabled=false",
    ]
    if max_entries is not None:
        lines.append(f"cache_max_entries={max_entries}")
    (root / "config.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_session(root: Path, commands: list[str], mock: UpstreamMockServer, *, sinkhole="0.0.0.0", cache=True, max_entries=None, timeout=2):
    write_project(root, "127.0.0.1", mock.port, sinkhole=sinkhole, cache=cache, max_entries=max_entries, timeout=timeout)
    config = load_config(root)
    clock = FakeClock()
    engine = DNSProxyEngine(config, clock=clock)
    output = StringIO()
    ConsoleApp(engine, echo_input=True).run(ScriptedInput(commands, clock, mock), output)
    return output.getvalue(), engine


def _extract_results(transcript: str):
    lines = transcript.splitlines()
    results = []
    for index, line in enumerate(lines):
        if line.startswith("Domain : ") and index + 4 < len(lines):
            results.append({
                "domain": line.split(" : ", 1)[1],
                "source": lines[index + 1].split(" : ", 1)[1],
                "status": lines[index + 2].split(" : ", 1)[1],
                "ip": lines[index + 3].split(" : ", 1)[1],
                "ttl": lines[index + 4].split(" : ", 1)[1],
            })
    return results


def main():
    report: list[str] = []
    report.append("DNS PROXY — ACCEPTANCE TEST TRANSCRIPT")
    report.append("Source: Phase 1 assignment PDF, tests T1–T13")
    report.append("Note: TTL progression is controlled with a deterministic test clock; UDP packets are real localhost datagrams.")
    report.append("=" * 78)

    with tempfile.TemporaryDirectory(prefix="dnsproxy-acceptance-") as tmp:
        root = Path(tmp)
        mock = UpstreamMockServer("127.0.0.1", 0, ttl=5, verbose=False).start()
        commands = [
            "ads.example.com",              # T1
            "sub.ads.example.com",          # T2
            "ADS.Example.COM.",             # T3
            "notads.example.com",           # T4
            "service.example.org",          # T5
            "both.example.com",             # T6
            "normal.example.net",           # T7
            "normal.example.net",           # T8: +2s
            "normal.example.net",           # T9: +4s more; expired
            "missing.example.net",          # T10
            "missing.example.net",          # T10
            "other.example.net",             # T11: stop upstream before query
            "ads.example.com",              # T11: proxy still works
            "",                             # T12
            "bad domain.com",               # T12
            "exit",
        ]
        transcript, engine = run_session(root, commands, mock)
        expected = [
            ("ads.example.com", "AD_BLOCK", "OK"),
            ("sub.ads.example.com", "AD_BLOCK", "OK"),
            ("ads.example.com", "AD_BLOCK", "OK"),
            ("notads.example.com", "UPSTREAM", "OK"),
            ("service.example.org", "SANCTION", "OK"),
            ("both.example.com", "AD_BLOCK", "OK"),
            ("normal.example.net", "UPSTREAM", "OK"),
            ("normal.example.net", "CACHE", "OK"),
            ("normal.example.net", "UPSTREAM", "OK"),
            ("missing.example.net", "UPSTREAM", "NOT_FOUND"),
            ("missing.example.net", "UPSTREAM", "NOT_FOUND"),
            ("other.example.net", "UPSTREAM", "SERVER_ERROR"),
            ("ads.example.com", "AD_BLOCK", "OK"),
            ("(empty)", "NONE", "INVALID_INPUT"),
            ("bad domain.com", "NONE", "INVALID_INPUT"),
        ]
        actual = _extract_results(transcript)
        assert [(x["domain"], x["source"], x["status"]) for x in actual] == expected, actual
        assert actual[7]["ttl"] == "3", actual[7]
        assert mock.request_count == 5, mock.request_log
        report.append("\nT1–T12 — one fresh run, required order")
        report.append("Acceptance assertions: PASS (15 domain results; 5 UDP requests; TTL/cache/expiry/timeout verified).")
        report.append(transcript)
        report.append("Upstream simulator received:")
        report.extend(mock.request_log or ["(no requests)"])
        report.append(f"Verified upstream datagrams: {mock.request_count}")
        mock.stop()

        # T13 is explicitly run with modified configuration and a fresh process state.
        mock13 = UpstreamMockServer("127.0.0.1", 0, ttl=5, verbose=False).start()
        transcript13, engine13 = run_session(
            root,
            ["ads.example.com", "normal.example.net", "normal.example.net", "exit"],
            mock13,
            sinkhole="10.0.0.1",
            cache=False,
        )
        actual13 = _extract_results(transcript13)
        assert [(x["source"], x["status"], x["ip"]) for x in actual13] == [
            ("AD_BLOCK", "OK", "10.0.0.1"), ("UPSTREAM", "OK", "198.51.100.7"), ("UPSTREAM", "OK", "198.51.100.7")
        ], actual13
        assert mock13.request_count == 2, mock13.request_log
        report.append("\nT13 — changed config: sinkhole_ip=10.0.0.1, cache_enabled=false")
        report.append("Acceptance assertions: PASS (custom sinkhole IP and two upstream requests with cache disabled).")
        report.append(transcript13)
        report.append("Upstream simulator received (two normal lookups prove cache is disabled):")
        report.extend(mock13.request_log)
        report.append(f"Verified upstream datagrams: {mock13.request_count}")
        mock13.stop()

        report.append("\nBonus feature verification (B1–B6)")
        report.append("B1: Statistics counters are exercised by the unit/integration test suite.")
        report.append("B2: Reload reads both list files again; covered by test_reload_lists_updates_policy_without_restart.")
        report.append("B3: Cache command/API returns only live entries with remaining TTL; covered by cache tests.")
        report.append("B4: log.txt appends timestamp | domain | source | status | IP | TTL; covered by log tests.")
        report.append("B5: FIFO eviction at cache_max_entries=2; covered by test_fifo_cache_limit_and_disabled_cache.")
        report.append("B6: Real DNS A/TTL extraction and NXDOMAIN mapping are tested with deterministic DNS wire-response fixtures.")
        report.append("B6 live public DNS: UDP/53 probes to both 8.8.8.8 and 1.1.1.1 timed out in this execution environment; no live resolver result is claimed.")

    output_path = Path(__file__).resolve().parents[1] / "test_results.txt"
    output_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Acceptance transcript written to: {output_path}")
    print(f"Transcript size: {output_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()

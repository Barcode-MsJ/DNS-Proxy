from dnsproxy.console import ConsoleApp
from io import StringIO


def test_ads_and_subdomains_are_blocked_without_upstream(make_project):
    engine, mock, _ = make_project()
    try:
        assert engine.resolve("ads.example.com").source == "AD_BLOCK"
        assert engine.resolve("sub.ads.example.com").source == "AD_BLOCK"
        assert mock.request_count == 0
    finally: mock.stop()


def test_normalization_and_no_false_suffix_match(make_project):
    engine, mock, _ = make_project()
    try:
        normalized = engine.resolve("ADS.Example.COM.")
        assert (normalized.domain, normalized.source) == ("ads.example.com", "AD_BLOCK")
        unrelated = engine.resolve("notads.example.com")
        assert unrelated.source == "UPSTREAM"
        assert mock.request_count == 1
    finally: mock.stop()


def test_sanction_and_ad_priority(make_project):
    engine, mock, _ = make_project()
    try:
        sanction = engine.resolve("service.example.org")
        both = engine.resolve("both.example.com")
        assert (sanction.source, sanction.ip, sanction.ttl) == ("SANCTION", "192.0.2.10", 60)
        assert (both.source, both.ip) == ("AD_BLOCK", "0.0.0.0")
        assert mock.request_count == 0
    finally: mock.stop()


def test_upstream_then_cache_hit(make_project):
    engine, mock, _ = make_project()
    try:
        first = engine.resolve("normal.example.net")
        second = engine.resolve("normal.example.net")
        assert (first.source, first.status, first.ip, first.ttl) == ("UPSTREAM", "OK", "198.51.100.7", 5)
        assert (second.source, second.status) == ("CACHE", "OK")
        assert second.ttl in {4, 5}
        assert mock.request_count == 1
    finally: mock.stop()


def test_not_found_is_not_cached(make_project):
    engine, mock, _ = make_project()
    try:
        first = engine.resolve("missing.example.net")
        second = engine.resolve("missing.example.net")
        assert first.status == second.status == "NOT_FOUND"
        assert first.source == second.source == "UPSTREAM"
        assert mock.request_count == 2
    finally: mock.stop()


def test_timeout_does_not_crash_and_next_request_still_works(make_project):
    engine, mock, _ = make_project(timeout=0.1)
    mock.stop()
    result = engine.resolve("other.example.net")
    after = engine.resolve("ads.example.com")
    assert result.status == "SERVER_ERROR"
    assert after.status == "OK" and after.source == "AD_BLOCK"


def test_empty_and_invalid_inputs(make_project):
    engine, mock, _ = make_project()
    try:
        empty = engine.resolve("")
        bad = engine.resolve("bad domain.com")
        assert (empty.domain, empty.source, empty.status, empty.ip, empty.ttl) == ("(empty)", "NONE", "INVALID_INPUT", "-", "-")
        assert (bad.domain, bad.source, bad.status) == ("bad domain.com", "NONE", "INVALID_INPUT")
        assert mock.request_count == 0
    finally: mock.stop()


def test_reload_lists_updates_policy_without_restart(make_project):
    engine, mock, root = make_project()
    try:
        (root / "ad_list.txt").write_text("newad.example.com\n", encoding="utf-8")
        engine.reload_lists()
        result = engine.resolve("newad.example.com")
        assert result.source == "AD_BLOCK"
        assert mock.request_count == 0
    finally: mock.stop()


def test_bad_list_line_warns_and_is_skipped(make_project):
    engine, mock, root = make_project()
    try:
        (root / "ad_list.txt").write_text("ads.example.com\nbad domain.com\n", encoding="utf-8")
        warnings = engine.reload_lists()
        assert warnings == ("Warning: bad line in ad_list.txt: bad domain.com",)
        assert engine.resolve("bad domain.com").status == "INVALID_INPUT"
    finally: mock.stop()


def test_bonus_stats_and_log_are_recorded(make_project):
    engine, mock, root = make_project()
    try:
        engine.resolve("ads.example.com")
        engine.resolve("normal.example.net")
        engine.resolve("normal.example.net")
        engine.resolve("bad domain.com")
        stats = engine.stats_snapshot()
        assert stats == {"Total": 4, "AD_BLOCK": 1, "SANCTION": 0, "CACHE": 1, "UPSTREAM": 1, "ERRORS": 1}
        log_lines = (root / "log.txt").read_text(encoding="utf-8").splitlines()
        assert len(log_lines) == 4
        assert " | AD_BLOCK | OK | 0.0.0.0 | 60" in log_lines[0]
        assert " | NONE | INVALID_INPUT | - | -" in log_lines[-1]
    finally: mock.stop()


def test_console_commands_and_exact_five_line_block(make_project):
    engine, mock, _ = make_project()
    try:
        output = StringIO()
        ConsoleApp(engine).run(StringIO("ads.example.com\nstats\ncache\nexit\n"), output)
        text = output.getvalue()
        assert "DNS Proxy ready." in text
        assert "Domain : ads.example.com\nSource : AD_BLOCK\nStatus : OK\nIP : 0.0.0.0\nTTL : 60" in text
        assert "Total: 1 | AD_BLOCK: 1 | SANCTION: 0 | CACHE: 0 | UPSTREAM: 0 | ERRORS: 0" in text
        assert "Cache is empty." in text
        assert text.rstrip().endswith("Bye.")
    finally: mock.stop()


def test_fifo_cache_limit_and_disabled_cache(make_project):
    engine, mock, _ = make_project(cache_max_entries=2)
    try:
        for domain in ("site1.example.net", "site2.example.net", "site3.example.net"):
            assert engine.resolve(domain).source == "UPSTREAM"
        assert [item["domain"] for item in engine.cache_snapshot()] == ["site2.example.net", "site3.example.net"]
        assert engine.resolve("site1.example.net").source == "UPSTREAM"
        assert mock.request_count == 4
    finally: mock.stop()

    engine2, mock2, _ = make_project(cache_enabled=False)
    try:
        engine2.resolve("normal.example.net")
        engine2.resolve("normal.example.net")
        assert mock2.request_count == 2
        assert engine2.cache_snapshot() == []
    finally: mock2.stop()

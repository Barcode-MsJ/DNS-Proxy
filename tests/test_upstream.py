import dns.flags
import dns.message
import dns.rdatatype
import dns.rrset

from dnsproxy.upstream import UpstreamClient, parse_text_reply


def test_text_protocol_parser():
    assert parse_text_reply("OK 198.51.100.7 5").status == "OK"
    assert parse_text_reply("NOT_FOUND").status == "NOT_FOUND"
    for invalid in ("OK 999.1.1.1 5", "OK 198.51.100.7 -1", "OK 198.51.100.7", "SERVER_ERROR", "garbage"):
        assert parse_text_reply(invalid).status == "SERVER_ERROR"


def test_real_dns_b6_extracts_a_record_and_real_ttl(make_project, monkeypatch):
    engine, mock, _ = make_project(real_dns=True)
    try:
        query = dns.message.make_query("example.com", dns.rdatatype.A)
        response = dns.message.make_response(query)
        response.answer.append(dns.rrset.from_text("example.com.", 245, "IN", "A", "93.184.216.34"))
        calls = {}
        def fake_udp(q, server, timeout, port):
            calls.update(server=server, timeout=timeout, port=port)
            return response
        monkeypatch.setattr("dns.query.udp", fake_udp)
        result = engine.resolve("example.com")
        assert (result.source, result.status, result.ip, result.ttl) == ("UPSTREAM", "OK", "93.184.216.34", 245)
        assert calls == {"server": "8.8.8.8", "timeout": 0.25, "port": 53}
        cached = engine.resolve("example.com")
        assert cached.source == "CACHE"
    finally:
        if mock: mock.stop()


def test_real_dns_nxdomain_maps_to_not_found(make_project, monkeypatch):
    engine, mock, _ = make_project(real_dns=True)
    try:
        query = dns.message.make_query("missing.example", dns.rdatatype.A)
        response = dns.message.make_response(query)
        response.set_rcode(3)
        monkeypatch.setattr("dns.query.udp", lambda *args, **kwargs: response)
        result = engine.resolve("missing.example")
        assert result.status == "NOT_FOUND"
        assert result.ip == result.ttl == "-"
    finally:
        if mock: mock.stop()


def test_real_dns_timeout_maps_to_server_error(make_project, monkeypatch):
    engine, mock, _ = make_project(real_dns=True)
    try:
        def timeout(*args, **kwargs):
            raise TimeoutError("simulated DNS timeout")
        monkeypatch.setattr("dns.query.udp", timeout)
        result = engine.resolve("example.com")
        assert result.source == "UPSTREAM"
        assert result.status == "SERVER_ERROR"
        assert result.ip == result.ttl == "-"
    finally:
        if mock: mock.stop()

import json
from threading import Thread
from urllib.request import Request, urlopen

from web.app import create_server


def test_web_dashboard_and_api_share_engine(make_project):
    engine, mock, _ = make_project()
    server = create_server(engine, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(base + "/") as response:
            page = response.read().decode("utf-8")
            assert response.status == 200
            assert "داشبورد DNS Proxy" in page
        with urlopen(base + "/api/status") as response:
            status = json.loads(response.read())
            assert status["status"] == "online"
        request = Request(base + "/api/resolve", data=json.dumps({"domain": "ads.example.com"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            result = json.loads(response.read())
            assert result["source"] == "AD_BLOCK"
        with urlopen(base + "/api/stats") as response:
            stats = json.loads(response.read())
            assert stats["Total"] == 1
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=1)
        mock.stop()


def test_web_reload_endpoint_updates_lists(make_project):
    engine, mock, root = make_project()
    server = create_server(engine, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        (root / "ad_list.txt").write_text("freshad.example.com\n", encoding="utf-8")
        request = Request(base + "/api/reload", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request) as response:
            result = json.loads(response.read())
        assert result["ok"] is True
        assert "freshad.example.com" in result["lists"]["ads"]
        assert engine.resolve("freshad.example.com").source == "AD_BLOCK"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=1)
        mock.stop()

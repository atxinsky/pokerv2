import json
import threading
import urllib.error
import urllib.request

from pokergym.server import make_server, reset_session


def _start():
    httpd = make_server("127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, httpd.server_address[1]


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read()


def _post(port, path, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode())


def test_pages_and_api():
    reset_session(seed=1, mode="train")
    httpd, port = _start()
    try:
        st, html = _get(port, "/")
        assert st == 200
        text = html.decode("utf-8")
        assert "PokerGym" in text
        assert "fonts.googleapis" not in text
        assert "gto-grid" in text
        assert "/js/app.js" in text
        assert "id=\"legal\"" in text
        assert "id=\"bet-amount\"" in text
        assert "id=\"hist\"" in text
        st, css = _get(port, "/css/app.css")
        assert st == 200
        assert b"--felt" in css
        st, js = _get(port, "/js/app.js")
        assert st == 200
        assert b"confirmBet" in js
        st, body = _get(port, "/api/state")
        data = json.loads(body.decode())
        assert data["waiting"] in ("hero", "bot", "over")
        assert len(data["seats"]) == 8
        st, data = _post(port, "/api/new", {"seed": 2, "mode": "train"})
        assert st == 200
        assert len(data["seats"]) == 8
        # 推进到英雄或结束
        for _ in range(24):
            if data["waiting"] != "bot":
                break
            st, data = _post(port, "/api/step", {})
        if data["waiting"] == "hero":
            kinds = {x["kind"] for x in data["legal"]}
            kind = "check" if "check" in kinds else ("call" if "call" in kinds else "fold")
            st, data = _post(port, "/api/action", {"kind": kind})
            assert st == 200
            assert data["waiting"] in ("hero", "bot", "over")
    finally:
        httpd.shutdown()

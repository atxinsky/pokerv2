"""本地 HTTP：静态页 + JSON API。无第三方依赖。"""

from __future__ import annotations

import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pokergym.live import LiveSession
from pokergym.serialize import dump_state

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"

_lock = threading.Lock()
_session: LiveSession | None = None


def get_session() -> LiveSession:
    global _session
    if _session is None:
        _session = LiveSession()
        _session.new_hand()
    return _session


def reset_session(seed: int = 1, mode: str = "train") -> LiveSession:
    global _session
    _session = LiveSession(seed=seed, mode=mode)
    _session.new_hand()
    return _session


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0:
            return {}
        body = self.rfile.read(n)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            with _lock:
                self._json(dump_state(get_session()))
            return
        if path == "/":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._json({"error": "JSON 无效"}, 400)
            return
        with _lock:
            if path == "/api/new":
                seed = int(payload.get("seed", 1))
                mode = payload.get("mode", "train")
                if mode not in ("train", "realism"):
                    mode = "train"
                sess = reset_session(seed, mode)
                self._json(dump_state(sess))
                return
            if path == "/api/hand":
                sess = get_session()
                sess.new_hand()
                self._json(dump_state(sess))
                return
            if path == "/api/step":
                sess = get_session()
                sess.step_bot()
                self._json(dump_state(sess))
                return
            if path == "/api/action":
                sess = get_session()
                kind = payload.get("kind")
                if kind not in ("fold", "check", "call", "bet", "raise"):
                    self._json({"error": "未知动作"}, 400)
                    return
                to_bb = payload.get("to_bb")
                try:
                    sess.hero_act(kind, to_bb)
                except RuntimeError as e:
                    self._json({"error": str(e)}, 409)
                    return
                self._json(dump_state(sess))
                return
        self._json({"error": "无此接口"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.end_headers()


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    return httpd


def serve_forever(host: str = "127.0.0.1", port: int = 8765):
    httpd = make_server(host, port)
    print(f"PokerGym  http://{host}:{port}/")
    httpd.serve_forever()

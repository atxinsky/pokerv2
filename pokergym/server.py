"""本地 HTTP：静态页 + JSON API。无第三方依赖。"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pokergym.live import LiveSession
from pokergym.serialize import dump_state
from pokergym.store import apply_env, export_hands, lower_intensity, public_settings, save_settings

apply_env()

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"

_lock = threading.RLock()
_session: LiveSession | None = None


def get_session() -> LiveSession:
    global _session
    if _session is None:
        _session = LiveSession()
        _session.new_hand()
    return _session


def reset_session(seed: int = 1, mode: str = "train", wait_llm: bool = False) -> LiveSession:
    global _session
    _session = LiveSession(seed=seed, mode=mode, wait_llm=wait_llm)
    _session.new_hand()
    return _session


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        path = urlparse(self.path).path
        if path.endswith((".js", ".css", ".html")) or path in ("/", "/index.html"):
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Pragma", "no-cache")
        super().end_headers()

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
        if path == "/api/settings":
            self._json(public_settings())
            return
        if path == "/api/export.json":
            raw = json.dumps(export_hands(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=pokergym-hands.json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
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
        if path == "/api/llm-ping":
            from pokergym.deepseek import ping
            from pokergym.store import log_llm

            apply_env()
            info = ping()
            log_llm(info["msg"])
            self._json(info)
            return
        with _lock:
            if path == "/api/settings":
                info = save_settings(payload)
                apply_env()
                self._json(info)
                return
            if path == "/api/usage/lower":
                info = lower_intensity()
                self._json(info)
                return
            if path == "/api/new":
                seed = int(payload.get("seed", 1))
                mode = payload.get("mode", "train")
                if mode not in ("train", "realism"):
                    mode = "train"
                try:
                    from pokergym.store import set_setting

                    set_setting("product_mode", mode)
                    apply_env()
                except Exception:
                    pass
                wait = bool(payload.get("wait_llm"))
                sess = reset_session(seed, mode, wait_llm=wait)
                self._json(dump_state(sess))
                return
            if path == "/api/hand":
                sess = get_session()
                sess.new_hand()
                self._json(dump_state(sess))
                return
            if path == "/api/step":
                sess = get_session()

                @contextmanager
                def _unlock():
                    # LLM 调用期间释放锁，让 GET /api/state 能读到 thinking
                    _lock.release()
                    try:
                        yield
                    finally:
                        _lock.acquire()

                sess.step_bot(unlock=_unlock)
                self._json(dump_state(sess))
                return
            if path == "/api/review-detail":
                sess = get_session()
                try:
                    text_out = sess.request_review_detail()
                except Exception as e:
                    self._json({"error": str(e)}, 500)
                    return
                self._json({"ok": bool(text_out), "llm_review": text_out, "state": dump_state(sess)})
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

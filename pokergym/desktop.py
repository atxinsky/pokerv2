"""桌面窗口：优先 Edge/Chrome --app，不行就开浏览器。"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from pokergym.server import make_server


def _edge() -> str | None:
    for p in (
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ):
        if p and Path(p).is_file():
            return p
    return shutil.which("msedge")


def _chrome() -> str | None:
    for p in (
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ):
        if p and Path(p).is_file():
            return p
    return shutil.which("chrome")


def open_desktop(url: str) -> bool:
    app = _edge() or _chrome()
    if not app:
        webbrowser.open(url)
        return False
    subprocess.Popen(
        [app, f"--app={url}", "--window-size=1480,920", "--new-window"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _bind(host: str, port: int):
    last = None
    for p in range(port, port + 15):
        try:
            return make_server(host, p), p
        except OSError as e:
            last = e
    raise RuntimeError(f"端口占用: {last}")


def run_ui(host: str = "127.0.0.1", port: int = 8765, browser: bool = False):
    httpd, port = _bind(host, port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    url = f"http://{host}:{port}/"
    # 等端口起来
    time.sleep(0.15)
    print(f"PokerGym 桌面  {url}")
    if browser:
        webbrowser.open(url)
    else:
        open_desktop(url)
    try:
        while True:
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("关闭中")
        httpd.shutdown()

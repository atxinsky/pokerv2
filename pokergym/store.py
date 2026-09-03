"""本地 SQLite：设置 + 牌谱。密钥只存在本机。"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


def _db_path() -> Path:
    raw = os.environ.get("POKERGYM_DB")
    if raw:
        p = Path(raw)
    else:
        p = Path(__file__).resolve().parent.parent / "data" / "pokergym.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_path(), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _lock:
        c = _conn()
        try:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    played_at TEXT NOT NULL,
                    seed INTEGER,
                    mode TEXT,
                    hand_idx INTEGER,
                    delta_bb REAL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS llm_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    msg TEXT NOT NULL
                );
                """
            )
            c.commit()
        finally:
            c.close()


def get_setting(k: str, default: str = "") -> str:
    init()
    with _lock:
        c = _conn()
        try:
            row = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
            return row["v"] if row else default
        finally:
            c.close()


def set_setting(k: str, v: str) -> None:
    init()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (k, v),
            )
            c.commit()
        finally:
            c.close()


def apply_env() -> None:
    """把库里的密钥灌进环境变量，供 DeepSeek 客户端读取。"""
    init()
    key = get_setting("deepseek_key")
    if key:
        os.environ["DEEPSEEK_API_KEY"] = key
    base = get_setting("deepseek_base", "https://api.deepseek.com")
    if base:
        os.environ["DEEPSEEK_BASE_URL"] = base
    model = get_setting("deepseek_model", "deepseek-chat")
    if model:
        os.environ["DEEPSEEK_MODEL"] = model
    enabled = get_setting("llm_enabled", "1")
    os.environ["POKERGYM_LLM"] = enabled if enabled in ("0", "1") else "1"
    brain = get_setting("llm_brain", "0")
    os.environ["POKERGYM_LLM_BRAIN"] = brain if brain in ("0", "1") else "0"


def public_settings() -> dict:
    key = get_setting("deepseek_key")
    masked = ""
    if key:
        masked = ("*" * max(0, len(key) - 4)) + key[-4:]
    return {
        "deepseek_key_masked": masked,
        "has_key": bool(key),
        "deepseek_base": get_setting("deepseek_base", "https://api.deepseek.com"),
        "deepseek_model": get_setting("deepseek_model", "deepseek-chat"),
        "llm_enabled": get_setting("llm_enabled", "1") != "0",
        "llm_brain": get_setting("llm_brain", "0") == "1",
        "hint": "密钥只发往 DeepSeek 官方接口，牌谱存在本机 SQLite，不走 Google。",
    }


def save_settings(payload: dict) -> dict:
    if "llm_enabled" in payload:
        set_setting("llm_enabled", "1" if payload.get("llm_enabled") else "0")
    if "llm_brain" in payload:
        set_setting("llm_brain", "1" if payload.get("llm_brain") else "0")
    if payload.get("deepseek_base"):
        set_setting("deepseek_base", str(payload["deepseek_base"]).strip())
    if payload.get("deepseek_model"):
        set_setting("deepseek_model", str(payload["deepseek_model"]).strip())
    key = payload.get("deepseek_key")
    if isinstance(key, str) and key.strip() and "*" not in key:
        set_setting("deepseek_key", key.strip())
    apply_env()
    return public_settings()


def insert_hand(payload: dict) -> None:
    init()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO hands(played_at, seed, mode, hand_idx, delta_bb, payload) VALUES (?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    payload.get("seed"),
                    payload.get("mode"),
                    payload.get("hand_idx"),
                    payload.get("delta_bb"),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            c.commit()
        finally:
            c.close()


def list_hands(limit: int = 40) -> list[dict]:
    init()
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT payload FROM hands ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            c.close()
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["payload"]))
        except json.JSONDecodeError:
            continue
    return out


def export_hands() -> list[dict]:
    return list_hands(limit=5000)


def log_llm(msg: str) -> None:
    init()
    with _lock:
        c = _conn()
        try:
            c.execute(
                "INSERT INTO llm_log(at, msg) VALUES (?,?)",
                (datetime.now(timezone.utc).isoformat(), msg[:300]),
            )
            c.execute("DELETE FROM llm_log WHERE id NOT IN (SELECT id FROM llm_log ORDER BY id DESC LIMIT 30)")
            c.commit()
        finally:
            c.close()


def llm_logs(limit: int = 12) -> list[dict]:
    init()
    with _lock:
        c = _conn()
        try:
            rows = c.execute(
                "SELECT at, msg FROM llm_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            c.close()
    return [{"at": r["at"], "msg": r["msg"]} for r in rows]

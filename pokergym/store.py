"""本地 SQLite：设置 + 牌谱。密钥只存在本机。"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()

# Phase 1：全桌 LLM 出牌强度 → 用 LLM 的对手座位数比例
BRAIN_INTENSITY = {
    "full": 1.0,    # 全部对手
    "high": 0.75,
    "med": 0.5,
    "low": 0.25,    # 约 1/4，8 人桌约 2 个
    "sparse": 0.25,
}


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


def _normalize_intensity(raw: str | None) -> str:
    v = (raw or "full").strip().lower()
    if v in BRAIN_INTENSITY:
        return v
    if v in ("medium", "mid"):
        return "med"
    return "full"


def _normalize_timeout(raw: str | None, default: float = 12.0) -> float:
    try:
        t = float(raw) if raw not in (None, "") else default
    except (TypeError, ValueError):
        t = default
    return max(3.0, min(30.0, t))


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
    # Phase 1 默认：有 Key 时全桌 LLM 出牌开（显式存 0 才关）
    brain_row = get_setting("llm_brain", "")
    if brain_row == "":
        brain = "1" if key else "0"
    else:
        brain = brain_row if brain_row in ("0", "1") else "1"
    os.environ["POKERGYM_LLM_BRAIN"] = brain
    intensity = _normalize_intensity(get_setting("llm_brain_intensity", "full"))
    os.environ["POKERGYM_LLM_BRAIN_INTENSITY"] = intensity
    timeout = _normalize_timeout(get_setting("llm_brain_timeout", "12"))
    os.environ["POKERGYM_LLM_BRAIN_TIMEOUT"] = str(timeout)
    # Phase 2: hero coaching
    coach = get_setting("coach_enabled", "1")
    os.environ["POKERGYM_COACH"] = coach if coach in ("0", "1") else "1"
    pre = get_setting("coach_pre_hint", "0")
    os.environ["POKERGYM_COACH_PRE_HINT"] = pre if pre in ("0", "1") else "0"
    mode = get_setting("product_mode", "train")
    if mode not in ("train", "realism"):
        mode = "train"
    os.environ["POKERGYM_MODE"] = mode


def _usage_public() -> dict:
    try:
        from pokergym.usage import snapshot

        return snapshot()
    except Exception:
        return {
            "calls": 0,
            "total_tokens": 0,
            "est_usd": 0.0,
            "session_total_tokens": 0,
            "session_est_usd": 0.0,
        }


def lower_intensity() -> dict:
    """One-click softer LLM seat coverage; returns updated public settings."""
    cur = _normalize_intensity(get_setting("llm_brain_intensity", "full"))
    from pokergym.usage import next_lower_intensity

    nxt = next_lower_intensity(cur)
    if nxt is None:
        apply_env()
        out = public_settings()
        out["intensity_changed"] = False
        out["intensity_note"] = "已经是最低强度"
        return out
    set_setting("llm_brain_intensity", nxt)
    apply_env()
    out = public_settings()
    out["intensity_changed"] = True
    out["intensity_note"] = f"强度 {cur} → {nxt}"
    return out


def public_settings() -> dict:
    key = get_setting("deepseek_key")
    masked = ""
    if key:
        masked = ("*" * max(0, len(key) - 4)) + key[-4:]
    brain_row = get_setting("llm_brain", "")
    if brain_row == "":
        brain_on = bool(key)
    else:
        brain_on = brain_row == "1"
    intensity = _normalize_intensity(get_setting("llm_brain_intensity", "full"))
    timeout = _normalize_timeout(get_setting("llm_brain_timeout", "12"))
    return {
        "deepseek_key_masked": masked,
        "has_key": bool(key),
        "deepseek_base": get_setting("deepseek_base", "https://api.deepseek.com"),
        "deepseek_model": get_setting("deepseek_model", "deepseek-chat"),
        "llm_enabled": get_setting("llm_enabled", "1") != "0",
        "llm_brain": brain_on,
        "llm_brain_intensity": intensity,
        "llm_brain_timeout": timeout,
        "coach_enabled": get_setting("coach_enabled", "1") != "0",
        "coach_pre_hint": get_setting("coach_pre_hint", "0") == "1",
        "product_mode": get_setting("product_mode", "train") if get_setting("product_mode", "train") in ("train", "realism") else "train",
        "usage": _usage_public(),
        "hint": "密钥只发往 DeepSeek 官方接口，牌谱存在本机 SQLite，不走 Google。有 Key 时默认全桌 LLM 出牌。产品卖点是 LLM 对手 + LLM 教练；GTO 范围图仅作参考。",
    }


def save_settings(payload: dict) -> dict:
    if "llm_enabled" in payload:
        set_setting("llm_enabled", "1" if payload.get("llm_enabled") else "0")
    if "llm_brain" in payload:
        set_setting("llm_brain", "1" if payload.get("llm_brain") else "0")
    if "llm_brain_intensity" in payload:
        set_setting("llm_brain_intensity", _normalize_intensity(str(payload.get("llm_brain_intensity"))))
    if "llm_brain_timeout" in payload:
        set_setting("llm_brain_timeout", str(_normalize_timeout(str(payload.get("llm_brain_timeout")))))
    if "coach_enabled" in payload:
        set_setting("coach_enabled", "1" if payload.get("coach_enabled") else "0")
    if "coach_pre_hint" in payload:
        set_setting("coach_pre_hint", "1" if payload.get("coach_pre_hint") else "0")
    if "product_mode" in payload:
        mode = str(payload.get("product_mode") or "train").strip().lower()
        set_setting("product_mode", mode if mode in ("train", "realism") else "train")
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

def update_hand_llm_review(hand_idx: int, llm_review: str) -> None:
    """Attach LLM review text onto the newest matching hand row."""
    if not llm_review:
        return
    init()
    with _lock:
        c = _conn()
        try:
            row = c.execute(
                "SELECT id, payload FROM hands WHERE hand_idx=? ORDER BY id DESC LIMIT 1",
                (hand_idx,),
            ).fetchone()
            if not row:
                return
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                return
            payload["llm_review"] = llm_review
            rev = payload.get("review")
            if isinstance(rev, dict):
                rev = dict(rev)
                rev["llm"] = llm_review
                payload["review"] = rev
            c.execute(
                "UPDATE hands SET payload=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), row["id"]),
            )
            c.commit()
        finally:
            c.close()

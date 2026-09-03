"""DeepSeek Chat。只塑造人格/适应/复盘文案，不选动作。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pokergym.envload import load_dotenv

LAST_ERROR = ""

ALLOWED_DELTA = (
    "threebet_freq",
    "squeeze_freq",
    "bluff_mult",
    "cbet_freq",
    "fold_to_cbet",
    "call_station_idx",
    "river_bluff_freq",
    "fold_bias",
)


def available() -> bool:
    load_dotenv()
    try:
        from pokergym.store import apply_env

        apply_env()
    except Exception:
        pass
    if os.environ.get("POKERGYM_LLM", "1") == "0":
        return False
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def status() -> dict:
    on = available()
    hint = "DeepSeek 已接通，对手人格/适应走大模型"
    if not on:
        hint = "设置里填 DeepSeek Key 才会调用大模型；没 Key 用规则人格"
    if LAST_ERROR:
        hint = f"DeepSeek 失败：{LAST_ERROR}"
    return {
        "enabled": on,
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat") if on else None,
        "hint": hint,
        "error": LAST_ERROR or None,
    }


def chat_json(
    system: str,
    user: str,
    timeout: float = 12.0,
    temperature: float = 0.7,
    max_tokens: int = 700,
) -> dict | None:
    global LAST_ERROR
    load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        LAST_ERROR = ""
        return json.loads(text)
    except urllib.error.HTTPError as e:
        LAST_ERROR = f"HTTP {e.code}"
        return None
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, IndexError, OSError) as e:
        LAST_ERROR = type(e).__name__
        return None


def ping() -> dict:
    data = chat_json(
        '只输出 JSON：{"ok":true,"msg":"pong"}',
        "连通测试",
        timeout=10,
    )
    if data and (data.get("ok") or data.get("msg")):
        return {"ok": True, "msg": "DeepSeek 连通正常"}
    return {"ok": False, "msg": f"连通失败 {LAST_ERROR or '无返回'}"}


def clamp_delta(delta: dict | None) -> dict:
    out = {}
    if not isinstance(delta, dict):
        return out
    for k, v in delta.items():
        if k not in ALLOWED_DELTA:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        out[k] = max(-0.15, min(0.15, x))
    return out

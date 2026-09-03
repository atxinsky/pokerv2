"""DeepSeek Chat。只塑造人格/适应/复盘文案，不选动作。"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pokergym.envload import load_dotenv

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
    if os.environ.get("POKERGYM_LLM", "1") == "0":
        return False
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def status() -> dict:
    load_dotenv()
    on = available()
    return {
        "enabled": on,
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat") if on else None,
        "hint": "DeepSeek 已接通，对手会读你" if on else "未配置 DEEPSEEK_API_KEY，对手用规则人格",
    }


def chat_json(system: str, user: str, timeout: float = 12.0) -> dict | None:
    load_dotenv()
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    body = {
        "model": model,
        "temperature": 0.7,
        "max_tokens": 700,
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
        return json.loads(text)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError, IndexError):
        return None


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

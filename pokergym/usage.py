"""Session / lifetime LLM token usage estimates (local only)."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()

# Approximate DeepSeek chat list prices (USD per 1M tokens). Estimates only.
USD_PER_M_PROMPT = 0.14
USD_PER_M_COMPLETION = 0.28

_INTENSITY_STEPS = ("full", "high", "med", "low")

_state = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "calls": 0,
    "session_prompt_tokens": 0,
    "session_completion_tokens": 0,
    "session_calls": 0,
}


def reset_session() -> None:
    with _lock:
        _state["session_prompt_tokens"] = 0
        _state["session_completion_tokens"] = 0
        _state["session_calls"] = 0


def record(prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    pt = max(0, int(prompt_tokens or 0))
    ct = max(0, int(completion_tokens or 0))
    with _lock:
        _state["prompt_tokens"] += pt
        _state["completion_tokens"] += ct
        _state["calls"] += 1
        _state["session_prompt_tokens"] += pt
        _state["session_completion_tokens"] += ct
        _state["session_calls"] += 1


def estimate_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens / 1_000_000 * USD_PER_M_PROMPT
        + completion_tokens / 1_000_000 * USD_PER_M_COMPLETION,
        6,
    )


def snapshot() -> dict[str, Any]:
    with _lock:
        pt = _state["prompt_tokens"]
        ct = _state["completion_tokens"]
        spt = _state["session_prompt_tokens"]
        sct = _state["session_completion_tokens"]
        calls = _state["calls"]
        scalls = _state["session_calls"]
    total = pt + ct
    session_total = spt + sct
    return {
        "calls": calls,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": total,
        "est_usd": estimate_usd(pt, ct),
        "session_calls": scalls,
        "session_prompt_tokens": spt,
        "session_completion_tokens": sct,
        "session_total_tokens": session_total,
        "session_est_usd": estimate_usd(spt, sct),
        "hint": "用量为 DeepSeek 返回的 token 累计；费用按公开价目粗估，仅供控成本参考。",
    }


def next_lower_intensity(current: str) -> str | None:
    """One step softer: full→high→med→low. None if already lowest."""
    v = (current or "full").strip().lower()
    if v == "sparse":
        v = "low"
    if v not in _INTENSITY_STEPS:
        v = "full"
    i = _INTENSITY_STEPS.index(v)
    if i >= len(_INTENSITY_STEPS) - 1:
        return None
    return _INTENSITY_STEPS[i + 1]


def bump_intensity_for_realism(current: str) -> str:
    """Realism wants tougher LLM opponents: bump one notch toward full."""
    v = (current or "full").strip().lower()
    if v == "sparse":
        v = "low"
    if v not in _INTENSITY_STEPS:
        return "full"
    i = _INTENSITY_STEPS.index(v)
    if i <= 0:
        return "full"
    return _INTENSITY_STEPS[i - 1]

"""Product modes: train (coach on) vs realism (fewer hints, tougher LLM)."""

from __future__ import annotations

from pokergym.const import MODE_REALISM, MODE_TRAIN
from pokergym.usage import bump_intensity_for_realism

VALID_MODES = (MODE_TRAIN, MODE_REALISM)


def normalize_mode(raw: str | None) -> str:
    v = (raw or MODE_TRAIN).strip().lower()
    return v if v in VALID_MODES else MODE_TRAIN


def effective_intensity(stored: str, mode: str) -> str:
    """Realism bumps LLM seat coverage one notch toward full."""
    v = (stored or "full").strip().lower()
    if mode == MODE_REALISM:
        return bump_intensity_for_realism(v)
    return v if v in ("full", "high", "med", "low", "sparse") else "full"


def pre_hint_allowed(mode: str, setting_on: bool) -> bool:
    """Realism suppresses pre-action hints even if the setting is on."""
    if mode == MODE_REALISM:
        return False
    return bool(setting_on)


def coach_default_on(mode: str) -> bool:
    """Train defaults coach on; realism still allows post-hand review unless user disables."""
    return mode != MODE_REALISM or True  # post-hand review stays available


def realism_tougher_prompt_extra(mode: str) -> str:
    if mode != MODE_REALISM:
        return ""
    return (
        "拟真模式：对手更凶、更会施压，诈唬与价值下注更敢下，少做软弱过牌，"
        "该打就打，别轻易放过英雄。"
    )


def mode_label(mode: str) -> str:
    if mode == MODE_REALISM:
        return "拟真 · 少提示、对手更猛"
    return "训练 · 教练开"

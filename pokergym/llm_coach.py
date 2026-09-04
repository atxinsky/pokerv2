"""Hero coaching via DeepSeek: pre-action hint + post-hand review.

Never auto-acts for hero — advice only.
"""

from __future__ import annotations

import json

from pokergym.archetypes import ARCHETYPE_ZH
from pokergym.cards import card_pretty
from pokergym.const import CHIP_PER_BB
from pokergym.deepseek import available, chat_json
from pokergym.ranges import hole_code
from pokergym.store import log_llm
from pokergym.types import BotView

STREET_ZH = {"pre": "牌前", "flop": "翻牌", "turn": "转牌", "river": "河牌", "over": "摊牌"}
KIND_ZH = {"fold": "弃牌", "check": "过牌", "call": "跟注", "bet": "下注", "raise": "加注"}


def coach_enabled() -> bool:
    try:
        from pokergym.store import apply_env, get_setting

        apply_env()
        return get_setting("coach_enabled", "1") != "0"
    except Exception:
        return True


def pre_hint_enabled(mode: str | None = None) -> bool:
    """Optional short pre-action hint; default off. Realism forces off."""
    try:
        from pokergym.store import apply_env, get_setting

        apply_env()
        setting_on = get_setting("coach_pre_hint", "0") == "1"
        if mode is None:
            mode = get_setting("product_mode", "train")
        from pokergym.modes import pre_hint_allowed

        return pre_hint_allowed(mode, setting_on)
    except Exception:
        return False


def comment_spot(view: BotView, local: dict) -> str | None:
    """Short pre-action hint (settings-gated by caller)."""
    if not available():
        return None
    code = hole_code(view.hole)
    payload = {
        "position": view.position,
        "street": view.street,
        "hand": code,
        "pot_bb": round(view.pot_bb, 2),
        "to_call_bb": round(view.to_call_bb, 2),
        "n_opponents": view.n_opponents,
        "equity": local.get("equity"),
        "engine_action": local.get("action_zh"),
        "engine_why": local.get("why"),
    }
    sys = (
        "你是线下现金局教练，站在玩家身后说话。"
        "只输出 JSON：{\"comment\":\"...\"}。"
        "comment 一两句中文口语，不要复述数字，不要自己计算胜率，直接用给定结论。"
        "可以同意或补充引擎建议。不要替玩家做决定口吻。"
    )
    data = chat_json(sys, "当前决策点：" + str(payload), timeout=10, max_tokens=160)
    if not data:
        log_llm("教练提示调用失败")
        return None
    text = str(data.get("comment") or "").strip()
    if not text:
        return None
    log_llm("DeepSeek 提示：" + text[:80])
    return text[:160]


def _cards_text(cards) -> str:
    if not cards:
        return "无"
    return " ".join(card_pretty(c) for c in cards)


def _log_lines(log, names: dict | None = None) -> list[str]:
    lines = []
    for a in log or []:
        if isinstance(a, dict):
            seat = a.get("seat")
            who = (names or {}).get(seat) or a.get("name") or f"#{seat}"
            street = STREET_ZH.get(a.get("street", ""), a.get("street", ""))
            kind = KIND_ZH.get(a.get("kind", ""), a.get("kind", ""))
            put = a.get("put_chips")
            to = a.get("to_chips")
            if a.get("kind") in ("bet", "raise") and to is not None:
                lines.append(f"[{street}] {who} {kind}到 {to / CHIP_PER_BB:.1f}bb")
            elif a.get("kind") == "call" and put is not None:
                lines.append(f"[{street}] {who} 跟注 {put / CHIP_PER_BB:.1f}bb")
            else:
                lines.append(f"[{street}] {who} {kind}")
            continue
        who = (names or {}).get(a.seat, f"#{a.seat}")
        street = STREET_ZH.get(a.street, a.street)
        kind = KIND_ZH.get(a.kind, a.kind)
        if a.kind in ("bet", "raise"):
            lines.append(f"[{street}] {who} {kind}到 {a.to_chips / CHIP_PER_BB:.1f}bb")
        elif a.kind == "call":
            lines.append(f"[{street}] {who} 跟注 {a.put_chips / CHIP_PER_BB:.1f}bb")
        else:
            lines.append(f"[{street}] {who} {kind}")
    return lines


def review_hand_llm(
    *,
    hole,
    board,
    position: str,
    log,
    tags: list[str],
    delta_bb: float,
    rule_review: dict | None,
    opponent_types: list[str] | None = None,
    names: dict | None = None,
    detail: bool = False,
    timeout: float = 14.0,
) -> str | None:
    """Post-hand LLM review for hero. Returns Chinese text or None."""
    if not available():
        return None
    code = hole_code(hole) if hole else "?"
    notes = (rule_review or {}).get("notes") or []
    summary = (rule_review or {}).get("summary") or ""
    sys = (
        "你是线下现金局扑克教练，只点评英雄（hero）这一手。"
        "只输出 JSON：{\"review\":\"...\"}。"
        "review 用中文口语："
        + (
            "详细讲清楚：错在哪、更好的线、为什么、以及对手类型怎么影响这手。120～220字。"
            if detail
            else "指出错在哪、更好的线、为什么。结合位置和对手类型。60～120字。"
        )
        + "不要自己编造没给出的牌或行动。不要替玩家自动打牌。"
    )
    user = {
        "hero_position": position,
        "hero_hand": code,
        "hero_cards": _cards_text(hole) if hole else "?",
        "board": _cards_text(board),
        "delta_bb": delta_bb,
        "leak_tags": tags or [],
        "rule_notes": notes,
        "rule_summary": summary,
        "opponent_types": opponent_types or [],
        "action_log": _log_lines(log, names),
    }
    data = chat_json(
        sys,
        json.dumps(user, ensure_ascii=False),
        timeout=timeout,
        temperature=0.55,
        max_tokens=420 if detail else 280,
    )
    if not data:
        log_llm("教练复盘调用失败")
        return None
    text = str(data.get("review") or "").strip()
    if not text:
        return None
    log_llm("DeepSeek 复盘：" + text[:80])
    return text[:800] if detail else text[:420]


def opponent_type_labels(bots: dict, hero_seat: int) -> list[str]:
    out = []
    for seat, bot in sorted(bots.items()):
        if seat == hero_seat:
            continue
        zh = ARCHETYPE_ZH.get(bot.archetype, bot.archetype)
        out.append(f"{bot.name.rstrip('0123456789') or bot.name}({zh})")
    return out

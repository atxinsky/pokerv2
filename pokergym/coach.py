"""数学教练层：不调 LLM，只给赔率/SPR/牌力/标签。"""

from __future__ import annotations

from pokergym.classify import board_texture, hand_class
from pokergym.postflop import rough_equity
from pokergym.types import Action, BotView


def pot_odds(view: BotView) -> float:
    if view.to_call_bb <= 0:
        return 0.0
    return view.to_call_bb / (view.pot_bb + view.to_call_bb)


def mdf(view: BotView) -> float:
    """最小防守频率：1 - bet/(pot+bet)。"""
    if view.to_call_bb <= 0:
        return 0.0
    return 1 - view.to_call_bb / (view.pot_bb + view.to_call_bb)


def snapshot(view: BotView) -> dict:
    hc = hand_class(view.hole, view.board) if view.board else "PRE"
    eq = rough_equity(hc, view.n_opponents, view.street) if view.board else None
    return {
        "position": view.position,
        "spr": round(view.spr, 2),
        "pot_bb": round(view.pot_bb, 2),
        "to_call_bb": round(view.to_call_bb, 2),
        "pot_odds": round(pot_odds(view), 3),
        "mdf": round(mdf(view), 3),
        "hand_class": hc,
        "texture": board_texture(view.board) if view.board else None,
        "equity_est": None if eq is None else round(eq, 3),
        "n_opponents": view.n_opponents,
    }


def tag_action(view: BotView, action: Action) -> list[str]:
    """给英雄动作贴泄漏标签，供 drill 统计。"""
    tags = []
    odds = pot_odds(view)
    hc = hand_class(view.hole, view.board) if view.board else "PRE"
    if view.street == "pre":
        from pokergym.preflop import classify_preflop
        from pokergym.ranges import percentile

        seq = classify_preflop(view.action_log)
        pct = percentile(view.hole)
        if seq.facing == "threebet" and action.kind == "fold" and pct <= 0.08:
            tags.append("overfold_3bet")
        if seq.facing == "limp" and action.kind == "call" and pct <= 0.12:
            tags.append("no_iso")
        if seq.facing == "unopened" and action.kind == "fold" and pct <= 0.10:
            tags.append("underopen")
    if view.street == "river" and view.to_call_bb > 0 and action.kind == "fold":
        if hc in ("STRONG", "NUTTED"):
            tags.append("overfold_river")
        if odds <= 0.25 and hc in ("MEDIUM", "WEAK_MADE"):
            tags.append("overfold_river")
    if view.to_call_bb > 0 and action.kind == "call" and hc == "AIR" and odds > 0.4:
        tags.append("calling_station")
    return tags

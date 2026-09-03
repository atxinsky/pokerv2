"""翻牌锁定意图，后续街道查表 + 跃迁。"""

from __future__ import annotations

import random

from pokergym.classify import (
    TEXTURE_BLUFF_MULT,
    board_texture,
    hand_class,
    turn_card_class,
)
from pokergym.rngutil import weighted_choice
from pokergym.types import BotView

INTENTS = (
    "PURE_VALUE",
    "THIN_VALUE",
    "SEMI_BLUFF",
    "PURE_BLUFF",
    "POT_CONTROL",
    "GIVE_UP",
    "TRAP",
)

# 转牌下注频率基线（进攻方）
TURN_BET = {
    "PURE_VALUE": {"REINFORCE": 0.90, "BLANK": 0.85, "SCARE_VILLAIN": 0.78, "HELP_VILLAIN": 0.72},
    "THIN_VALUE": {"REINFORCE": 0.62, "BLANK": 0.55, "SCARE_VILLAIN": 0.38, "HELP_VILLAIN": 0.22},
    "SEMI_BLUFF": {"REINFORCE": 0.78, "BLANK": 0.62, "SCARE_VILLAIN": 0.70, "HELP_VILLAIN": 0.28},
    "PURE_BLUFF": {"REINFORCE": 0.58, "BLANK": 0.38, "SCARE_VILLAIN": 0.72, "HELP_VILLAIN": 0.12},
    "POT_CONTROL": {"REINFORCE": 0.18, "BLANK": 0.10, "SCARE_VILLAIN": 0.12, "HELP_VILLAIN": 0.05},
    "GIVE_UP": {"REINFORCE": 0.06, "BLANK": 0.03, "SCARE_VILLAIN": 0.10, "HELP_VILLAIN": 0.02},
    "TRAP": {"REINFORCE": 0.35, "BLANK": 0.22, "SCARE_VILLAIN": 0.40, "HELP_VILLAIN": 0.15},
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _bluff_score(view: BotView) -> float:
    """阻断 + 残差胜率的廉价打分，不跑蒙特卡洛。"""
    hole_ranks = [c % 13 for c in view.hole]
    board_ranks = [c % 13 for c in view.board]
    blocker = 0.0
    if 12 in hole_ranks:
        blocker += 0.35
    if 11 in hole_ranks:
        blocker += 0.2
    # 同花阻断
    suits = [c // 13 for c in view.board]
    if suits:
        from collections import Counter

        s, n = Counter(suits).most_common(1)[0]
        if n >= 2 and any(c // 13 == s for c in view.hole):
            blocker += 0.25
    showdown = 0.7 if max(hole_ranks) >= 10 else 0.3
    if max(hole_ranks) in board_ranks:
        showdown = 0.6
    residual = 0.25
    return _clamp(0.40 * min(blocker, 1.0) + 0.30 * residual + 0.30 * (1 - showdown), 0, 1)


def assign_intent(view: BotView, params: dict, rng: random.Random) -> str:
    hc = hand_class(view.hole, view.board)
    tx = board_texture(view.board)
    deep = view.spr > 6
    ip = view.is_ip
    bm = params.get("bluff_mult", 1.0)

    if hc == "NUTTED":
        return "PURE_VALUE"
    if hc == "STRONG":
        if deep and tx in ("WET_CONNECTED", "MONOTONE"):
            return weighted_choice(rng, {"THIN_VALUE": 0.55, "POT_CONTROL": 0.45})
        return "PURE_VALUE" if not deep else "THIN_VALUE"
    if hc == "MEDIUM":
        return weighted_choice(
            rng,
            {"THIN_VALUE": 0.35 if ip else 0.15, "POT_CONTROL": 0.65 if ip else 0.85},
        )
    if hc == "WEAK_MADE":
        return weighted_choice(rng, {"POT_CONTROL": 0.75, "GIVE_UP": 0.25})
    if hc == "DRAW_STRONG":
        f = _clamp(0.70 * bm, 0.15, 0.90)
        return weighted_choice(rng, {"SEMI_BLUFF": f, "POT_CONTROL": 1 - f})
    if hc == "DRAW_WEAK":
        f = _clamp(0.35 * bm, 0.05, 0.70)
        return weighted_choice(rng, {"SEMI_BLUFF": f, "GIVE_UP": 1 - f})
    score = _bluff_score(view)
    f = _clamp(score * bm * TEXTURE_BLUFF_MULT.get(tx, 1.0), 0.0, 0.75)
    return weighted_choice(rng, {"PURE_BLUFF": f, "GIVE_UP": 1 - f})


def apply_transition(intent: str | None, view: BotView, faced_raise: bool = False) -> str:
    if not intent:
        return "POT_CONTROL"
    hc = hand_class(view.hole, view.board)
    if intent == "SEMI_BLUFF":
        if hc in ("NUTTED", "STRONG"):
            return "PURE_VALUE"
        if hc == "MEDIUM":
            return "THIN_VALUE"
        if view.street == "river" and hc in ("AIR", "WEAK_MADE", "DRAW_WEAK"):
            return "PURE_BLUFF"
    if intent == "PURE_BLUFF":
        tclass = "BLANK"
        if len(view.board) >= 4:
            tclass = turn_card_class(view.hole, view.board[:-1], view.board[-1], intent)
        if tclass == "HELP_VILLAIN" or faced_raise:
            return "GIVE_UP"
    if intent == "THIN_VALUE" and faced_raise:
        return "POT_CONTROL"
    if intent == "PURE_VALUE" and faced_raise:
        return "PURE_VALUE"
    if intent == "PURE_VALUE" and view.street != "flop":
        # 翻牌过牌后的诱捕在 bot 里单独标 TRAP
        pass
    return intent


def bet_freq_for(intent: str, tclass: str, params: dict, multiway: bool) -> float:
    base = TURN_BET.get(intent, TURN_BET["POT_CONTROL"]).get(tclass, 0.1)
    if intent in ("PURE_VALUE", "THIN_VALUE", "TRAP"):
        base *= params.get("value_mult", 1.0)
    if intent in ("PURE_BLUFF", "SEMI_BLUFF"):
        base *= params.get("bluff_mult", 1.0)
    if multiway:
        if intent in ("PURE_BLUFF", "SEMI_BLUFF"):
            base *= 0.4
        else:
            base *= 0.75
    return _clamp(base, 0.0, 0.95)

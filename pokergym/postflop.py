"""翻后进攻 / 面对下注。多人池降诈唬。"""

from __future__ import annotations

from pokergym.classify import board_texture, hand_class, turn_card_class
from pokergym.const import CHIP_PER_BB
from pokergym.intent import bet_freq_for
from pokergym.types import Action, BotView

ROUGH_EQ = {
    ("NUTTED", "flop"): 0.88,
    ("NUTTED", "turn"): 0.90,
    ("NUTTED", "river"): 0.93,
    ("STRONG", "flop"): 0.72,
    ("STRONG", "turn"): 0.74,
    ("STRONG", "river"): 0.78,
    ("MEDIUM", "flop"): 0.55,
    ("MEDIUM", "turn"): 0.52,
    ("MEDIUM", "river"): 0.50,
    ("WEAK_MADE", "flop"): 0.38,
    ("WEAK_MADE", "turn"): 0.34,
    ("WEAK_MADE", "river"): 0.32,
    ("DRAW_STRONG", "flop"): 0.46,
    ("DRAW_STRONG", "turn"): 0.36,
    ("DRAW_STRONG", "river"): 0.18,
    ("DRAW_WEAK", "flop"): 0.28,
    ("DRAW_WEAK", "turn"): 0.18,
    ("DRAW_WEAK", "river"): 0.10,
    ("AIR", "flop"): 0.14,
    ("AIR", "turn"): 0.10,
    ("AIR", "river"): 0.07,
}


def rough_equity(hc: str, n_opp: int, street: str) -> float:
    e = ROUGH_EQ.get((hc, street), 0.3)
    if n_opp >= 2:
        e *= 0.88 ** (n_opp - 1)
    return max(0.04, min(0.95, e))


def _tclass(view: BotView, intent: str) -> str:
    if view.street == "flop" or len(view.board) < 4:
        tx = board_texture(view.board)
        if tx in ("DRY_RAINBOW", "HIGH_CARD"):
            return "BLANK"
        if tx in ("WET_CONNECTED", "MONOTONE"):
            return "SCARE_VILLAIN"
        return "BLANK"
    return turn_card_class(view.hole, view.board[:-1], view.board[-1], intent)


def aggressor_freqs(view: BotView, intent: str, params: dict) -> dict[str, float]:
    """无人下注时：过牌或下注。"""
    multi = view.n_opponents >= 2
    tclass = _tclass(view, intent)
    is_pfr = view.pfr_seat == view.seat
    bet_f = bet_freq_for(intent, tclass, params, multi)
    # 翻牌 PFR 用 cbet_freq 当主开关，意图只做微调
    if view.street == "flop" and is_pfr:
        bet_f = params.get("cbet_freq", 0.6)
        if intent == "GIVE_UP":
            bet_f *= 0.30
        elif intent == "POT_CONTROL":
            bet_f *= 0.55
        elif intent == "TRAP":
            bet_f *= 0.22
        if multi:
            bet_f *= 0.72
    elif view.street == "flop" and not is_pfr and not view.is_ip:
        donk = params.get("donk_freq", 0.05) * (1.2 if intent in ("PURE_VALUE", "SEMI_BLUFF") else 0.6)
        if multi:
            donk *= 0.5
        bet_f = min(0.5, donk if intent not in ("PURE_VALUE", "TRAP") else max(bet_f * 0.5, donk))
    if intent == "TRAP" and view.street != "flop":
        bet_f = max(bet_f, 0.35)
    if view.street == "river":
        if intent in ("PURE_BLUFF", "SEMI_BLUFF"):
            bet_f = min(0.95, bet_f * (0.8 + params.get("river_bluff_freq", 0.1)))
    bet_f = max(0.0, min(0.95, bet_f))
    check_f = 1 - bet_f
    # 尺度：干面小、湿面中
    tx = board_texture(view.board)
    if tx in ("DRY_RAINBOW", "HIGH_CARD"):
        small, mid, big = 0.55, 0.35, 0.10
    elif tx == "MONOTONE":
        small, mid, big = 0.20, 0.40, 0.40
    else:
        small, mid, big = 0.25, 0.50, 0.25
    if params.get("sizing_bias", 1.0) > 1.15:
        small, mid, big = 0.15, 0.40, 0.45
    return {
        "check": check_f,
        "bet_small": bet_f * small,
        "bet_mid": bet_f * mid,
        "bet_big": bet_f * big,
    }


def defender_freqs(view: BotView, intent: str, params: dict) -> dict[str, float]:
    hc = hand_class(view.hole, view.board)
    req = view.to_call_bb / max(view.pot_bb + view.to_call_bb, 0.01)
    eq = rough_equity(hc, view.n_opponents, view.street)
    sizing = view.to_call_bb / max(view.pot_bb, 0.01)
    polar = 0.05 if sizing >= 0.75 else 0.0
    bias = params.get("fold_bias", 0.0) - 0.16 * params.get("call_station_idx", 0.3)
    need = req + bias + polar
    station = params.get("call_station_idx", 0.3)

    fold_cbet = params.get("fold_to_cbet", 0.45)
    raise_f, call_f, fold_f = 0.0, 0.0, 0.0
    if hc == "NUTTED":
        raise_f = 0.50 * params.get("value_mult", 1.0)
        call_f = 1 - raise_f
    elif hc == "STRONG":
        raise_f = 0.22 * params.get("value_mult", 1.0)
        if eq + 0.08 < need and station < 0.5:
            fold_f = 0.15
            call_f = 1 - raise_f - fold_f
        else:
            call_f = 1 - raise_f
    elif hc == "MEDIUM":
        raise_f = 0.08 if view.is_ip else 0.04
        fold_f = fold_cbet * 0.45
        if eq < need and station < 0.65:
            fold_f = max(fold_f, 0.35 + max(0, need - eq))
        call_f = max(0.08, 1 - raise_f - fold_f)
    elif hc == "DRAW_STRONG":
        raise_f = 0.35 * params.get("bluff_mult", 1.0)
        call_f = 0.55
        fold_f = max(0.0, 1 - raise_f - call_f)
    elif hc == "DRAW_WEAK":
        if eq >= need * 0.9 or station > 0.7:
            call_f = 0.70
            fold_f = 0.25
            raise_f = 0.05
        else:
            fold_f = 0.70
            call_f = 0.25
            raise_f = 0.05
    elif hc == "WEAK_MADE":
        fold_f = 0.35 + fold_cbet * 0.5
        if station > 0.7 or eq >= need:
            fold_f *= 0.45
        call_f = max(0.1, 0.95 - fold_f)
        raise_f = max(0.0, 1 - fold_f - call_f)
    else:  # AIR
        bluff_r = 0.08 * params.get("bluff_mult", 1.0)
        if view.n_opponents >= 2:
            bluff_r *= 0.3
        raise_f = bluff_r
        fold_f = min(0.95, fold_cbet + 0.15)
        if station > 0.8:
            fold_f *= 0.5
        call_f = max(0.0, 1 - raise_f - fold_f)
    if not view.can_raise:
        call_f += raise_f
        raise_f = 0.0
    s = raise_f + call_f + fold_f
    if s <= 0:
        return {"fold": 1.0}
    return {"fold": fold_f / s, "call": call_f / s, "raise_min": raise_f / s}


def materialize_postflop(key: str, view: BotView) -> Action:
    pot = int(round(view.pot_bb * CHIP_PER_BB))
    max_to = int(round((view.my_stack_bb + view.bet_street_bb) * CHIP_PER_BB))
    min_bet = int(round(view.bet_street_bb * CHIP_PER_BB)) + int(CHIP_PER_BB)
    if key == "fold":
        return Action("fold")
    if key == "check":
        return Action("check")
    if key == "call":
        to = int(round((view.bet_street_bb + view.to_call_bb) * CHIP_PER_BB))
        return Action("call", min(to, max_to))
    frac = {"bet_small": 0.33, "bet_mid": 0.66, "bet_big": 1.0}.get(key)
    if frac is not None:
        to = min(max_to, max(min_bet, int(pot * frac) + int(view.bet_street_bb * CHIP_PER_BB)))
        kind = "bet" if view.to_call_bb <= 0 else "raise"
        return Action(kind, to)
    if key in ("raise_min", "raise_mid"):
        min_to = int(round(view.min_raise_to_bb * CHIP_PER_BB))
        to = min_to if key == "raise_min" else max(min_to, int(view.current_bet_bb * CHIP_PER_BB * 3))
        return Action("raise", min(to, max_to))
    if key == "allin":
        return Action("raise" if view.to_call_bb > 0 else "bet", max_to)
    return Action("check" if view.to_call_bb <= 0 else "fold")

"""实时建议：翻前对照 GTO 表，翻后对照胜率 vs 底池赔率。"""

from __future__ import annotations

from pokergym.classify import board_texture, hand_class
from pokergym.equity import equity_vs_codes
from pokergym.gto import (
    CALL,
    OPEN,
    THREEBET,
    grid,
    in_3bet,
    in_call,
    in_iso,
    in_open,
    preflop_line,
    spot_label,
)
from pokergym.preflop import classify_preflop
from pokergym.ranges import hole_code
from pokergym.types import Action, BotView

LINE_ZH = {
    "fold": "弃牌",
    "check": "过牌",
    "open": "加注开池",
    "bet": "下注",
    "iso": "加注隔离",
    "call": "跟注",
    "threebet": "3bet",
    "fourbet": "4bet",
}

CLASS_ZH = {
    "NUTTED": "坚果",
    "STRONG": "强牌",
    "MEDIUM": "中等成牌",
    "WEAK_MADE": "弱成牌",
    "DRAW_STRONG": "强听牌",
    "DRAW_WEAK": "弱听牌",
    "AIR": "空气",
    "PRE": "翻前",
}


def _odds(view: BotView) -> float:
    if view.to_call_bb <= 0:
        return 0.0
    return view.to_call_bb / (view.pot_bb + view.to_call_bb)


def _villain_codes(facing: str, pos: str) -> set[str]:
    if facing in ("open", "open_calls"):
        return OPEN.get("CO", set()) | OPEN.get("BTN", set())
    if facing == "threebet":
        return THREEBET.get("BTN", set()) | THREEBET.get("CO", set())
    if facing == "limp":
        return CALL.get("BB", set())
    return OPEN.get(pos, set()) or OPEN["MP"]


def advise(view: BotView) -> dict:
    code = hole_code(view.hole)
    seq = classify_preflop(view.action_log)
    facing = seq.facing
    pos = view.position
    spot, title = spot_label(facing, pos)
    g = grid(spot if spot != "defend" else "defend", pos if spot != "defend" else "BB", code)

    if view.street == "pre":
        line = preflop_line(pos, facing, code)
        eq = None
        try:
            eq = round(equity_vs_codes(view.hole, (), _villain_codes(facing, pos), iters=120), 3)
        except Exception:
            eq = None
        why = _pre_why(pos, facing, code, line)
        size = None
        if line == "open":
            size = "开到 2.5–3.5bb"
        elif line == "iso":
            size = "隔离到 4bb + 每个 limp 再 +1bb"
        elif line == "threebet":
            size = "IP 约 3x，OOP 约 3.5–4x"
        return {
            "code": code,
            "action": line,
            "action_zh": LINE_ZH.get(line, line),
            "why": why,
            "equity": eq,
            "pot_odds": round(_odds(view), 3),
            "spot": spot,
            "chart_title": title,
            "grid": g,
            "in_open": in_open(pos, code),
            "in_3bet": in_3bet(pos, code),
            "in_call": in_call(pos, code),
            "size_hint": size,
            "hand_class": "PRE",
            "hand_class_zh": "翻前",
        }

    hc = hand_class(view.hole, view.board)
    odds = _odds(view)
    codes = _villain_codes(facing if facing != "unopened" else "open", pos)
    eq = round(equity_vs_codes(view.hole, view.board, codes, iters=140), 3)
    if view.to_call_bb > 0:
        if eq + 0.04 < odds and hc not in ("NUTTED", "STRONG", "DRAW_STRONG"):
            line, why = "fold", f"胜率 {eq:.0%} 低于跟注所需 {odds:.0%}，这口汤不该喝。"
        elif hc in ("NUTTED", "STRONG") or eq > 0.62:
            line, why = "threebet" if view.can_raise else "call", f"成牌/胜率 {eq:.0%}，该加注要价值。"
            if not view.can_raise:
                line = "call"
                why = f"胜率 {eq:.0%}，至少跟注。"
        else:
            line, why = "call", f"胜率 {eq:.0%} 盖过赔率 {odds:.0%}，可以跟。"
    else:
        if hc in ("NUTTED", "STRONG") or (hc == "DRAW_STRONG" and view.n_opponents <= 2):
            line, why = "open", f"{CLASS_ZH.get(hc)}，应该下注占主动。"
        elif hc in ("AIR", "WEAK_MADE") and view.n_opponents >= 2:
            line, why = "check", "多人池空气/弱牌，过牌控池。"
        else:
            line, why = "check", f"{CLASS_ZH.get(hc)}，优先过牌，除非对手很弱。"
    return {
        "code": code,
        "action": line,
        "action_zh": LINE_ZH.get(line, line),
        "why": why,
        "equity": eq,
        "pot_odds": round(odds, 3),
        "spot": spot,
        "chart_title": title,
        "grid": g,
        "in_open": in_open(pos, code),
        "in_3bet": in_3bet(pos, code),
        "in_call": in_call(pos, code),
        "size_hint": "干面 1/3 底池，湿面 2/3 底池" if line == "open" else None,
        "hand_class": hc,
        "hand_class_zh": CLASS_ZH.get(hc, hc),
        "texture": board_texture(view.board),
    }


def _pre_why(pos, facing, code, line) -> str:
    if facing == "unopened":
        if line == "open":
            return f"{pos} 拿 {code} 在开池范围内，标准加注。"
        if pos == "BB":
            return "大盲无人加注，过牌看翻牌。"
        return f"{pos} 拿 {code} 不在开池范围，弃牌。不要用垃圾边路位置强开。"
    if facing == "limp":
        if line == "iso":
            return f"面对 limp，{code} 足够隔离。目标是打到单挑。"
        if line == "call":
            return "这手可以跟 limp 进池，但不值得加注。"
        return "面对 limp 也不该进。让他们去玩。"
    if facing in ("open", "open_calls"):
        if line == "threebet":
            return f"{code} 是这个位置的 3bet 组合（价值或阻挡诈唬）。"
        if line == "call":
            return f"{code} 可跟注，但不要 3bet。注意位置和 SPR。"
        return f"面对加注，{code} 不在继续范围内。漂亮的弃牌比勉强跟注更赚钱。"
    if facing == "threebet":
        if line in ("call", "fourbet"):
            return f"面对 3bet，{code} 可以继续。弱于 QQ 的对子多数该弃。"
        return "面对 3bet 这手太边。弃牌。"
    return f"建议 {LINE_ZH.get(line, line)}。"


def review_hand(hole, position: str, log, tags: list[str], delta_bb: float) -> dict:
    """一手结束后的复盘。"""
    pre = tuple(a for a in log if getattr(a, "street", "") == "pre")
    facing = classify_preflop(pre).facing
    code = hole_code(hole) if hole else "?"
    ideal = preflop_line(position, facing, code) if hole else "fold"
    hero_acts = [a.kind for a in pre if True]
    # 英雄第一动作：由调用方传入很难，用 tags + 理想线
    notes = []
    if "underopen" in tags:
        notes.append(f"{position} 拿 {code} 该开却弃，漏了范围里的牌。")
    if "no_iso" in tags:
        notes.append("面对 limp 该加注隔离，平跟会把多人池玩砸。")
    if "overfold_3bet" in tags:
        notes.append("面对 3bet 弃掉了该继续的强牌。")
    if "overfold_river" in tags:
        notes.append("河牌面对下注弃了还有摊牌价值的牌。")
    if "calling_station" in tags:
        notes.append("空气牌付了不该付的河牌。")
    if not notes:
        if ideal == "fold":
            notes.append(f"翻前理想是弃牌（{position} {code} / {facing}）。")
        else:
            notes.append(f"翻前理想：{LINE_ZH.get(ideal, ideal)}（{position} {code}）。")
    if delta_bb > 0:
        result = f"这手 +{delta_bb}bb。"
    elif delta_bb < 0:
        result = f"这手 {delta_bb}bb。"
    else:
        result = "这手打平。"
    return {
        "ideal": ideal,
        "ideal_zh": LINE_ZH.get(ideal, ideal),
        "code": code,
        "facing": facing,
        "notes": notes[:3],
        "summary": result + " " + notes[0],
        "tags": tags,
    }

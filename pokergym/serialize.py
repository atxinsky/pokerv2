"""把 LiveSession 打成前端 JSON。他人未摊牌底牌不会出现。"""

from __future__ import annotations

from pokergym.archetypes import ARCHETYPE_ZH
from pokergym.cards import RANKS, SUITS, card_pretty, card_rank, card_suit
from pokergym.const import CHIP_PER_BB
from pokergym.legal import legal_actions
from pokergym.live import LiveSession
from pokergym.stats import collect
from pokergym.step import is_hand_over

KIND_ZH = {
    "fold": "弃牌",
    "check": "过牌",
    "call": "跟注",
    "bet": "下注",
    "raise": "加注",
}
STREET_ZH = {"pre": "翻前", "flop": "翻牌", "turn": "转牌", "river": "河牌", "over": "摊牌"}
CLASS_ZH = {
    "NUTTED": "坚果",
    "STRONG": "强牌",
    "MEDIUM": "中等",
    "WEAK_MADE": "弱成牌",
    "DRAW_STRONG": "强听",
    "DRAW_WEAK": "弱听",
    "AIR": "空气",
    "PRE": "翻前",
}
TEXTURE_ZH = {
    "DRY_RAINBOW": "干燥彩虹",
    "HIGH_CARD": "高张干燥",
    "PAIRED": "对子面",
    "WET_CONNECTED": "湿润连张",
    "MONOTONE": "三同花",
}
TAG_ZH = {
    "overfold_3bet": "3bet 过折",
    "no_iso": "该 iso 却平跟",
    "underopen": "该开却弃",
    "overfold_river": "河牌过折",
    "calling_station": "跟注站",
}
SESSION_ZH = {
    "normal": "状态平常",
    "tilted": "今晚上头",
    "conservative": "今晚保守",
    "fatigued": "今晚疲惫",
}


def card_dto(c: int) -> dict:
    s = card_suit(c)
    return {
        "id": c,
        "rank": RANKS[card_rank(c)],
        "suit": SUITS[s],
        "pretty": card_pretty(c),
        "red": s in (1, 2),
    }


def _bb(chips: int) -> float:
    return round(chips / CHIP_PER_BB, 2)


def _bet_ui(sess: LiveSession) -> dict | None:
    """下注/加注用「加到 to_bb」（本街累计），并给出投入 add_bb。"""
    if sess.waiting() != "hero":
        return None
    st = sess.st
    p = st.players[sess.hero_seat]
    kinds = {a.kind for a in legal_actions(st, sess.hero_seat)}
    if "bet" not in kinds and "raise" not in kinds:
        return None
    pot = st.pot_chips
    already = p.bet_street
    max_to = already + p.stack
    tc = st.current_bet - already
    if tc > 0:
        kind = "raise"
        min_to = min(max_to, st.current_bet + st.min_raise_by)
        raw = [
            ("最小", min_to),
            ("2.5x", int(st.current_bet * 2.5)),
            ("3x", int(st.current_bet * 3)),
            ("底池", st.current_bet + pot),
            ("全下", max_to),
        ]
    else:
        kind = "bet"
        min_to = min(max_to, already + st.bb_chips)
        raw = [
            ("1/3", already + max(st.bb_chips, int(pot * 0.33))),
            ("1/2", already + max(st.bb_chips, int(pot * 0.50))),
            ("2/3", already + max(st.bb_chips, int(pot * 0.66))),
            ("底池", already + max(st.bb_chips, pot)),
            ("1.5x", already + max(st.bb_chips, int(pot * 1.5))),
            ("全下", max_to),
        ]
    presets = []
    seen: set[float] = set()
    for label, to in raw:
        to = max(min_to, min(to, max_to))
        if to <= already:
            continue
        if tc > 0 and to < min_to and to < max_to:
            continue
        key = round(to / CHIP_PER_BB, 2)
        if key in seen:
            continue
        seen.add(key)
        add = to - already
        presets.append(
            {
                "label": label,
                "to_bb": _bb(to),
                "add_bb": _bb(add),
                "hint": f"投入 {_bb(add)}bb",
            }
        )
    half = already + max(st.bb_chips, int(pot * 0.5))
    default = min(max_to, max(min_to, half if kind == "bet" else min_to))
    return {
        "kind": kind,
        "min_to_bb": _bb(min_to),
        "max_to_bb": _bb(max_to),
        "default_to_bb": _bb(default),
        "already_bb": _bb(already),
        "to_call_bb": _bb(max(0, tc)),
        "pot_bb": _bb(pot),
        "step_bb": 0.5,
        "presets": presets,
    }


def _as_cards(xs) -> list[dict]:
    if not xs:
        return []
    if isinstance(xs[0], dict):
        return list(xs)
    return [card_dto(int(c)) for c in xs]


def _history(sess: LiveSession) -> list[dict]:
    stored = []
    try:
        from pokergym.store import list_hands

        stored = list_hands(40)
    except Exception:
        stored = []
    src = stored if stored else None
    if src is not None:
        out = []
        for rec in src:
            log = []
            for a in rec.get("log") or []:
                if isinstance(a, dict):
                    log.append(
                        {
                            "name": a.get("name") or f"#{a.get('seat')}",
                            "street_zh": STREET_ZH.get(a.get("street", ""), a.get("street", "")),
                            "kind_zh": KIND_ZH.get(a.get("kind", ""), a.get("kind", "")),
                            "put_bb": _bb(int(a.get("put_chips") or 0)),
                            "to_bb": _bb(int(a.get("to_chips") or 0)),
                            "kind": a.get("kind"),
                        }
                    )
            out.append(
                {
                    "hand_idx": rec.get("hand_idx"),
                    "delta_bb": rec.get("delta_bb"),
                    "folded": rec.get("folded"),
                    "vpip": rec.get("vpip"),
                    "pfr": rec.get("pfr"),
                    "tags": [TAG_ZH.get(t, t) for t in rec.get("tags") or []],
                    "hole": _as_cards(rec.get("hole") or []),
                    "board": _as_cards(rec.get("board") or []),
                    "log": log,
                    "review": rec.get("review") or {},
                }
            )
        return out
    out = []
    for rec in sess.archive[-40:]:
        hole = rec.get("hole") or ()
        board = rec.get("board") or ()
        log = []
        for a in rec.get("log") or []:
            log.append(
                {
                    "name": sess._name(a.seat),
                    "street_zh": STREET_ZH.get(a.street, a.street),
                    "kind_zh": KIND_ZH.get(a.kind, a.kind),
                    "put_bb": _bb(a.put_chips),
                    "to_bb": _bb(a.to_chips),
                    "kind": a.kind,
                }
            )
        out.append(
            {
                "hand_idx": rec["hand_idx"],
                "delta_bb": rec["delta_bb"],
                "folded": rec["folded"],
                "vpip": rec["vpip"],
                "pfr": rec["pfr"],
                "tags": [TAG_ZH.get(t, t) for t in rec.get("tags") or []],
                "hole": [card_dto(c) for c in hole],
                "board": [card_dto(c) for c in board],
                "log": log,
                "review": rec.get("review") or {},
            }
        )
    return out


def _hero_stats(sess: LiveSession) -> dict:
    rows = sess.archive
    n = len(rows)
    bb = sum(r["delta_bb"] for r in rows)
    vpip = sum(1 for r in rows if r["vpip"])
    pfr = sum(1 for r in rows if r["pfr"])
    wins = sum(1 for r in rows if r["delta_bb"] > 0)
    stats = collect(sess.hist, sess.n) if sess.hist else None
    hs = stats.get(sess.hero_seat) if stats else None
    three = 0.0
    if hs and hs.vs_open:
        three = hs.threebet / hs.vs_open
    return {
        "hands": n,
        "bb": round(bb, 1),
        "bb100": round(bb / n * 100, 1) if n else 0.0,
        "vpip": round(100 * vpip / n) if n else 0,
        "pfr": round(100 * pfr / n) if n else 0,
        "wins": wins,
        "wtsd": round(100 * hs.wtsd) if hs else 0,
        "threebet": round(100 * three),
    }


def _legal_dto(sess: LiveSession) -> list[dict]:
    if sess.waiting() != "hero":
        return []
    acts = legal_actions(sess.st, sess.hero_seat)
    out = []
    for a in acts:
        to_bb = None if a.to_chips is None else _bb(a.to_chips)
        label = KIND_ZH.get(a.kind, a.kind)
        if a.kind == "call" and to_bb is not None:
            need = sess.hero_to_call_bb()
            label = f"跟注 {need:.1f}bb".replace(".0bb", "bb")
        out.append({"kind": a.kind, "to_bb": to_bb, "label": label})
    # 每种 kind 只留一个代表（尺度走 slider）
    by = {}
    for item in out:
        k = item["kind"]
        if k not in by:
            by[k] = item
        elif k in ("bet", "raise") and item["to_bb"] and (
            by[k]["to_bb"] is None or item["to_bb"] < by[k]["to_bb"]
        ):
            by[k] = item  # 最小合法尺度
    order = ["fold", "check", "call", "bet", "raise"]
    return [by[k] for k in order if k in by]


def dump_state(sess: LiveSession) -> dict:
    st = sess.st
    waiting = sess.waiting()
    stats = collect(sess.hist, sess.n) if sess.hist else None
    revealed = set(st.revealed)
    seats = []
    sb = (st.button + 1) % st.n
    bb = (st.button + 2) % st.n
    for p in st.players:
        bot = sess.bots.get(p.seat)
        is_hero = p.seat == sess.hero_seat
        show_hole = False
        hole = None
        if p.seat in st.holes:
            if is_hero or p.seat in revealed:
                hole = [card_dto(c) for c in st.holes[p.seat]]
                show_hole = True
        hud = None
        if stats and stats[p.seat].hands >= 1:
            hs = stats[p.seat]
            hud = {
                "hands": hs.hands,
                "vpip": round(hs.vpip_pct * 100),
                "pfr": round(hs.pfr_pct * 100),
            }
        seats.append(
            {
                "seat": p.seat,
                "name": "你" if is_hero else (bot.name if bot else f"#{p.seat}"),
                "archetype": None if is_hero else (bot.archetype if bot else None),
                "archetype_zh": None if is_hero else (ARCHETYPE_ZH.get(bot.archetype) if bot else None),
                "session_zh": None if is_hero else (SESSION_ZH.get(bot.session.kind, "") if bot else None),
                "notes": None if is_hero else (list(bot.hero_notes) if bot else []),
                "position": st.pos_name(p.seat),
                "stack_bb": _bb(p.stack),
                "bet_bb": _bb(p.bet_street),
                "folded": p.folded,
                "allin": p.allin,
                "acting": waiting != "over" and waiting != "idle" and st.to_act == p.seat,
                "is_hero": is_hero,
                "is_button": p.seat == st.button,
                "is_sb": p.seat == sb,
                "is_bb": p.seat == bb,
                "hole": hole,
                "hole_hidden": (not is_hero) and (p.seat not in revealed) and (not p.folded) and sess.hand_open,
                "hud": hud,
            }
        )
    coach = None
    if sess.hand_open and sess.hero_seat in st.holes:
        try:
            raw = sess.coach()
            if raw:
                coach = {
                    **raw,
                    "hand_class_zh": CLASS_ZH.get(raw["hand_class"], raw["hand_class"]),
                    "texture_zh": TEXTURE_ZH.get(raw["texture"], raw["texture"]) if raw.get("texture") else None,
                }
        except Exception:
            coach = None
    log = []
    for a in st.action_log[-40:]:
        log.append(
            {
                "seat": a.seat,
                "name": sess._name(a.seat),
                "street": a.street,
                "street_zh": STREET_ZH.get(a.street, a.street),
                "kind": a.kind,
                "kind_zh": KIND_ZH.get(a.kind, a.kind),
                "to_bb": _bb(a.to_chips),
                "put_bb": _bb(a.put_chips),
            }
        )
    winners = []
    if is_hand_over(st):
        merged = {}
        for seat, chips in st.winners:
            merged[seat] = merged.get(seat, 0) + chips
        for seat, chips in merged.items():
            winners.append(
                {
                    "seat": seat,
                    "name": "你" if seat == sess.hero_seat else (
                        sess.bots[seat].name.rstrip("0123456789") if seat in sess.bots else f"#{seat}"
                    ),
                    "bb": _bb(chips),
                    "hole": [card_dto(c) for c in st.revealed[seat]] if seat in st.revealed else None,
                }
            )
    return {
        "waiting": waiting,
        "seed": sess.seed,
        "mode": sess.mode,
        "hand_idx": st.hand_idx,
        "hands_played": len(sess.hist),
        "street": st.street,
        "street_zh": STREET_ZH.get(st.street, st.street),
        "pot_bb": _bb(st.pot_chips),
        "to_act": st.to_act,
        "button": st.button,
        "hero_seat": sess.hero_seat,
        "board": [card_dto(c) for c in st.board],
        "seats": seats,
        "legal": _legal_dto(sess),
        "bet": _bet_ui(sess),
        "to_call_bb": sess.hero_to_call_bb() if waiting == "hero" else 0,
        "stack_bb": _bb(st.players[sess.hero_seat].stack),
        "coach": coach,
        "log": log,
        "history": _history(sess),
        "hero_stats": _hero_stats(sess),
        "last_event": sess.last_event,
        "tags": [TAG_ZH.get(t, t) for t in sess.last_tags],
        "winners": winners,
        "llm": _llm_dto(sess),
    }


def _llm_dto(sess: LiveSession) -> dict:
    from pokergym.deepseek import status

    info = status()
    try:
        from pokergym.store import llm_logs

        info["log"] = llm_logs(8)
    except Exception:
        info["log"] = []
    return info

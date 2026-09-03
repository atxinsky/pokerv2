"""翻前：open / limp / iso / 3bet / squeeze / 4bet。"""

from __future__ import annotations

from dataclasses import dataclass

from pokergym.archetypes import LIMP_PCT, OPEN_PCT
from pokergym.const import BB_CHIPS, CHIP_PER_BB
from pokergym.ranges import percentile
from pokergym.types import Action, BotView, PublicAction


@dataclass
class PreSeq:
    n_limps: int = 0
    n_callers: int = 0
    has_open: bool = False
    open_to: int = BB_CHIPS
    opener_seat: int | None = None
    n_raises: int = 0
    last_raise_to: int = BB_CHIPS
    facing: str = "unopened"  # unopened/limp/open/open_calls/threebet/fourbet


def classify_preflop(log: tuple[PublicAction, ...]) -> PreSeq:
    seq = PreSeq()
    for a in log:
        if a.street != "pre":
            continue
        if a.kind == "raise":
            seq.n_raises += 1
            seq.last_raise_to = a.to_chips
            if not seq.has_open:
                seq.has_open = True
                seq.open_to = a.to_chips
                seq.opener_seat = a.seat
            if seq.n_raises == 1 and seq.n_limps > 0:
                pass  # iso
            if seq.n_raises >= 2:
                seq.n_callers = 0
        elif a.kind == "call":
            if not seq.has_open:
                seq.n_limps += 1
            else:
                seq.n_callers += 1
        elif a.kind == "bet":
            seq.n_raises += 1
            seq.has_open = True
            seq.open_to = a.to_chips
            seq.opener_seat = a.seat
            seq.last_raise_to = a.to_chips
    if seq.n_raises >= 3:
        seq.facing = "fourbet"
    elif seq.n_raises == 2:
        seq.facing = "threebet"
    elif seq.has_open and seq.n_callers >= 1:
        seq.facing = "open_calls"
    elif seq.has_open:
        seq.facing = "open"
    elif seq.n_limps >= 1:
        seq.facing = "limp"
    else:
        seq.facing = "unopened"
    return seq


def _open_to(view: BotView, params: dict) -> int:
    bb = int(round(view.pot_bb * CHIP_PER_BB / max(view.n_active, 1)))  # 不可靠
    bb = BB_CHIPS
    size = int(3.5 * bb * params.get("sizing_bias", 1.0))
    return max(2 * bb, min(size, int(view.my_stack_bb * CHIP_PER_BB) + int(view.bet_street_bb * CHIP_PER_BB)))


def _raise_to(view: BotView, mult: float) -> int:
    cur = int(round(view.current_bet_bb * CHIP_PER_BB))
    max_to = int(round((view.my_stack_bb + view.bet_street_bb) * CHIP_PER_BB))
    min_to = int(round(view.min_raise_to_bb * CHIP_PER_BB))
    to = int(cur * mult)
    return max(min_to, min(to, max_to))


def preflop_action(view: BotView, params: dict, archetype: str) -> dict[str, float]:
    """返回抽象频率，随后 clip 到合法动作。"""
    seq = classify_preflop(view.action_log)
    pct = percentile(view.hole)
    pos = view.position
    from pokergym.archetypes import ARCHETYPE_BASE

    base_pfr = ARCHETYPE_BASE[archetype]["pfr"]
    open_w = OPEN_PCT[archetype].get(pos, 0.12) * (params["pfr"] / base_pfr)
    limp_w = LIMP_PCT[archetype].get(pos, 0.0) * (params["limp_rate"] / max(0.01, ARCHETYPE_BASE[archetype]["limp_rate"]))
    limp_w = min(0.85, limp_w)

    def mix(fold, **kwargs):
        d = {"fold": fold, **kwargs}
        return d

    if seq.facing == "unopened":
        if pct <= open_w:
            return mix(0.02, open=0.98)
        if pct <= limp_w:
            return mix(0.05, limp=0.95)
        return mix(1.0)

    if seq.facing == "limp":
        iso_w = open_w * 0.9 + params["iso_freq"] * 0.15
        if pct <= iso_w:
            return mix(0.05, iso=0.95)
        over = limp_w
        if pct <= over:
            return mix(0.10, limp=0.90)
        return mix(1.0)

    if seq.facing == "open":
        t3 = params["threebet_freq"]
        if pos == "BB":
            defend = min(0.92, params["vpip"] * 1.20)
        elif pos in ("SB", "BTN"):
            defend = min(0.85, params["vpip"] * 1.05)
        else:
            defend = min(0.70, params["vpip"] * 0.85)
        if pct <= max(0.02, t3 * 2.5):
            return mix(0.06, threebet=0.94)
        if pct <= defend:
            return mix(0.12, call=0.88)
        return mix(0.88, call=0.12)

    if seq.facing == "open_calls":
        sq = params["squeeze_freq"] * (0.85 ** max(0, seq.n_callers - 1))
        defend = min(0.80, params["vpip"] * 0.90)
        if pct <= max(0.02, sq * 2.5):
            return mix(0.10, squeeze=0.90)
        if pct <= defend:
            return mix(0.18, call=0.82)
        return mix(1.0)

    if seq.facing == "threebet":
        f4 = params["fourbet_freq"]
        if pct <= f4 * 2.0:
            return mix(0.05, fourbet=0.95)
        call_w = (1 - params["fold_to_3bet"]) * 0.5
        if pct <= max(0.04, call_w):
            return mix(params["fold_to_3bet"] * 0.4, call=1 - params["fold_to_3bet"] * 0.4)
        return mix(params["fold_to_3bet"] + 0.15, call=max(0.02, 0.85 - params["fold_to_3bet"]))

    if seq.facing == "fourbet":
        if pct <= 0.03:
            return mix(0.1, fourbet=0.4, call=0.5)
        return mix(0.85, call=0.15)

    return mix(1.0)


def materialize_preflop(key: str, view: BotView, params: dict) -> Action:
    seq = classify_preflop(view.action_log)
    max_to = int(round((view.my_stack_bb + view.bet_street_bb) * CHIP_PER_BB))
    if key == "fold":
        return Action("fold")
    if key == "limp":
        return Action("call", int(round(view.bet_street_bb * CHIP_PER_BB + view.to_call_bb * CHIP_PER_BB)))
    if key == "call":
        to = int(round((view.bet_street_bb + view.to_call_bb) * CHIP_PER_BB))
        return Action("call", min(to, max_to))
    if key == "open":
        return Action("raise", min(_open_to(view, params), max_to))
    if key == "iso":
        extra = seq.n_limps * BB_CHIPS
        return Action("raise", min(_open_to(view, params) + extra, max_to))
    if key == "threebet":
        mult = 3.0 if view.is_ip else 3.5
        return Action("raise", _raise_to(view, mult))
    if key == "squeeze":
        to = int(4 * seq.open_to + seq.n_callers * BB_CHIPS)
        if not view.is_ip:
            to += BB_CHIPS
        return Action("raise", min(max(to, int(view.min_raise_to_bb * CHIP_PER_BB)), max_to))
    if key == "fourbet":
        return Action("raise", _raise_to(view, 2.3))
    if key == "check":
        return Action("check")
    if key == "allin":
        return Action("raise" if view.to_call_bb > 0 else "bet", max_to)
    return Action("fold")

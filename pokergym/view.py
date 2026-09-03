"""视角隔离：bot 决策只许看到 BotView。"""

from __future__ import annotations

from dataclasses import replace

from pokergym.const import CHIP_PER_BB
from pokergym.legal import can_raise, legal_kinds, to_call
from pokergym.state import TableState
from pokergym.types import BotView, PublicAction


def _bb(chips: int) -> float:
    return chips / CHIP_PER_BB


def _is_ip(st: TableState, seat: int) -> bool:
    """本街剩余行动者中，自己是否最后行动。"""
    live = [p.seat for p in st.players if not p.folded and not p.allin]
    if seat not in live:
        return False
    if st.street == "pre":
        order_start = (st.button + 3) % st.n
    else:
        order_start = (st.button + 1) % st.n
    ordered = [(order_start + i) % st.n for i in range(st.n)]
    remaining = [s for s in ordered if s in live]
    return bool(remaining) and remaining[-1] == seat


def build_bot_view(seat: int, st: TableState) -> BotView:
    p = st.players[seat]
    hole = st.holes[seat]
    board = tuple(st.board)
    tc = to_call(st, p)
    pot = st.pot_chips
    others = [o for o in st.players if o.seat != seat and not o.folded]
    eff = min([p.stack] + [o.stack for o in others]) if others else p.stack
    n_active = sum(1 for o in st.players if not o.folded)
    revealed = tuple(sorted(st.revealed.items()))
    min_raise_to = st.current_bet + st.min_raise_by
    view = BotView(
        seat=seat,
        hole=tuple(sorted(hole)),
        board=board,
        street=st.street,
        position=st.pos_name(seat),
        pot_bb=_bb(pot),
        to_call_bb=_bb(tc),
        current_bet_bb=_bb(st.current_bet),
        min_raise_to_bb=_bb(min_raise_to),
        my_stack_bb=_bb(p.stack),
        bet_street_bb=_bb(p.bet_street),
        effective_stack_bb=_bb(eff),
        spr=(_bb(eff) / _bb(pot)) if pot else 99.0,
        n_active=n_active,
        n_opponents=max(0, n_active - 1),
        is_ip=_is_ip(st, seat),
        can_raise=can_raise(st, p),
        raise_is_open=st.raise_is_open,
        action_log=tuple(st.action_log),
        showdown_history=revealed,
        my_intent=st.intent.get(seat),
        last_aggressor=st.last_aggressor,
        pfr_seat=st.pfr_seat,
        legal_kinds=legal_kinds(st, seat),
    )
    _assert_no_leak(view, st, seat)
    return view


def with_intent(view: BotView, intent: str | None) -> BotView:
    return replace(view, my_intent=intent)


def _assert_no_leak(view: BotView, st: TableState, seat: int) -> None:
    my_cards = set(view.hole) | set(view.board)
    revealed_seats = set(st.revealed)
    for other, cards in st.holes.items():
        if other == seat or other in revealed_seats:
            continue
        for c in cards:
            if c in view.hole:
                raise AssertionError(f"LEAK: seat {other} card {c} 出现在 view.hole")
            if c in view.board:
                # 公共牌撞车只可能是发牌 bug
                raise AssertionError(f"LEAK/DEAL: 公共牌含他人底牌 {c}")
            if c in my_cards:
                raise AssertionError(f"LEAK: 他人底牌 {c} 出现在可见集合")
    if view.hole != tuple(sorted(st.holes[seat])):
        raise AssertionError("view.hole 必须等于自己的底牌")
    # 禁止把全员底牌字典挂到 view 上（结构约束，不靠字符串搜）
    if hasattr(view, "holes") or hasattr(view, "all_holes"):
        raise AssertionError("LEAK: 禁止字段")

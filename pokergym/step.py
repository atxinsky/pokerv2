"""发牌、行动、边池。每手重载到 100bb（训练场约定）。"""

from __future__ import annotations

from pokergym.const import BB_CHIPS
from pokergym.evaluator import eval_best
from pokergym.legal import can_raise, legal_actions, to_call
from pokergym.state import Player, TableState
from pokergym.types import Action, PublicAction


def _put(p: Player, amount: int) -> int:
    amount = max(0, min(amount, p.stack))
    p.stack -= amount
    p.bet_street += amount
    p.committed += amount
    if p.stack == 0:
        p.allin = True
    return amount


def _needs_action(st: TableState, p: Player) -> bool:
    if p.folded or p.allin:
        return False
    if p.bet_street < st.current_bet:
        return True
    return not p.acted_this_street


def _live(st: TableState) -> list[Player]:
    return [p for p in st.players if not p.folded]


def _next_actor(st: TableState, from_seat: int) -> int | None:
    for i in range(1, st.n + 1):
        s = (from_seat + i) % st.n
        if _needs_action(st, st.players[s]):
            return s
    return None


def _first_postflop(st: TableState) -> int | None:
    start = (st.button + 1) % st.n
    for i in range(st.n):
        s = (start + i) % st.n
        if _needs_action(st, st.players[s]):
            return s
    return None


def start_hand(st: TableState) -> None:
    st.hand_idx += 1
    if st.hand_idx > 0:
        st.button = (st.button + 1) % st.n
    st.street = "pre"
    st.board = []
    st.action_log = []
    st.intent = {}
    st.revealed = {}
    st.winners = []
    st.pfr_seat = None
    st.last_aggressor = None
    st.raise_is_open = True
    st.min_raise_by = st.bb_chips
    for p in st.players:
        p.stack = st.start_stack
        p.bet_street = 0
        p.committed = 0
        p.folded = False
        p.allin = False
        p.acted_this_street = False
    st.deck = list(range(52))
    st.rng.shuffle(st.deck)
    st.holes = {}
    for p in st.players:
        c1, c2 = st.deck.pop(), st.deck.pop()
        st.holes[p.seat] = (c1, c2)
    sb = st.players[(st.button + 1) % st.n]
    bb = st.players[(st.button + 2) % st.n]
    _put(sb, st.sb_chips)
    _put(bb, st.bb_chips)
    st.current_bet = st.bb_chips
    st.to_act = (st.button + 3) % st.n
    if not _needs_action(st, st.players[st.to_act]):
        nxt = _next_actor(st, st.to_act - 1)
        st.to_act = nxt if nxt is not None else st.to_act


def _draw(st: TableState, n: int) -> list[int]:
    return [st.deck.pop() for _ in range(n)]


def _return_uncalled(st: TableState) -> None:
    live = _live(st)
    if not live:
        return
    mx = max(p.committed for p in st.players)
    second = max((p.committed for p in st.players if p.committed < mx), default=0)
    rich = [p for p in st.players if p.committed == mx]
    if len(rich) == 1 and mx > second:
        extra = mx - second
        rich[0].stack += extra
        rich[0].committed -= extra


def _payout(st: TableState) -> None:
    live = _live(st)
    if len(live) == 1:
        _return_uncalled(st)
        w = live[0]
        pot = st.pot_chips
        w.stack += pot
        st.winners.append((w.seat, pot))
        for p in st.players:
            p.committed = 0
        st.street = "over"
        return

    _return_uncalled(st)
    for p in live:
        st.revealed[p.seat] = st.holes[p.seat]
    levels = sorted({p.committed for p in st.players if p.committed > 0})
    prev = 0
    for level in levels:
        layer = level - prev
        n_in = sum(1 for p in st.players if p.committed >= level)
        pot = layer * n_in
        eligible = [p for p in live if p.committed >= level]
        if pot <= 0 or not eligible:
            prev = level
            continue
        if len(eligible) == 1:
            eligible[0].stack += pot
            st.winners.append((eligible[0].seat, pot))
        else:
            scored = [
                (eval_best(list(st.holes[p.seat]) + st.board), p.seat) for p in eligible
            ]
            best = max(s for s, _ in scored)
            win_seats = [seat for s, seat in scored if s == best]
            share, rem = divmod(pot, len(win_seats))
            # 余筹从按钮左侧开始
            order = sorted(
                win_seats, key=lambda s: (s - st.button - 1) % st.n
            )
            for i, seat in enumerate(order):
                got = share + (1 if i < rem else 0)
                st.players[seat].stack += got
                st.winners.append((seat, got))
        prev = level
    for p in st.players:
        p.committed = 0
    st.street = "over"


def _runout(st: TableState) -> None:
    while len(st.board) < 5:
        need = 3 if not st.board else 1
        st.board.extend(_draw(st, need))


def _street_reset(st: TableState) -> None:
    for p in st.players:
        p.bet_street = 0
        p.acted_this_street = False
    st.current_bet = 0
    st.min_raise_by = st.bb_chips
    st.raise_is_open = True


def _advance_street(st: TableState) -> None:
    chips_players = [p for p in _live(st) if not p.allin]
    if len(_live(st)) <= 1:
        _payout(st)
        return
    if len(chips_players) <= 1:
        _runout(st)
        _payout(st)
        return
    if st.street == "pre":
        st.street = "flop"
        st.board.extend(_draw(st, 3))
    elif st.street == "flop":
        st.street = "turn"
        st.board.extend(_draw(st, 1))
    elif st.street == "turn":
        st.street = "river"
        st.board.extend(_draw(st, 1))
    else:
        _payout(st)
        return
    _street_reset(st)
    nxt = _first_postflop(st)
    if nxt is None:
        _advance_street(st)
        return
    st.to_act = nxt


def apply_action(st: TableState, action: Action) -> None:
    p = st.players[st.to_act]
    if not _needs_action(st, p):
        raise RuntimeError(f"seat {p.seat} 不该行动")
    legal = legal_actions(st, p.seat)
    kinds = {a.kind for a in legal}
    if action.kind not in kinds:
        raise RuntimeError(f"非法动作 {action} legal={legal}")

    put = 0
    to_chips = p.bet_street
    if action.kind == "fold":
        p.folded = True
        p.acted_this_street = True
    elif action.kind == "check":
        p.acted_this_street = True
    elif action.kind == "call":
        put = _put(p, to_call(st, p))
        to_chips = p.bet_street
        p.acted_this_street = True
    elif action.kind in ("bet", "raise"):
        target = action.to_chips
        if target is None:
            target = p.bet_street + p.stack
        target = min(target, p.bet_street + p.stack)
        prev = st.current_bet
        put = _put(p, target - p.bet_street)
        to_chips = p.bet_street
        raise_by = p.bet_street - prev
        full = p.bet_street > prev and raise_by >= st.min_raise_by
        if p.bet_street > prev:
            st.current_bet = p.bet_street
            st.last_aggressor = p.seat
            if st.street == "pre" and action.kind == "raise":
                st.pfr_seat = p.seat
            if full:
                st.min_raise_by = raise_by
                st.raise_is_open = True
                for o in st.players:
                    if o.seat != p.seat and not o.folded and not o.allin:
                        o.acted_this_street = False
            else:
                # 不足额全下：跟注额上升，但不重开已行动玩家的加注权
                st.raise_is_open = False
                for o in st.players:
                    if o.seat != p.seat and not o.folded and not o.allin:
                        if o.bet_street < st.current_bet:
                            pass  # 仍需跟注，acted 保持；_needs_action 看 bet_street
        p.acted_this_street = True
    else:
        raise RuntimeError(f"未知动作 {action.kind}")

    st.action_log.append(
        PublicAction(
            seat=p.seat,
            street=st.street,
            kind=action.kind,
            to_chips=to_chips,
            put_chips=put,
            pot_chips=st.pot_chips,
        )
    )

    live = _live(st)
    if len(live) == 1:
        _payout(st)
        return
    if any(_needs_action(st, x) for x in st.players):
        nxt = _next_actor(st, p.seat)
        if nxt is None:
            _advance_street(st)
            return
        st.to_act = nxt
        return
    _advance_street(st)


def is_hand_over(st: TableState) -> bool:
    return st.street == "over"

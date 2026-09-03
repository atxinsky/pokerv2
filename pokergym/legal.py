"""合法动作。所有下注目标都是「本街累计到多少」。"""

from __future__ import annotations

from pokergym.state import Player, TableState
from pokergym.types import Action


def to_call(st: TableState, p: Player) -> int:
    return max(0, st.current_bet - p.bet_street)


def can_raise(st: TableState, p: Player) -> bool:
    tc = to_call(st, p)
    if p.stack <= tc:
        return False
    if not st.raise_is_open and p.acted_this_street:
        return False
    return True


def _unique(acts: list[Action]) -> list[Action]:
    seen: set[tuple] = set()
    out = []
    for a in acts:
        key = (a.kind, a.to_chips)
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def legal_actions(st: TableState, seat: int) -> list[Action]:
    p = st.players[seat]
    if p.folded or p.allin or st.street in ("over", "showdown"):
        return []
    tc = to_call(st, p)
    pot = st.pot_chips
    acts: list[Action] = []
    max_to = p.bet_street + p.stack

    if tc > 0:
        acts.append(Action("fold"))
        acts.append(Action("call", p.bet_street + min(tc, p.stack)))
        if can_raise(st, p):
            min_to = min(max_to, st.current_bet + st.min_raise_by)
            if min_to > st.current_bet:
                acts.append(Action("raise", min_to))
            # 常见尺度：2.5x、底池、全下
            for to in (
                st.current_bet * 3,
                st.current_bet + max(pot, st.bb_chips),
                max_to,
            ):
                to = max(min_to, min(to, max_to))
                if to > st.current_bet:
                    acts.append(Action("raise", to))
    else:
        acts.append(Action("check"))
        if p.stack > 0:
            min_to = min(max_to, p.bet_street + st.bb_chips)
            acts.append(Action("bet", min_to))
            for frac in (0.33, 0.66, 1.0, 1.5):
                to = p.bet_street + max(st.bb_chips, int(pot * frac))
                to = min(to, max_to)
                if to > p.bet_street:
                    acts.append(Action("bet", to))
            if max_to > p.bet_street:
                acts.append(Action("bet", max_to))
    return _unique(acts)


def legal_kinds(st: TableState, seat: int) -> tuple[str, ...]:
    return tuple(sorted({a.kind for a in legal_actions(st, seat)}))


def snap_action(st: TableState, seat: int, action: Action) -> Action:
    """把意图动作对齐到最近的合法动作，避免尺度/种类越界。"""
    legal = legal_actions(st, seat)
    if not legal:
        return Action("fold")
    same = [a for a in legal if a.kind == action.kind]
    if not same:
        kinds = {a.kind for a in legal}
        if action.kind == "raise" and "bet" in kinds:
            same = [a for a in legal if a.kind == "bet"]
        elif action.kind == "bet" and "raise" in kinds:
            same = [a for a in legal if a.kind == "raise"]
        elif action.kind in ("bet", "raise") and "call" in kinds:
            same = [a for a in legal if a.kind == "call"]
        elif action.kind == "call" and "check" in kinds:
            return Action("check")
        elif "check" in kinds:
            return Action("check")
        elif "call" in kinds:
            return next(a for a in legal if a.kind == "call")
        elif "fold" in kinds:
            return Action("fold")
        else:
            return legal[0]
    if action.to_chips is None:
        return same[0]
    return min(same, key=lambda a: abs((a.to_chips or 0) - (action.to_chips or 0)))

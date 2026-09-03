"""对局循环。一张桌子、一个种子，完整可复现。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from pokergym.adapt import maybe_adapt
from pokergym.bot import decide
from pokergym.const import MODE_TRAIN, N_SEATS
from pokergym.digest import HandHist, build_hand_hist
from pokergym.legal import snap_action
from pokergym.personality import BotProfile, spawn_table_bots
from pokergym.state import TableState, new_table
from pokergym.step import apply_action, is_hand_over, start_hand
from pokergym.types import Action
from pokergym.view import build_bot_view


@dataclass
class SessionResult:
    seed: int
    hands: list[HandHist]
    bots: dict[int, BotProfile]
    action_trace: list[tuple[int, int, str, int | None]] = field(default_factory=list)
    n: int = N_SEATS
    hero_seat: int | None = None
    mode: str = MODE_TRAIN


class HeroPolicy:
    """脚本英雄。decide(view, st) -> Action。"""

    seat = 0

    def decide(self, view, st) -> Action:
        raise NotImplementedError


def run_session(
    seed: int,
    n_hands: int,
    n: int = N_SEATS,
    hero: HeroPolicy | None = None,
    hero_seat: int = 0,
    mode: str = MODE_TRAIN,
) -> SessionResult:
    rng = random.Random(seed)
    st = new_table(n, rng, button=0)
    hs = hero_seat if hero is not None else None
    bots = spawn_table_bots(rng, n, hs)
    if hero is not None:
        hero.seat = hero_seat
    hist: list[HandHist] = []
    trace: list[tuple[int, int, str, int | None]] = []
    lost_big = {s: False for s in range(n)}

    for _ in range(n_hands):
        start_hand(st)
        steps = 0
        while not is_hand_over(st):
            steps += 1
            if steps > 96:
                raise RuntimeError(f"hand {st.hand_idx} 卡死 street={st.street} to_act={st.to_act}")
            seat = st.to_act
            if hero is not None and seat == hero.seat:
                view = build_bot_view(seat, st)
                raw = hero.decide(view, st)
                action = snap_action(st, seat, raw)
            else:
                action = decide(st, bots[seat], rng, lost_big=lost_big[seat])
            trace.append((st.hand_idx, seat, action.kind, action.to_chips))
            apply_action(st, action)

        reached_flop = len(st.board) >= 3
        flop_seen = {}
        folded_pre = set()
        for a in st.action_log:
            if a.street == "pre" and a.kind == "fold":
                folded_pre.add(a.seat)
        for s in range(n):
            flop_seen[s] = reached_flop and s not in folded_pre
        h = build_hand_hist(
            st.hand_idx, n, st.action_log, st.winners, st.revealed, st.pfr_seat, flop_seen
        )
        hist.append(h)
        # 谁这手大亏
        for s in range(n):
            won = h.won_chips.get(s, 0)
            lost_big[s] = won == 0 and any(v >= 2000 for v in h.won_chips.values())
        if hero is not None:
            for b in bots.values():
                b.hands_since_update += 1
                maybe_adapt(b, hist, hero.seat, st.hand_idx, mode, rng)

    return SessionResult(
        seed=seed, hands=hist, bots=bots, action_trace=trace, n=n, hero_seat=hs, mode=mode
    )

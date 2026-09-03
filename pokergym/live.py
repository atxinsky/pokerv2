"""交互对局：UI / API 共用。每次只推进一步，方便动画。"""

from __future__ import annotations

import random

from pokergym.adapt import maybe_adapt
from pokergym.bot import decide
from pokergym.coach import snapshot, tag_action
from pokergym.const import CHIP_PER_BB, MODE_TRAIN, N_SEATS
from pokergym.digest import snapshot_hand
from pokergym.legal import legal_actions, snap_action, to_call
from pokergym.personality import spawn_table_bots
from pokergym.state import new_table
from pokergym.step import apply_action, is_hand_over, start_hand
from pokergym.types import Action
from pokergym.view import build_bot_view


class LiveSession:
    def __init__(self, seed: int = 1, mode: str = MODE_TRAIN, n: int = N_SEATS, hero_seat: int = 0):
        self.seed = seed
        self.mode = mode
        self.n = n
        self.hero_seat = hero_seat
        self.rng = random.Random(seed)
        self.st = new_table(n, self.rng, button=0)
        self.bots = spawn_table_bots(self.rng, n, hero_seat)
        self.hist = []
        self.lost_big = {s: False for s in range(n)}
        self.last_tags: list[str] = []
        self.last_event: dict | None = None
        self.hand_open = False
        self.finished_recorded = False
        self.archive: list[dict] = []

    def waiting(self) -> str:
        if not self.hand_open:
            return "idle"
        if is_hand_over(self.st):
            return "over"
        if self.st.to_act == self.hero_seat:
            return "hero"
        return "bot"

    def new_hand(self) -> None:
        start_hand(self.st)
        self.hand_open = True
        self.finished_recorded = False
        self.last_tags = []
        self.last_event = None

    def _event(self, seat: int, action: Action) -> dict:
        return {
            "seat": seat,
            "kind": action.kind,
            "to_bb": None if action.to_chips is None else action.to_chips / CHIP_PER_BB,
            "name": self._name(seat),
        }

    def _name(self, seat: int) -> str:
        if seat == self.hero_seat:
            return "你"
        bot = self.bots.get(seat)
        if not bot:
            return f"座位{seat}"
        return bot.name.rstrip("0123456789") or bot.name

    def _finish_if_needed(self) -> None:
        if not is_hand_over(self.st) or self.finished_recorded:
            return
        h = snapshot_hand(self.st)
        self.hist.append(h)
        self.finished_recorded = True
        hero = self.st.players[self.hero_seat]
        self.archive.append(
            {
                "hand_idx": self.st.hand_idx,
                "delta_bb": round((hero.stack - self.st.start_stack) / CHIP_PER_BB, 2),
                "hole": self.st.holes.get(self.hero_seat),
                "board": tuple(self.st.board),
                "log": list(self.st.action_log),
                "winners": list(self.st.winners),
                "revealed": dict(self.st.revealed),
                "tags": list(self.last_tags),
                "folded": hero.folded,
                "vpip": bool(h.vpip.get(self.hero_seat)),
                "pfr": bool(h.pfr.get(self.hero_seat)),
            }
        )
        if len(self.archive) > 80:
            self.archive = self.archive[-80:]
        for s in range(self.n):
            won = h.won_chips.get(s, 0)
            self.lost_big[s] = won == 0 and any(v >= 2000 for v in h.won_chips.values())
        for b in self.bots.values():
            b.hands_since_update += 1
            maybe_adapt(b, self.hist, self.hero_seat, self.st.hand_idx, self.mode, self.rng)

    def step_bot(self) -> dict | None:
        if self.waiting() != "bot":
            self._finish_if_needed()
            return None
        seat = self.st.to_act
        action = decide(self.st, self.bots[seat], self.rng, lost_big=self.lost_big[seat])
        apply_action(self.st, action)
        self.last_event = self._event(seat, action)
        self._finish_if_needed()
        return self.last_event

    def hero_act(self, kind: str, to_bb: float | None = None) -> dict:
        if self.waiting() != "hero":
            raise RuntimeError("现在不是你行动")
        seat = self.hero_seat
        view = build_bot_view(seat, self.st)
        to_chips = None if to_bb is None else int(round(float(to_bb) * CHIP_PER_BB))
        action = snap_action(self.st, seat, Action(kind, to_chips))
        self.last_tags = tag_action(view, action)
        apply_action(self.st, action)
        self.last_event = self._event(seat, action)
        self._finish_if_needed()
        return self.last_event

    def hero_legal(self) -> list[Action]:
        if self.waiting() != "hero":
            return []
        return legal_actions(self.st, self.hero_seat)

    def hero_to_call_bb(self) -> float:
        p = self.st.players[self.hero_seat]
        return to_call(self.st, p) / CHIP_PER_BB

    def coach(self) -> dict | None:
        if not self.hand_open or self.hero_seat not in self.st.holes:
            return None
        if is_hand_over(self.st) and self.st.street == "over":
            # 结束仍给最后一手的数学，用当前可见
            pass
        view = build_bot_view(self.hero_seat, self.st)
        return snapshot(view)

"""单人牌局：UI / API 共用。每次只推进一个座位的动作。"""

from __future__ import annotations

import random
from typing import Callable, Iterator

from pokergym.adapt import maybe_adapt
from pokergym.advise import advise, review_hand
from pokergym.bot import decide
from pokergym.coach import snapshot as math_snapshot, tag_action
from pokergym.deepseek import status as llm_status
from pokergym.llm_persona import adapt_bots_async, enrich_bots_async
from pokergym.const import CHIP_PER_BB, MODE_TRAIN, N_SEATS
from pokergym.digest import snapshot_hand
from pokergym.legal import legal_actions, snap_action, to_call
from pokergym.personality import spawn_table_bots
from pokergym.state import new_table
from pokergym.step import apply_action, is_hand_over, start_hand
from pokergym.types import Action
from pokergym.view import build_bot_view


class LiveSession:
    def __init__(
        self,
        seed: int = 1,
        mode: str = MODE_TRAIN,
        n: int = N_SEATS,
        hero_seat: int = 0,
        wait_llm: bool = False,
    ):
        self.seed = seed
        self.mode = mode if mode in ("train", "realism") else "train"
        try:
            from pokergym.usage import reset_session

            reset_session()
        except Exception:
            pass
        try:
            from pokergym.store import set_setting

            set_setting("product_mode", self.mode)
        except Exception:
            pass
        self.n = n
        self.hero_seat = hero_seat
        self.rng = random.Random(seed)
        self.st = new_table(n, self.rng, button=0)
        self.bots = spawn_table_bots(self.rng, n, hero_seat)
        enrich_bots_async(self.bots, blocking=wait_llm)
        self.llm_comment: str | None = None
        self._llm_comment_key = None
        self._llm_comment_busy = False
        self.hist = []
        self.llm = llm_status()
        self._advice_cache = {}
        self._advice_key = None
        self.lost_big = {s: False for s in range(n)}
        self.last_tags: list[str] = []
        self.last_event: dict | None = None
        self.hand_open = False
        self.finished_recorded = False
        self.archive: list[dict] = []
        self.says: dict[int, str] = {}  # 每个座位最近一句嘴炮
        # Phase 1：谁在想（供 UI /api/state 展示）
        self.thinking_seat: int | None = None
        self.thinking_name: str | None = None
        self.bot_busy: bool = False
        # Phase 2: post-hand LLM review for hero
        self.llm_review: str | None = None
        self.llm_review_busy: bool = False
        self.llm_review_hand_idx: int | None = None
        # Phase 2: weakness-targeted drill focus (None = normal table)
        self.drill: dict | None = None

    def waiting(self) -> str:
        if not self.hand_open:
            return "idle"
        if is_hand_over(self.st):
            return "over"
        if self.st.to_act == self.hero_seat:
            return "hero"
        return "bot"

    def new_hand(self) -> None:
        try:
            from pokergym.store import set_setting

            set_setting("product_mode", self.mode if self.mode in ("train", "realism") else "train")
        except Exception:
            pass
        start_hand(self.st)
        self.hand_open = True
        self.finished_recorded = False
        self.last_tags = []
        self.last_event = None
        self.says = {}
        self.thinking_seat = None
        self.thinking_name = None
        self.bot_busy = False
        self.llm_review = None
        self.llm_review_busy = False
        self.llm_review_hand_idx = None

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
        rec = {
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
            "review": review_hand(
                self.st.holes.get(self.hero_seat),
                self.st.pos_name(self.hero_seat),
                self.st.action_log,
                list(self.last_tags),
                round((hero.stack - self.st.start_stack) / CHIP_PER_BB, 2),
            ),
            "llm_review": None,
        }
        self.archive.append(rec)
        self._kick_llm_review(rec)
        if len(self.archive) > 80:
            self.archive = self.archive[-80:]
        try:
            from pokergym.store import insert_hand

            insert_hand(
                {
                    "seed": self.seed,
                    "mode": self.mode,
                    "hand_idx": rec["hand_idx"],
                    "delta_bb": rec["delta_bb"],
                    "folded": rec["folded"],
                    "vpip": rec["vpip"],
                    "pfr": rec["pfr"],
                    "tags": rec["tags"],
                    "review": rec["review"],
                    "llm_review": rec.get("llm_review"),
                    "hole": list(rec["hole"] or ()),
                    "board": list(rec["board"] or ()),
                    "log": [
                        {
                            "seat": a.seat,
                            "name": self._name(a.seat),
                            "street": a.street,
                            "kind": a.kind,
                            "put_chips": a.put_chips,
                            "to_chips": a.to_chips,
                        }
                        for a in rec["log"]
                    ],
                }
            )
        except Exception:
            pass
        for s in range(self.n):
            won = h.won_chips.get(s, 0)
            self.lost_big[s] = won == 0 and any(v >= 2000 for v in h.won_chips.values())
        for b in self.bots.values():
            b.hands_since_update += 1
            maybe_adapt(b, self.hist, self.hero_seat, self.st.hand_idx, self.mode, self.rng)
        adapt_bots_async(self.bots, self.hist, self.hero_seat, self.st.hand_idx, self.mode)

    def _names(self) -> dict[int, str]:
        return {s: self._name(s) for s in range(self.n)}

    def _will_llm(self, seat: int) -> bool:
        from pokergym.llm_brain import seat_uses_llm

        return seat_uses_llm(seat, self.hero_seat, self.n, mode=self.mode)

    def step_bot(self, unlock: Callable[[], Iterator[None]] | None = None) -> dict | None:
        """推进一个 bot。unlock：在 LLM 调用期间释放服务器锁，便于 /api/state 轮询 thinking。"""
        if self.waiting() != "bot":
            self._finish_if_needed()
            return None
        seat = self.st.to_act
        bot = self.bots[seat]
        say = ""
        action = None
        from pokergym.llm_brain import decide_llm

        use_llm = self._will_llm(seat)
        self.bot_busy = True
        if use_llm:
            self.thinking_seat = seat
            self.thinking_name = self._name(seat)
        try:
            if use_llm:
                try:
                    if unlock is not None:
                        with unlock():
                            out = decide_llm(
                                self.st, bot, self._names(), lost_big=self.lost_big[seat], mode=self.mode
                            )
                    else:
                        out = decide_llm(
                            self.st, bot, self._names(), lost_big=self.lost_big[seat], mode=self.mode
                        )
                except Exception:
                    out = None
                if out:
                    action, say = out
            if action is None:
                # 规则兜底：LLM 关闭/失败/强度未覆盖时牌局照常
                action = decide(self.st, bot, self.rng, lost_big=self.lost_big[seat])
            apply_action(self.st, action)
            self.last_event = self._event(seat, action)
            if say:
                self.last_event["say"] = say
                self.says[seat] = say
            self._finish_if_needed()
            return self.last_event
        finally:
            self.thinking_seat = None
            self.thinking_name = None
            self.bot_busy = False

    def hero_act(self, kind: str, to_bb: float | None = None) -> dict:
        if self.waiting() != "hero":
            raise RuntimeError("现在轮不到你行动")
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
            # 结束后仍给最后一口教学：用当前可见
            pass
        view = build_bot_view(self.hero_seat, self.st)
        math = math_snapshot(view)
        if self.waiting() != "hero":
            out = {**math, **(self._advice_cache or {})}
            return out
        key = (
            view.street,
            view.hole,
            tuple(view.board),
            round(view.to_call_bb, 2),
            view.position,
            len(view.action_log),
        )
        if key != self._advice_key:
            try:
                self._advice_cache = advise(view)
            except Exception:
                self._advice_cache = {}
            self._advice_key = key
        adv = self._advice_cache or {}
        out = {**math, **adv}
        if adv.get("equity") is not None:
            out["equity_est"] = adv["equity"]
        out["llm_comment"] = self.llm_comment if self._llm_comment_key == key else None
        if (
            self.waiting() == "hero"
            and not self._llm_comment_busy
            and self._llm_comment_key != key
        ):
            try:
                from pokergym.llm_coach import coach_enabled, pre_hint_enabled

                if coach_enabled() and pre_hint_enabled(mode=self.mode):
                    self._kick_llm_comment(key, view, adv)
            except Exception:
                pass
        return out

    def _kick_llm_comment(self, key, view, adv: dict) -> None:
        import threading

        from pokergym.deepseek import available

        if not available():
            return
        self._llm_comment_busy = True

        def work():
            try:
                from pokergym.llm_coach import comment_spot

                text = comment_spot(view, adv)
                if text:
                    self.llm_comment = text
                    self._llm_comment_key = key
            finally:
                self._llm_comment_busy = False

        threading.Thread(target=work, daemon=True).start()

    def _kick_llm_review(self, rec: dict) -> None:
        """Async post-hand LLM review; never auto-acts for hero."""
        import threading

        try:
            from pokergym.llm_coach import coach_enabled, opponent_type_labels, review_hand_llm
        except Exception:
            return
        if not coach_enabled():
            return
        if self.llm_review_busy:
            return
        hand_idx = rec.get("hand_idx")
        self.llm_review_busy = True
        self.llm_review_hand_idx = hand_idx
        holes = rec.get("hole")
        board = rec.get("board")
        log = list(rec.get("log") or [])
        tags = list(rec.get("tags") or [])
        delta = float(rec.get("delta_bb") or 0)
        rule = rec.get("review") or {}
        names = self._names()
        opps = opponent_type_labels(self.bots, self.hero_seat)
        position = self.st.pos_name(self.hero_seat)

        def work():
            text = None
            try:
                text = review_hand_llm(
                    hole=holes,
                    board=board,
                    position=position,
                    log=log,
                    tags=tags,
                    delta_bb=delta,
                    rule_review=rule,
                    opponent_types=opps,
                    names=names,
                    detail=False,
                )
            except Exception:
                text = None
            finally:
                self.llm_review_busy = False
            if not text:
                return
            self.llm_review = text
            self.llm_review_hand_idx = hand_idx
            for row in reversed(self.archive):
                if row.get("hand_idx") == hand_idx:
                    row["llm_review"] = text
                    rev = dict(row.get("review") or {})
                    rev["llm"] = text
                    row["review"] = rev
                    break
            try:
                from pokergym.store import update_hand_llm_review

                update_hand_llm_review(hand_idx, text)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True).start()

    def request_review_detail(self) -> str | None:
        """Optional deeper review for the last finished hand."""
        if not self.archive:
            return None
        try:
            from pokergym.llm_coach import coach_enabled, opponent_type_labels, review_hand_llm
        except Exception:
            return None
        if not coach_enabled():
            return None
        rec = self.archive[-1]
        text = review_hand_llm(
            hole=rec.get("hole"),
            board=rec.get("board"),
            position=self.st.pos_name(self.hero_seat),
            log=list(rec.get("log") or []),
            tags=list(rec.get("tags") or []),
            delta_bb=float(rec.get("delta_bb") or 0),
            rule_review=rec.get("review") or {},
            opponent_types=opponent_type_labels(self.bots, self.hero_seat),
            names=self._names(),
            detail=True,
        )
        if text:
            self.llm_review = text
            self.llm_review_hand_idx = rec.get("hand_idx")
            rec["llm_review"] = text
            rev = dict(rec.get("review") or {})
            rev["llm"] = text
            rec["review"] = rev
            try:
                from pokergym.store import update_hand_llm_review

                update_hand_llm_review(rec.get("hand_idx"), text)
            except Exception:
                pass
        return text

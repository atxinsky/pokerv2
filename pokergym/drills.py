"""脚本英雄 + 泄漏训练。"""

from __future__ import annotations

from pokergym.preflop import classify_preflop, materialize_preflop
from pokergym.ranges import percentile
from pokergym.table import HeroPolicy, run_session
from pokergym.types import Action, BotView


class AlwaysFoldTo3Bet(HeroPolicy):
    """翻前能开就开，面对 3bet 永远弃。用来验收 B 层。"""

    def decide(self, view: BotView, st) -> Action:
        if view.street != "pre":
            if view.to_call_bb > 0:
                return Action("fold") if "fold" in view.legal_kinds else Action("call")
            return Action("check") if "check" in view.legal_kinds else Action("fold")
        seq = classify_preflop(view.action_log)
        if seq.facing == "threebet":
            return Action("fold")
        if seq.facing == "unopened" and percentile(view.hole) <= 0.40:
            return materialize_preflop("open", view, {"sizing_bias": 1.0})
        if seq.facing == "limp":
            return materialize_preflop("iso", view, {"sizing_bias": 1.0})
        return Action("fold")


class CallingStation(HeroPolicy):
    def decide(self, view: BotView, st) -> Action:
        if "check" in view.legal_kinds:
            return Action("check")
        if "call" in view.legal_kinds:
            return Action("call")
        return Action("fold")


class AlwaysFoldRiver(HeroPolicy):
    def decide(self, view: BotView, st) -> Action:
        if view.street == "river" and view.to_call_bb > 0:
            return Action("fold")
        if view.street == "pre":
            seq = classify_preflop(view.action_log)
            if seq.facing == "unopened" and percentile(view.hole) <= 0.25:
                return materialize_preflop("open", view, {"sizing_bias": 1.0})
        if "check" in view.legal_kinds:
            return Action("check")
        if "call" in view.legal_kinds:
            return Action("call")
        return Action("fold")


def threebet_rate(result, start: int, end: int, hero_seat: int = 0) -> float:
    """只统计：英雄开池之后，是否有人 3bet。"""
    hands = result.hands[start:end]
    opens = 0
    threes = 0
    for h in hands:
        hero_opened = False
        got_3bet = False
        for n in h.nodes:
            if n.street != "pre":
                continue
            if n.seat == hero_seat and n.action in ("raise", "open") and n.faced in (
                "unopened",
                "limp",
            ):
                hero_opened = True
            if (
                hero_opened
                and n.seat != hero_seat
                and n.action == "raise"
                and n.faced in ("open", "open_calls")
            ):
                got_3bet = True
        if hero_opened:
            opens += 1
            if got_3bet:
                threes += 1
    return threes / max(opens, 1)


def _agg_threebet_mult(result) -> float:
    from pokergym.params import resolve_params

    ratios = []
    last = result.hands[-1].hand_idx if result.hands else 0
    for b in result.bots.values():
        if b.archetype not in ("tight_aggressive", "loose_aggressive", "maniac"):
            continue
        p = resolve_params(
            b.archetype, b.base_params, b.session, b.updates, b.leaks, set(), last
        )
        ratios.append(p["threebet_freq"] / max(b.base_params["threebet_freq"], 1e-6))
    return sum(ratios) / max(len(ratios), 1)


def run_fold_to_3bet_drill(seed: int = 9, hands: int = 200) -> dict:
    hero = AlwaysFoldTo3Bet()
    res = run_session(seed=seed, n_hands=hands, hero=hero, mode="train")
    early = threebet_rate(res, 0, min(50, hands // 4), hero.seat)
    late = threebet_rate(res, max(0, hands - 50), hands, hero.seat)
    param_mult = _agg_threebet_mult(res)
    return {
        "early": early,
        "late": late,
        "lift": late / max(early, 1e-6),
        "param_mult": param_mult,
        "result": res,
    }

"""A 层决策：频率 → 采样 → 对齐合法动作。不含 LLM。"""

from __future__ import annotations

import random

from pokergym.intent import apply_transition, assign_intent
from pokergym.legal import snap_action
from pokergym.params import resolve_params
from pokergym.personality import BotProfile
from pokergym.postflop import aggressor_freqs, defender_freqs, materialize_postflop
from pokergym.preflop import classify_preflop, materialize_preflop, preflop_action
from pokergym.rngutil import sample_action
from pokergym.state import TableState
from pokergym.types import Action, BotView
from pokergym.view import build_bot_view, with_intent


def active_triggers(view: BotView, lost_big: bool) -> set[str]:
    t: set[str] = set()
    seq = classify_preflop(view.action_log)
    if seq.facing == "threebet":
        t.add("faced_3bet")
    if view.n_opponents >= 2:
        t.add("multiway_pot")
    if view.street == "river" and view.to_call_bb > 0:
        t.add("river_faced_bet")
    if view.position in ("SB", "BB"):
        t.add("in_blinds")
    if view.my_stack_bb <= 40:
        t.add("short_stacked")
    street = [a for a in view.action_log if a.street == view.street]
    kinds = [a.kind for a in street]
    if "check" in kinds and "raise" in kinds:
        t.add("faced_check_raise")
    if (
        view.street != "pre"
        and street
        and street[0].kind == "bet"
        and view.pfr_seat is not None
        and street[0].seat != view.pfr_seat
    ):
        t.add("faced_donk_bet")
    if lost_big:
        t.add("just_lost_big_pot")
    return t


def _filter_freqs(freqs: dict[str, float], view: BotView) -> dict[str, float]:
    kind_of = {
        "fold": "fold",
        "check": "check",
        "call": "call",
        "limp": "call",
        "open": "raise",
        "iso": "raise",
        "threebet": "raise",
        "squeeze": "raise",
        "fourbet": "raise",
        "bet_small": "bet",
        "bet_mid": "bet",
        "bet_big": "bet",
        "raise_min": "raise",
        "raise_mid": "raise",
        "allin": "raise" if view.to_call_bb > 0 else "bet",
    }
    legal = set(view.legal_kinds)
    out = {}
    for k, v in freqs.items():
        kind = kind_of.get(k)
        if kind is None:
            continue
        if kind not in legal:
            if kind == "raise" and "bet" in legal:
                kind = "bet"
            elif kind == "bet" and "raise" in legal:
                kind = "raise"
            elif kind == "call" and "check" in legal:
                kind = "check"
            elif kind == "check" and "call" in legal:
                kind = "call"
            else:
                continue
        if kind in legal:
            out[k] = v
    return out


def decide(
    st: TableState,
    bot: BotProfile,
    rng: random.Random,
    lost_big: bool = False,
) -> Action:
    view = build_bot_view(bot.seat, st)
    trig = active_triggers(view, lost_big)
    params = resolve_params(
        bot.archetype,
        bot.base_params,
        bot.session,
        bot.updates,
        bot.leaks,
        trig,
        st.hand_idx,
    )
    intent = view.my_intent
    faced_raise = view.to_call_bb > 0 and view.street != "pre" and "raise" in [
        a.kind for a in view.action_log if a.street == view.street
    ]
    if view.street == "flop" and intent is None:
        intent = assign_intent(view, params, rng)
        st.intent[bot.seat] = intent
    elif view.street in ("turn", "river"):
        intent = apply_transition(intent, view, faced_raise=faced_raise)
        st.intent[bot.seat] = intent
        view = with_intent(view, intent)

    if view.street == "pre":
        freqs = preflop_action(view, params, bot.archetype)
        freqs = _filter_freqs(freqs, view)
        if not freqs:
            key = "fold" if "fold" in view.legal_kinds else "check"
        else:
            key = sample_action(freqs, rng)
        raw = materialize_preflop(key, view, params)
    else:
        if view.to_call_bb > 0:
            freqs = defender_freqs(view, intent or "POT_CONTROL", params)
        else:
            freqs = aggressor_freqs(view, intent or "POT_CONTROL", params)
        freqs = _filter_freqs(freqs, view)
        if not freqs:
            key = "check" if "check" in view.legal_kinds else (
                "call" if "call" in view.legal_kinds else "fold"
            )
        else:
            key = sample_action(freqs, rng)
        raw = materialize_postflop(key, view)
    return snap_action(st, bot.seat, raw)

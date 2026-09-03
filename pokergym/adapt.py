"""B 层：规则适应。train 快狠，realism 慢且绑原型。"""

from __future__ import annotations

import random

from pokergym.const import MODE_REALISM, MODE_TRAIN
from pokergym.digest import hero_digest, n_obs, rate
from pokergym.params import ParamUpdate
from pokergym.personality import BotProfile

PASSIVE = {"loose_passive", "tight_passive"}


def _interval(mode: str, bot: BotProfile) -> int:
    if mode == MODE_TRAIN:
        return 12
    if bot.archetype in PASSIVE:
        return 40
    return 25


def maybe_adapt(
    bot: BotProfile,
    hands,
    hero_seat: int,
    hand_idx: int,
    mode: str,
    rng: random.Random,
) -> ParamUpdate | None:
    if hero_seat is None:
        return None
    if bot.hands_since_update < bot.next_update_at:
        return None
    window = 15 if mode == MODE_TRAIN else 50
    d = hero_digest(hands, hero_seat, window=window)
    if d["hands_observed"] < (8 if mode == MODE_TRAIN else 20):
        bot.next_update_at = bot.hands_since_update + 8
        return None

    scale = 1.6 if mode == MODE_TRAIN else 0.7
    if mode == MODE_REALISM and bot.archetype in PASSIVE:
        scale *= 0.25

    deltas: dict[str, float] = {}
    if n_obs(d, "vs_3bet") >= (2 if mode == MODE_TRAIN else 5) and rate(d, "vs_3bet", "fold") >= 0.60:
        deltas["threebet_freq"] = 0.15 * scale
        deltas["squeeze_freq"] = 0.10 * scale
    if n_obs(d, "vs_cbet") >= 4 and rate(d, "vs_cbet", "fold") >= 0.60:
        deltas["cbet_freq"] = 0.10 * scale
        deltas["bluff_mult"] = 0.10 * scale
    if n_obs(d, "river_faced_bet") >= 3 and rate(d, "river_faced_bet", "fold") >= 0.65:
        deltas["river_bluff_freq"] = 0.12 * scale
        deltas["bluff_mult"] = deltas.get("bluff_mult", 0) + 0.08 * scale
    if n_obs(d, "vs_cbet") >= 4 and rate(d, "vs_cbet", "call") >= 0.55:
        deltas["bluff_mult"] = deltas.get("bluff_mult", 0) - 0.10 * scale
        deltas["value_mult"] = 0.10 * scale

    # 鱼不会突然学会诈唬
    if bot.archetype == "loose_passive":
        deltas.pop("bluff_mult", None)
        if "threebet_freq" in deltas:
            deltas["threebet_freq"] = min(deltas["threebet_freq"], 0.05)

    # 相对增量上限
    for k in list(deltas):
        deltas[k] = max(-0.15, min(0.15, deltas[k]))
        if abs(deltas[k]) < 0.01:
            deltas.pop(k)

    bot.hands_since_update = 0
    bot.next_update_at = _interval(mode, bot) + rng.randint(-4, 4)
    if not deltas:
        return None
    upd = ParamUpdate(
        delta=deltas,
        applied_at=hand_idx,
        decay_hands=40 if mode == MODE_TRAIN else 70,
        confidence=0.8 if mode == MODE_TRAIN else 0.55,
    )
    bot.updates.append(upd)
    bot.hero_notes = [f"{k}:{v:+.2f}" for k, v in deltas.items()][:3]
    return upd

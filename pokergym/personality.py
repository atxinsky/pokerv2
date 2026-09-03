"""C 层：表抽样人格。不用 LLM。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from pokergym.archetypes import (
    ARCHETYPE_MIX,
    ARCHETYPE_RANGE,
    ARCHETYPES,
    ARCHETYPE_ZH,
)
from pokergym.params import SessionState, SignatureLeak, default_base

NICKNAMES = [
    "老陈", "阿强", "小周", "肥波", "阿龙", "老张", "阿伟", "大飞",
    "小美", "阿杰", "老王", "阿成", "二狗", "阿坤", "小吴", "阿辉",
    "老李", "阿峰", "阿明", "阿涛",
]

SESSION_KINDS = ("normal", "normal", "normal", "normal", "tilted", "conservative", "fatigued")

SESSION_MULT = {
    "normal": {},
    "tilted": {"bluff_mult": 1.25, "vpip": 1.12, "fold_bias": 0.85, "threebet_freq": 1.2},
    "conservative": {"bluff_mult": 0.80, "vpip": 0.90, "fold_bias": 1.15, "cbet_freq": 0.90},
    "fatigued": {"bluff_mult": 0.85, "threebet_freq": 0.90},
}

LEAK_POOL = [
    ("faced_check_raise", {"fold_to_cbet": 0.15}),
    ("faced_3bet", {"fold_to_3bet": 0.12}),
    ("multiway_pot", {"call_station_idx": 0.08}),
    ("river_faced_bet", {"fold_bias": 0.08}),
    ("just_lost_big_pot", {"vpip": 0.10, "bluff_mult": 0.20}),
    ("in_blinds", {"fold_to_cbet": -0.08}),
    ("faced_donk_bet", {"fold_to_cbet": 0.10}),
]


@dataclass
class BotProfile:
    seat: int
    name: str
    archetype: str
    base_params: dict
    session: SessionState
    leaks: list[SignatureLeak]
    updates: list = field(default_factory=list)
    hands_since_update: int = 0
    next_update_at: int = 20
    hero_notes: list[str] = field(default_factory=list)


def _offset_params(rng: random.Random, archetype: str) -> dict:
    base = default_base(archetype)
    box = ARCHETYPE_RANGE[archetype]
    out = {}
    for k, v in base.items():
        lo, hi = box[k]
        jitter = rng.uniform(0.85, 1.15)
        out[k] = min(max(v * jitter, lo), hi)
    return out


def spawn_bot(rng: random.Random, seat: int, archetype: str | None = None) -> BotProfile:
    if archetype is None:
        names = list(ARCHETYPE_MIX)
        weights = [ARCHETYPE_MIX[n] for n in names]
        archetype = rng.choices(names, weights=weights, k=1)[0]
    kind = rng.choice(SESSION_KINDS)
    leaks = []
    for trig, delta in rng.sample(LEAK_POOL, k=min(2, len(LEAK_POOL))):
        leaks.append(SignatureLeak(trigger=trig, delta=dict(delta)))
    return BotProfile(
        seat=seat,
        name=rng.choice(NICKNAMES) + str(seat),
        archetype=archetype,
        base_params=_offset_params(rng, archetype),
        session=SessionState(
            kind=kind,
            multipliers=dict(SESSION_MULT[kind]),
            start_hand=0,
            decay_hands=rng.randint(40, 120),
        ),
        leaks=leaks,
        next_update_at=rng.randint(12, 28),
    )


def spawn_table_bots(rng: random.Random, n: int, hero_seat: int | None) -> dict[int, BotProfile]:
    bots = {}
    # 保证五种原型至少各一个（英雄座位除外）
    pool = list(ARCHETYPES)
    rng.shuffle(pool)
    seats = [s for s in range(n) if s != hero_seat]
    for i, seat in enumerate(seats):
        arch = pool[i % len(pool)]
        bots[seat] = spawn_bot(rng, seat, arch)
    return bots


def desc(bot: BotProfile) -> str:
    return f"{bot.name}·{ARCHETYPE_ZH[bot.archetype]}·今晚{bot.session.kind}"

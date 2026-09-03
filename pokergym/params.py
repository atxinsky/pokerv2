"""参数合成：今晚状态 × B 层增量 × 漏洞触发 × 原型夹逼。"""

from __future__ import annotations

from dataclasses import dataclass, field

from pokergym.archetypes import ARCHETYPE_BASE, clamp_params


def decay(elapsed: int, span: int) -> float:
    if span <= 0 or elapsed >= span:
        return 0.0
    return 1.0 - elapsed / span


@dataclass
class SessionState:
    kind: str = "normal"
    multipliers: dict[str, float] = field(default_factory=dict)
    start_hand: int = 0
    decay_hands: int = 80


@dataclass
class ParamUpdate:
    delta: dict[str, float]
    applied_at: int
    decay_hands: int
    confidence: float = 1.0


@dataclass
class SignatureLeak:
    trigger: str
    delta: dict[str, float]


def resolve_params(
    archetype: str,
    base_params: dict,
    session: SessionState,
    updates: list[ParamUpdate],
    leaks: list[SignatureLeak],
    active_triggers: set[str],
    hand_idx: int,
) -> dict:
    out = {}
    for k, base_v in base_params.items():
        p = float(base_v)
        w_sess = decay(hand_idx - session.start_hand, session.decay_hands)
        if w_sess > 0:
            p *= 1.0 + (session.multipliers.get(k, 1.0) - 1.0) * w_sess
        for upd in updates:
            if k in upd.delta:
                w = decay(hand_idx - upd.applied_at, upd.decay_hands)
                p *= 1 + upd.delta[k] * w * upd.confidence
        for leak in leaks:
            if leak.trigger in active_triggers and k in leak.delta:
                p *= 1 + leak.delta[k]
        out[k] = p
    return clamp_params(archetype, out)


def default_base(archetype: str) -> dict:
    return dict(ARCHETYPE_BASE[archetype])

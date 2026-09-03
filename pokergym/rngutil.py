"""频率采样。必须对 key 排序，否则同一 seed 会因 dict 顺序漂移。"""

from __future__ import annotations

import random


def sample_action(freqs: dict[str, float], rng: random.Random) -> str:
    cleaned = {k: max(0.0, float(v)) for k, v in freqs.items() if v > 0}
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError(f"空频率表: {freqs}")
    r = rng.random() * total
    acc = 0.0
    keys = sorted(cleaned)
    for k in keys:
        acc += cleaned[k]
        if r < acc:
            return k
    return keys[-1]


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    return sample_action(weights, rng)

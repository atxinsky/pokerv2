"""169 手牌排序。翻前用百分位阈值，不维护完整组合范围。"""

from __future__ import annotations

from pokergym.cards import RANKS


def hole_code(hole) -> str:
    r1, r2 = hole[0] % 13, hole[1] % 13
    s1, s2 = hole[0] // 13, hole[1] // 13
    a, b = max(r1, r2), min(r1, r2)
    if a == b:
        return f"{RANKS[a]}{RANKS[b]}"
    return f"{RANKS[a]}{RANKS[b]}{'s' if s1 == s2 else 'o'}"


def _strength(code: str) -> float:
    a = RANKS.index(code[0])
    b = RANKS.index(code[1])
    if a == b:
        return 1000 + a * 15
    suited = 16 if code.endswith("s") else 0
    gap = a - b
    score = a * 18 + b * 4 + suited - gap * 10
    if a == 12:
        score += 10
    if gap == 1:
        score += 6
    if gap == 0:
        score += 20
    return score


def _all_codes() -> list[str]:
    out = []
    for i in range(13):
        out.append(RANKS[i] * 2)
        for j in range(i):
            out.append(f"{RANKS[i]}{RANKS[j]}s")
            out.append(f"{RANKS[i]}{RANKS[j]}o")
    return out


RANKED_169: list[str] = sorted(_all_codes(), key=_strength, reverse=True)
RANK_INDEX: dict[str, int] = {h: i for i, h in enumerate(RANKED_169)}


def percentile(hole) -> float:
    """0 = 最强，1 = 最弱。"""
    return RANK_INDEX[hole_code(hole)] / (len(RANKED_169) - 1)


def in_top(hole, frac: float) -> bool:
    return percentile(hole) <= frac

"""蒙特卡洛胜率。相对给定 169 范围或随机手。"""

from __future__ import annotations

import random

from pokergym.cards import RANKS
from pokergym.evaluator import eval_best
from pokergym.ranges import hole_code

_SUITS = (0, 1, 2, 3)


def _rank(ch: str) -> int:
    return RANKS.index(ch)


def combos_of(code: str, dead: set[int]) -> list[tuple[int, int]]:
    if len(code) == 2:
        r = _rank(code[0])
        out = []
        for i, s1 in enumerate(_SUITS):
            for s2 in _SUITS[i + 1 :]:
                a, b = r + 13 * s1, r + 13 * s2
                if a not in dead and b not in dead:
                    out.append((a, b))
        return out
    r1, r2 = _rank(code[0]), _rank(code[1])
    suited = code.endswith("s")
    out = []
    if suited:
        for s in _SUITS:
            a, b = r1 + 13 * s, r2 + 13 * s
            if a not in dead and b not in dead:
                out.append((a, b))
    else:
        for s1 in _SUITS:
            for s2 in _SUITS:
                if s1 == s2:
                    continue
                a, b = r1 + 13 * s1, r2 + 13 * s2
                if a not in dead and b not in dead:
                    out.append((a, b))
    return out


def expand_range(codes, dead: set[int]) -> list[tuple[int, int]]:
    out = []
    for c in codes:
        out.extend(combos_of(c, dead))
    return out


def equity_vs_combos(
    hole,
    board,
    villains: list[tuple[int, int]],
    iters: int = 140,
    rng: random.Random | None = None,
) -> float:
    if not villains:
        return 0.5
    rng = rng or random.Random(1)
    dead = set(hole) | set(board)
    remaining = [c for c in range(52) if c not in dead]
    need = 5 - len(board)
    wins = 0.0
    n = 0
    hero = list(hole)
    for _ in range(iters):
        vh = villains[rng.randrange(len(villains))]
        if vh[0] in dead or vh[1] in dead:
            continue
        dead2 = dead | {vh[0], vh[1]}
        pool = [c for c in remaining if c not in dead2]
        if len(pool) < need:
            continue
        extra = rng.sample(pool, need) if need else []
        brd = list(board) + extra
        hs = eval_best(hero + brd)
        vs = eval_best([vh[0], vh[1]] + brd)
        if hs > vs:
            wins += 1
        elif hs == vs:
            wins += 0.5
        n += 1
    return wins / n if n else 0.5


def equity_vs_codes(hole, board, codes, iters: int = 240) -> float:
    dead = set(hole) | set(board)
    vill = expand_range(codes, dead)
    return equity_vs_combos(hole, board, vill, iters=iters)


def equity_preflop(hole, codes, iters: int = 180) -> float:
    return equity_vs_codes(hole, (), codes, iters=iters)

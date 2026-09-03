"""5/7 张牌力评估。分数越大越强，可直接整数比较。"""

from __future__ import annotations

from itertools import combinations

# 类别：8 同花顺 … 0 高牌
CAT_SF, CAT_QUADS, CAT_FH, CAT_FLUSH, CAT_ST = 8, 7, 6, 5, 4
CAT_TRIPS, CAT_TWO, CAT_PAIR, CAT_HIGH = 3, 2, 1, 0


def pack(cat: int, *kickers: int) -> int:
    v = cat << 20
    for i, k in enumerate(kickers):
        v |= (k & 15) << (16 - 4 * i)
    return v


def category(score: int) -> int:
    return score >> 20


def _straight_high(bits: int) -> int | None:
    for high in range(12, 3, -1):  # A-high 到 6-high
        mask = 0
        for i in range(5):
            mask |= 1 << (high - i)
        if (bits & mask) == mask:
            return high
    wheel = (1 << 12) | 0b1111  # A2345
    if (bits & wheel) == wheel:
        return 3
    return None


def eval5(cards) -> int:
    cards = list(cards)
    ranks = [c % 13 for c in cards]
    suits = [c // 13 for c in cards]
    counts = [0] * 13
    bits = 0
    for r in ranks:
        counts[r] += 1
        bits |= 1 << r
    is_flush = len(set(suits)) == 1
    st_high = _straight_high(bits)

    quads = [r for r in range(12, -1, -1) if counts[r] == 4]
    trips = [r for r in range(12, -1, -1) if counts[r] == 3]
    pairs = [r for r in range(12, -1, -1) if counts[r] == 2]
    singles = [r for r in range(12, -1, -1) if counts[r] == 1]

    if is_flush and st_high is not None:
        return pack(CAT_SF, st_high)
    if quads:
        k = singles[0] if singles else trips[0]
        return pack(CAT_QUADS, quads[0], k)
    if trips and pairs:
        return pack(CAT_FH, trips[0], pairs[0])
    if is_flush:
        return pack(CAT_FLUSH, *sorted(ranks, reverse=True))
    if st_high is not None:
        return pack(CAT_ST, st_high)
    if trips:
        return pack(CAT_TRIPS, trips[0], *singles)
    if len(pairs) >= 2:
        k = singles[0] if singles else 0
        return pack(CAT_TWO, pairs[0], pairs[1], k)
    if pairs:
        return pack(CAT_PAIR, pairs[0], *singles)
    return pack(CAT_HIGH, *sorted(ranks, reverse=True))


def eval_best(cards) -> int:
    cards = list(cards)
    n = len(cards)
    if n < 5:
        return 0
    if n == 5:
        return eval5(cards)
    best = -1
    for combo in combinations(cards, 5):
        s = eval5(combo)
        if s > best:
            best = s
    return best


def winner_seats(holes: dict[int, tuple], board, seats: list[int]) -> list[int]:
    scored = [(eval_best(list(holes[s]) + list(board)), s) for s in seats]
    best = max(s for s, _ in scored)
    return [seat for s, seat in scored if s == best]

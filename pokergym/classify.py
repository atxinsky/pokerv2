"""牌力、牌面结构、转牌性质。听牌：强听 ≥8 outs（含同花听）。"""

from __future__ import annotations

from collections import Counter

from pokergym.evaluator import eval_best

HAND_CLASSES = (
    "NUTTED",
    "STRONG",
    "MEDIUM",
    "WEAK_MADE",
    "DRAW_STRONG",
    "DRAW_WEAK",
    "AIR",
)

MADE_RANK = {
    "AIR": 0,
    "WEAK_MADE": 1,
    "MEDIUM": 2,
    "STRONG": 3,
    "NUTTED": 4,
    "DRAW_WEAK": 1,
    "DRAW_STRONG": 2,
}

TEXTURES = ("MONOTONE", "PAIRED", "WET_CONNECTED", "HIGH_CARD", "DRY_RAINBOW")


def _ranks(cs) -> list[int]:
    return [c % 13 for c in cs]


def classify_made(hole, board) -> str:
    cards = list(hole) + list(board)
    if len(cards) < 5:
        return "AIR"
    score = eval_best(cards)
    cat = score >> 20
    if cat >= 4:  # 顺子及以上
        return "NUTTED"
    if cat == 3:  # 三条
        return "NUTTED"
    if cat == 2:
        return "STRONG" if _is_bottom_two(hole, board) else "NUTTED"
    if cat == 1:
        return _classify_pair(hole, board)
    hr = sorted(_ranks(hole), reverse=True)
    if hr[0] == 12:
        return "WEAK_MADE"
    return "AIR"


def _is_bottom_two(hole, board) -> bool:
    if len(board) < 3:
        return False
    br = sorted(_ranks(board[:3]))
    hr = sorted(_ranks(hole))
    if hr[0] == hr[1]:
        return False
    return hr[0] == br[0] and hr[1] == br[1] and hr[1] != br[2]


def _classify_pair(hole, board) -> str:
    br = sorted(_ranks(board), reverse=True)
    hr = _ranks(hole)
    top = br[0]
    second = br[1] if len(br) > 1 else -1
    pocket = hr[0] == hr[1]
    if pocket:
        if hr[0] > top:
            return "STRONG"  # 超对
        if hr[0] == top:
            return "NUTTED"  # 暗三
        if hr[0] >= second:
            return "MEDIUM"
        return "WEAK_MADE"
    if top in hr:
        kicker = hr[0] if hr[1] == top else hr[1]
        if kicker >= 10 or kicker == 12:
            return "STRONG"
        return "MEDIUM"
    if second in hr:
        return "MEDIUM"
    return "WEAK_MADE"


def count_outs(hole, board) -> int:
    if len(board) < 3 or len(board) >= 5:
        return 0
    used = set(hole) | set(board)
    made0 = classify_made(hole, board)
    r0 = MADE_RANK[made0]
    outs = 0
    for c in range(52):
        if c in used:
            continue
        made1 = classify_made(hole, list(board) + [c])
        if MADE_RANK[made1] > r0:
            outs += 1
    return outs


def hand_class(hole, board) -> str:
    if len(board) < 3:
        return "AIR"
    made = classify_made(hole, board)
    if len(board) >= 5:
        return made
    if made in ("NUTTED", "STRONG"):
        return made
    outs = count_outs(hole, board)
    if outs >= 8:
        return "DRAW_STRONG"
    if outs >= 4 and made in ("WEAK_MADE", "AIR", "MEDIUM"):
        if made == "MEDIUM":
            return "MEDIUM"
        return "DRAW_WEAK"
    return made


def board_texture(board) -> str:
    if len(board) < 3:
        return "DRY_RAINBOW"
    flop = list(board[:3])
    suits = [c // 13 for c in flop]
    ranks = sorted(_ranks(flop))
    sc = Counter(suits)
    rc = Counter(ranks)
    if max(sc.values()) == 3:
        return "MONOTONE"
    if max(rc.values()) >= 2:
        return "PAIRED"
    two_tone = max(sc.values()) == 2
    connected = (ranks[2] - ranks[1] <= 2) or (ranks[1] - ranks[0] <= 2)
    span = ranks[2] - ranks[0]
    if two_tone or (connected and span <= 6):
        return "WET_CONNECTED"
    if max(ranks) >= 11 and span >= 4:
        return "HIGH_CARD"
    return "DRY_RAINBOW"


def _completes_flush(before, new_card) -> bool:
    suits = [c // 13 for c in before]
    if not suits:
        return False
    s, n = Counter(suits).most_common(1)[0]
    return n == 2 and new_card // 13 == s


def _completes_straight(before, new_card) -> bool:
    ranks = set(_ranks(before) + [new_card % 13])
    if 12 in ranks:
        ranks.add(-1)  # 轮子用 -1 当 A
    rs = sorted(ranks)
    run = 1
    for i in range(1, len(rs)):
        if rs[i] == rs[i - 1] + 1:
            run += 1
            if run >= 5:
                return True
        elif rs[i] != rs[i - 1]:
            run = 1
    return False


def turn_card_class(hole, board_before, new_card, intent: str | None) -> str:
    after = list(board_before) + [new_card]
    made0 = classify_made(hole, board_before)
    made1 = classify_made(hole, after)
    if MADE_RANK[made1] > MADE_RANK[made0]:
        return "REINFORCE"
    scare = (
        new_card % 13 >= 11
        or _completes_flush(board_before, new_card)
        or _completes_straight(board_before, new_card)
    )
    if scare:
        if intent in ("PURE_BLUFF", "SEMI_BLUFF", "PURE_VALUE"):
            return "SCARE_VILLAIN"
        return "HELP_VILLAIN"
    return "BLANK"


TEXTURE_BLUFF_MULT = {
    "DRY_RAINBOW": 1.3,
    "HIGH_CARD": 1.2,
    "PAIRED": 1.0,
    "WET_CONNECTED": 0.7,
    "MONOTONE": 0.6,
}

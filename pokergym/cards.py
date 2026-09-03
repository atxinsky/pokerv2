"""牌面编码：0-51，rank = c % 13（2=0 … A=12），suit = c // 13（cdhs）。"""

from __future__ import annotations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
SUIT_ZH = "♣♦♥♠"

def card_rank(c: int) -> int:
    return c % 13


def card_suit(c: int) -> int:
    return c // 13


def make_card(rank: int, suit: int) -> int:
    return suit * 13 + rank


def parse_card(s: str) -> int:
    s = s.strip()
    return make_card(RANKS.index(s[0].upper()), SUITS.index(s[1].lower()))


def parse_cards(text: str) -> tuple[int, ...]:
    parts = text.replace(",", " ").split()
    return tuple(parse_card(p) for p in parts)


def card_str(c: int) -> str:
    return RANKS[card_rank(c)] + SUITS[card_suit(c)]


def cards_str(cs) -> str:
    return " ".join(card_str(c) for c in cs)


def card_pretty(c: int) -> str:
    return RANKS[card_rank(c)] + SUIT_ZH[card_suit(c)]

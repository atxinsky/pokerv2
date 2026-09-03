from random import Random

from pokergym.state import new_table
from pokergym.step import start_hand
from pokergym.view import build_bot_view


def test_no_hole_card_leak():
    st = new_table(8, Random(7))
    start_hand(st)
    # 再发一张公共牌前，每人底牌都不同
    all_cards = {}
    for seat, hole in st.holes.items():
        all_cards[seat] = set(hole)
    for seat in range(8):
        v = build_bot_view(seat, st)
        mine = set(v.hole)
        assert mine == all_cards[seat]
        for other, cards in all_cards.items():
            if other == seat:
                continue
            assert cards.isdisjoint(mine)
            assert cards.isdisjoint(set(v.board))


def test_view_only_own_hole():
    st = new_table(8, Random(8))
    start_hand(st)
    v = build_bot_view(st.to_act, st)
    assert v.hole == tuple(sorted(st.holes[st.to_act]))
    assert not hasattr(v, "holes")

from pokergym.cards import parse_cards
from pokergym.classify import board_texture, count_outs, hand_class


def test_flush_draw_is_strong():
    hole = parse_cards("Ah 2h")
    board = parse_cards("Kh 9h 3c")
    assert count_outs(hole, board) >= 8
    assert hand_class(hole, board) == "DRAW_STRONG"


def test_overpair_strong():
    hole = parse_cards("Qs Qd")
    board = parse_cards("Jh 8c 2d")
    assert hand_class(hole, board) == "STRONG"


def test_set_nutted():
    hole = parse_cards("9h 9d")
    board = parse_cards("9c 2d 7s")
    assert hand_class(hole, board) == "NUTTED"


def test_texture_priority():
    assert board_texture(parse_cards("Kh 7h 2h")) == "MONOTONE"
    assert board_texture(parse_cards("Kh Kd 2c")) == "PAIRED"
    assert board_texture(parse_cards("Jh Th 8c")) == "WET_CONNECTED"
    assert board_texture(parse_cards("Kh 7c 2d")) == "HIGH_CARD"

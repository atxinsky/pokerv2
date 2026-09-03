from pokergym.cards import parse_cards
from pokergym.evaluator import CAT_FLUSH, CAT_QUADS, CAT_SF, CAT_ST, category, eval5, eval_best


def _e(text: str) -> int:
    return eval5(parse_cards(text))


def test_royal_beats_steel_wheel():
    royal = _e("Ah Kh Qh Jh Th")
    wheel = _e("Ah 2h 3h 4h 5h")
    assert category(royal) == CAT_SF
    assert category(wheel) == CAT_SF
    assert royal > wheel


def test_wheel_straight():
    s = _e("Ah 2c 3d 4s 5h")
    assert category(s) == CAT_ST
    six = _e("2c 3d 4s 5h 6c")
    assert six > s


def test_quads_beat_full_house():
    q = _e("9h 9d 9c 9s Ah")
    fh = _e("9h 9d 9c Ah Ad")
    assert category(q) == CAT_QUADS
    assert q > fh


def test_flush_beats_straight():
    fl = _e("Ah 3h 8h 9h Jh")
    st = _e("Ah Kd Qc Js Th")
    assert category(fl) == CAT_FLUSH
    assert fl > st


def test_eval7_picks_best():
    # 公共牌垃圾，口袋 AA 成一对
    hole = parse_cards("As Ad")
    board = parse_cards("2c 7d 8h 9s Jh")
    s = eval_best(list(hole) + list(board))
    pair_aa = _e("As Ad Jh 9s 8h")
    assert s == pair_aa

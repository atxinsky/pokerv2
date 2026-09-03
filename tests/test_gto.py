from pokergym.advise import advise
from pokergym.gto import in_3bet, in_open, preflop_line as gto_line
from pokergym.cards import parse_cards
from pokergym.types import BotView


def test_open_chart_sanity():
    assert in_open("UTG", "AA")
    assert in_open("UTG", "AKs")
    assert not in_open("UTG", "72o")
    assert in_open("BTN", "A4o")
    assert not in_open("BTN", "72o")
    assert gto_line("BB", "unopened", "AA") == "check"


def test_3bet_value():
    assert in_3bet("BTN", "AKs")
    assert in_3bet("CO", "QQ")
    assert not in_3bet("UTG", "22")


def test_advise_fold_junk_utg():
    hole = parse_cards("7c 2d")
    view = BotView(
        seat=3,
        hole=tuple(sorted(hole)),
        board=(),
        street="pre",
        position="UTG",
        pot_bb=1.5,
        to_call_bb=0.0,
        current_bet_bb=1.0,
        min_raise_to_bb=2.0,
        my_stack_bb=100,
        bet_street_bb=0,
        effective_stack_bb=100,
        spr=66,
        n_active=8,
        n_opponents=7,
        is_ip=False,
        can_raise=True,
        raise_is_open=True,
        action_log=(),
        showdown_history=(),
        my_intent=None,
        last_aggressor=None,
        pfr_seat=None,
        legal_kinds=("fold", "raise"),
    )
    a = advise(view)
    assert a["code"] == "72o"
    assert a["action"] == "fold"
    assert a["grid"]
    assert len(a["grid"]) == 13

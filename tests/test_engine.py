from random import Random

from pokergym.cards import parse_cards
from pokergym.legal import legal_actions, to_call
from pokergym.state import new_table
from pokergym.step import _payout, apply_action, start_hand
from pokergym.types import Action


def test_start_blinds_and_utg():
    st = new_table(8, Random(1), button=0)
    start_hand(st)
    assert st.street == "pre"
    sb = st.players[1]
    bb = st.players[2]
    assert sb.committed == 50
    assert bb.committed == 100
    assert st.to_act == 3  # UTG
    assert st.current_bet == 100


def test_fold_around_bb_wins():
    st = new_table(8, Random(2), button=0)
    start_hand(st)
    # UTG 到 SB 全弃
    while st.street != "over":
        p = st.players[st.to_act]
        if p.seat == 2:  # BB 不该再动
            break
        apply_action(st, Action("fold"))
    assert st.street == "over"
    assert st.winners[0][0] == 2
    # 未叫的大盲退回，净赢小盲 0.5bb
    assert st.players[2].stack == st.start_stack + 50


def test_min_raise_chain():
    st = new_table(8, Random(3), button=0)
    start_hand(st)
    apply_action(st, Action("raise", 350))  # UTG open 3.5bb
    assert st.current_bet == 350
    assert st.min_raise_by == 250
    # UTG1 fold until we get a reraise from next
    while st.to_act != 4:
        if st.players[st.to_act].bet_street < st.current_bet:
            apply_action(st, Action("fold"))
        else:
            break
    apply_action(st, Action("raise", 600))  # 350+250=600 min
    assert st.current_bet == 600


def test_side_pot_three_way():
    rng = Random(0)
    st = new_table(3, rng)
    st.street = "river"
    st.board = list(parse_cards("Ah Kd 9c 4s 2d"))
    st.holes = {
        0: parse_cards("Ac Ad"),
        1: parse_cards("Kc Ks"),
        2: parse_cards("7c 8c"),
    }
    for i, comm in enumerate((10000, 5000, 2000)):
        st.players[i].committed = comm
        st.players[i].stack = 0
        st.players[i].allin = True
        st.players[i].folded = False
    _payout(st)
    # 0 赢全部他人筹码 7000，自己拿回 10000 → 栈 17000
    assert st.players[0].stack == 17000
    assert st.players[1].stack == 0
    assert st.players[2].stack == 0


def test_check_option_bb():
    st = new_table(6, Random(4), button=0)
    start_hand(st)
    # 全员 limp 到 BB
    while st.street == "pre":
        p = st.players[st.to_act]
        tc = to_call(st, p)
        if p.seat == (st.button + 2) % st.n and tc == 0:
            kinds = {a.kind for a in legal_actions(st, p.seat)}
            assert "check" in kinds
            assert "bet" in kinds or "raise" in kinds
            apply_action(st, Action("check"))
            break
        if tc > 0:
            apply_action(st, Action("call"))
        else:
            apply_action(st, Action("check"))
    assert st.street == "flop"

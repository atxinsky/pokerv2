import json

from pokergym.live import LiveSession
from pokergym.serialize import dump_state


def _drive(sess: LiveSession, limit: int = 90):
    n = 0
    while sess.waiting() != "over" and n < limit:
        w = sess.waiting()
        if w == "bot":
            sess.step_bot()
        elif w == "hero":
            kinds = {a.kind for a in sess.hero_legal()}
            if "check" in kinds:
                sess.hero_act("check")
            elif "call" in kinds:
                sess.hero_act("call")
            elif "fold" in kinds:
                sess.hero_act("fold")
            else:
                break
        else:
            break
        n += 1
    return n


def test_live_finishes_a_hand():
    s = LiveSession(seed=11)
    s.new_hand()
    _drive(s)
    assert s.waiting() == "over"
    assert len(s.hist) == 1


def test_dump_does_not_leak_villain_holes():
    s = LiveSession(seed=4)
    s.new_hand()
    data = dump_state(s)
    blob_ids = []

    def walk(x):
        if isinstance(x, dict):
            if "id" in x and "rank" in x and "suit" in x:
                blob_ids.append(x["id"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(data)
    hero = set(s.st.holes[s.hero_seat]) | set(s.st.board)
    for seat, hole in s.st.holes.items():
        if seat == s.hero_seat:
            continue
        for c in hole:
            assert c not in blob_ids or c in hero


def test_json_roundtrip():
    s = LiveSession(seed=5)
    s.new_hand()
    raw = json.dumps(dump_state(s), ensure_ascii=False)
    assert "翻前" in raw or "翻牌" in raw
    assert "seats" in raw

"""全 LLM 出牌层测试：mock chat_json，不打真实网络。"""

from __future__ import annotations

import pytest

from pokergym import llm_brain
from pokergym.cards import card_pretty
from pokergym.live import LiveSession


@pytest.fixture
def brain_on(monkeypatch):
    """强制打开全 LLM 出牌，并接管 chat_json。"""
    monkeypatch.setenv("POKERGYM_LLM", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("POKERGYM_LLM_BRAIN", "1")
    monkeypatch.setenv("POKERGYM_LLM_BRAIN_INTENSITY", "full")
    monkeypatch.setattr(llm_brain, "brain_enabled", lambda: True)
    monkeypatch.setattr(llm_brain, "seat_uses_llm", lambda seat, hero, n, mode=None: True)
    calls = []

    def fake_chat(system, user, **kw):
        calls.append((system, user))
        return {"action": "fold", "say": "这牌没法打"}

    monkeypatch.setattr(llm_brain, "chat_json", fake_chat)
    return calls


def _step_to_bot(sess: LiveSession, limit: int = 60) -> None:
    """英雄用引擎快速过，直到轮到某个 bot。"""
    n = 0
    while sess.waiting() != "bot" and n < limit:
        if sess.waiting() == "hero":
            kinds = {a.kind for a in sess.hero_legal()}
            sess.hero_act("check" if "check" in kinds else ("call" if "call" in kinds else "fold"))
        n += 1


def test_llm_decides_and_says(brain_on):
    s = LiveSession(seed=7)
    s.new_hand()
    _step_to_bot(s)
    assert s.waiting() == "bot"
    seat = s.st.to_act
    s.step_bot()
    assert brain_on, "应该调用了 chat_json"
    assert s.last_event["seat"] == seat
    # mock 说 fold：若 fold 合法就该真是 fold，否则被 snap 到合法动作
    assert s.last_event["kind"] in ("fold", "check", "call", "bet", "raise")
    assert s.last_event.get("say") == "这牌没法打"
    assert s.says.get(seat) == "这牌没法打"
    assert s.thinking_seat is None
    assert s.bot_busy is False


def test_thinking_flag_during_llm(brain_on, monkeypatch):
    """LLM 调用期间 thinking_seat / bot_busy 置位，结束后清空。"""
    seen = {}
    s = LiveSession(seed=11)
    s.new_hand()
    _step_to_bot(s)
    assert s.waiting() == "bot"
    seat = s.st.to_act

    real = llm_brain.decide_llm

    def wrap(st, bot, names, lost_big=False, timeout=None, mode=None):
        seen["during"] = (s.thinking_seat, s.bot_busy, s.thinking_name)
        return real(st, bot, names, lost_big=lost_big, timeout=timeout, mode=mode)

    monkeypatch.setattr(llm_brain, "decide_llm", wrap)

    s.step_bot()
    assert seen.get("during") is not None
    assert seen["during"][0] == seat
    assert seen["during"][1] is True
    assert seen["during"][2]  # name set
    assert s.thinking_seat is None
    assert s.bot_busy is False


def test_prompt_contains_own_hole_not_hero(brain_on):
    """喂给 LLM 的 prompt：有自己底牌，没英雄底牌。"""
    s = LiveSession(seed=5)
    s.new_hand()
    _step_to_bot(s)
    assert s.waiting() == "bot"
    seat = s.st.to_act
    hero_hole = [card_pretty(c) for c in s.st.holes[s.hero_seat]]
    bot_hole = [card_pretty(c) for c in s.st.holes[seat]]
    s.step_bot()
    assert brain_on
    _, user = brain_on[-1]
    for c in bot_hole:
        assert c in user, "prompt 应包含 bot 自己的底牌"
    # 英雄底牌不能出现（除非撞脸：bot 自己也有同花色的牌，逐张精确匹配词边界即可）
    for c in hero_hole:
        if c not in bot_hole:
            assert c not in user, f"英雄底牌 {c} 泄漏进 prompt"


def test_fallback_when_llm_dead(monkeypatch):
    """LLM 返回垃圾/超时：引擎兜底，牌局照常推进。"""
    monkeypatch.setenv("POKERGYM_LLM", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("POKERGYM_LLM_BRAIN", "1")
    monkeypatch.setattr(llm_brain, "brain_enabled", lambda: True)
    monkeypatch.setattr(llm_brain, "seat_uses_llm", lambda seat, hero, n, mode=None: True)
    monkeypatch.setattr(llm_brain, "chat_json", lambda *a, **k: None)
    s = LiveSession(seed=9)
    s.new_hand()
    _step_to_bot(s)
    assert s.waiting() == "bot"
    before = len(s.st.action_log)
    s.step_bot()
    assert len(s.st.action_log) == before + 1
    assert not (s.last_event or {}).get("say")
    assert s.thinking_seat is None


def test_brain_off_by_default(monkeypatch):
    """显式关掉 brain 时走纯引擎，不调 LLM。"""
    monkeypatch.setenv("POKERGYM_LLM_BRAIN", "0")
    monkeypatch.setattr(llm_brain, "chat_json", lambda *a, **k: pytest.fail("不该调 LLM"))
    s = LiveSession(seed=13)
    s.new_hand()
    _step_to_bot(s)
    assert s.waiting() == "bot"
    s.step_bot()
    assert s.last_event is not None


def test_intensity_limits_seats(monkeypatch):
    """低强度时只有部分座位走 LLM。"""
    monkeypatch.setenv("POKERGYM_LLM", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("POKERGYM_LLM_BRAIN", "1")
    monkeypatch.setenv("POKERGYM_LLM_BRAIN_INTENSITY", "low")
    # 重新读 env
    monkeypatch.setattr(llm_brain, "brain_enabled", lambda: True)
    monkeypatch.setattr(llm_brain, "brain_intensity", lambda mode=None: "low")

    # 8 人桌 hero=0 → 7 bots，low=0.25 → k=max(1, round(1.75))=2 → seats 1,2
    assert llm_brain.seat_uses_llm(1, 0, 8) is True
    assert llm_brain.seat_uses_llm(2, 0, 8) is True
    assert llm_brain.seat_uses_llm(3, 0, 8) is False
    assert llm_brain.seat_uses_llm(7, 0, 8) is False


def test_state_exposes_thinking_shape(brain_on, monkeypatch):
    from pokergym.serialize import dump_state

    s = LiveSession(seed=3)
    s.new_hand()
    data = dump_state(s)
    assert "thinking" in data
    assert data["thinking"]["busy"] is False
    assert data["thinking"]["seat"] is None
    for seat in data["seats"]:
        assert "thinking" in seat
        assert "busy" in seat

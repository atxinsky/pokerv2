"""Phase 2 coach: mock LLM post-hand review + settings (no network)."""

from __future__ import annotations

import time

import pytest

from pokergym import llm_coach
from pokergym.live import LiveSession
from pokergym.serialize import dump_state
from pokergym.store import public_settings, save_settings


@pytest.fixture
def coach_on(monkeypatch):
    monkeypatch.setenv("POKERGYM_LLM", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("POKERGYM_COACH", "1")
    monkeypatch.setenv("POKERGYM_COACH_PRE_HINT", "0")
    monkeypatch.setattr(llm_coach, "coach_enabled", lambda: True)
    monkeypatch.setattr(llm_coach, "pre_hint_enabled", lambda mode=None: False)
    monkeypatch.setattr(llm_coach, "available", lambda: True)
    calls = []

    def fake_chat(system, user, **kw):
        calls.append((system, user, kw))
        if "review" in system or '"review"' in system:
            return {"review": "MOCK_REVIEW: better line is fold pre."}
        return {"comment": "MOCK_HINT: keep it tight."}

    monkeypatch.setattr(llm_coach, "chat_json", fake_chat)
    return calls


def _play_to_over(sess: LiveSession, limit: int = 200) -> None:
    n = 0
    while sess.waiting() != "over" and n < limit:
        w = sess.waiting()
        if w == "hero":
            kinds = {a.kind for a in sess.hero_legal()}
            if "fold" in kinds:
                sess.hero_act("fold")
            elif "check" in kinds:
                sess.hero_act("check")
            elif "call" in kinds:
                sess.hero_act("call")
            else:
                sess.hero_act("fold")
        elif w == "bot":
            sess.step_bot()
        else:
            break
        n += 1


def test_posthand_llm_review_stored(coach_on):
    s = LiveSession(seed=21)
    s.new_hand()
    _play_to_over(s)
    assert s.waiting() == "over"
    assert s.archive
    # async thread — wait briefly
    for _ in range(50):
        if s.archive[-1].get("llm_review"):
            break
        time.sleep(0.02)
    assert s.archive[-1].get("llm_review")
    assert "MOCK_REVIEW" in s.archive[-1]["llm_review"]
    assert coach_on
    data = dump_state(s)
    assert data.get("hand_review")
    assert data["hand_review"].get("llm_review")
    assert "coach_panel" in data
    hist = data.get("history") or []
    assert hist
    assert any(h.get("llm_review") for h in hist) or (hist[0].get("review") or {}).get("llm")


def test_pre_hint_default_off(coach_on, monkeypatch):
    monkeypatch.setattr(llm_coach, "pre_hint_enabled", lambda mode=None: False)
    s = LiveSession(seed=22)
    s.new_hand()
    # force hero to act if needed
    n = 0
    while s.waiting() != "hero" and n < 40:
        if s.waiting() == "bot":
            s.step_bot()
        else:
            break
        n += 1
    if s.waiting() != "hero":
        pytest.skip("hero not to act in this seed")
    before = len(coach_on)
    s.coach()
    time.sleep(0.05)
    # no pre-hint calls when gated off
    assert len(coach_on) == before


def test_pre_hint_on_calls_llm(coach_on, monkeypatch):
    monkeypatch.setattr(llm_coach, "pre_hint_enabled", lambda mode=None: True)
    monkeypatch.setattr(llm_coach, "coach_enabled", lambda: True)
    s = LiveSession(seed=22)
    s.new_hand()
    n = 0
    while s.waiting() != "hero" and n < 40:
        if s.waiting() == "bot":
            s.step_bot()
        else:
            break
        n += 1
    if s.waiting() != "hero":
        pytest.skip("hero not to act")
    s.coach()
    for _ in range(50):
        if s.llm_comment:
            break
        time.sleep(0.02)
    assert s.llm_comment
    assert "MOCK_HINT" in s.llm_comment


def test_coach_settings_roundtrip():
    save_settings({"coach_enabled": False, "coach_pre_hint": True})
    info = public_settings()
    assert info["coach_enabled"] is False
    assert info["coach_pre_hint"] is True
    save_settings({"coach_enabled": True, "coach_pre_hint": False})
    info = public_settings()
    assert info["coach_enabled"] is True
    assert info["coach_pre_hint"] is False


def test_review_detail_endpoint_shape(coach_on):
    s = LiveSession(seed=23)
    s.new_hand()
    _play_to_over(s)
    for _ in range(50):
        if not s.llm_review_busy:
            break
        time.sleep(0.02)
    text = s.request_review_detail()
    assert text
    assert "MOCK_REVIEW" in text


def test_never_auto_acts_hero(coach_on):
    s = LiveSession(seed=24)
    s.new_hand()
    before = len(s.st.action_log)
    # coaching helpers must not push hero actions
    s.coach()
    time.sleep(0.05)
    assert len(s.st.action_log) == before

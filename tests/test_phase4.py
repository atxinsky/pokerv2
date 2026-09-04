"""Phase 4: product modes + usage panel (no network)."""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from pokergym.modes import effective_intensity, normalize_mode, pre_hint_allowed
from pokergym.server import make_server, reset_session
from pokergym.store import lower_intensity, public_settings, save_settings
from pokergym.usage import next_lower_intensity, record, reset_session as reset_usage, snapshot


def test_mode_normalize_and_pre_hint():
    assert normalize_mode("realism") == "realism"
    assert normalize_mode("nope") == "train"
    assert pre_hint_allowed("train", True) is True
    assert pre_hint_allowed("train", False) is False
    assert pre_hint_allowed("realism", True) is False
    assert pre_hint_allowed("realism", False) is False


def test_realism_bumps_intensity():
    assert effective_intensity("low", "train") == "low"
    assert effective_intensity("low", "realism") == "med"
    assert effective_intensity("med", "realism") == "high"
    assert effective_intensity("high", "realism") == "full"
    assert effective_intensity("full", "realism") == "full"


def test_usage_record_and_estimate():
    reset_usage()
    before = snapshot()
    assert before["session_total_tokens"] == 0
    record(1000, 500)
    mid = snapshot()
    assert mid["session_prompt_tokens"] == 1000
    assert mid["session_completion_tokens"] == 500
    assert mid["session_total_tokens"] == 1500
    assert mid["session_calls"] == 1
    assert mid["est_usd"] >= 0
    reset_usage()
    after = snapshot()
    assert after["session_total_tokens"] == 0
    assert after["total_tokens"] >= 1500  # lifetime not cleared


def test_lower_intensity_steps(monkeypatch, tmp_path):
    monkeypatch.setenv("POKERGYM_DB", str(tmp_path / "u.sqlite"))
    save_settings({"llm_brain_intensity": "full"})
    assert next_lower_intensity("full") == "high"
    info = lower_intensity()
    assert info["intensity_changed"] is True
    assert info["llm_brain_intensity"] == "high"
    save_settings({"llm_brain_intensity": "low"})
    info = lower_intensity()
    assert info["intensity_changed"] is False
    assert info["llm_brain_intensity"] == "low"


def test_product_mode_in_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("POKERGYM_DB", str(tmp_path / "m.sqlite"))
    save_settings({"product_mode": "realism", "coach_pre_hint": True})
    info = public_settings()
    assert info["product_mode"] == "realism"
    assert "usage" in info
    from pokergym.llm_coach import pre_hint_enabled

    assert pre_hint_enabled(mode="realism") is False


def test_state_exposes_usage_and_mode_info():
    from pokergym.live import LiveSession
    from pokergym.serialize import dump_state

    s = LiveSession(seed=41, mode="realism")
    s.new_hand()
    data = dump_state(s)
    assert "usage" in data
    assert "mode_info" in data
    assert data["mode"] == "realism"
    assert data["mode_info"]["mode"] == "realism"
    assert data["mode_info"]["pre_hint_effective"] is False


def test_usage_lower_api(monkeypatch, tmp_path):
    monkeypatch.setenv("POKERGYM_DB", str(tmp_path / "api.sqlite"))
    save_settings({"llm_brain_intensity": "full"})
    reset_session(seed=1, mode="train")
    httpd = make_server("127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    port = httpd.server_address[1]
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/usage/lower",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            body = json.loads(r.read().decode())
        assert body["llm_brain_intensity"] == "high"
        assert body.get("intensity_changed") is True
    finally:
        httpd.shutdown()


def test_seat_uses_llm_realism_bump(monkeypatch):
    from pokergym import llm_brain

    monkeypatch.setattr(llm_brain, "brain_enabled", lambda: True)

    def bi(mode=None):
        base = "low"
        return effective_intensity(base, mode) if mode else base

    monkeypatch.setattr(llm_brain, "brain_intensity", bi)
    # train low → 2 seats (1,2); realism bumps to med → ~4 seats (1..4)
    assert llm_brain.seat_uses_llm(1, 0, 8, mode="train") is True
    assert llm_brain.seat_uses_llm(3, 0, 8, mode="train") is False
    assert llm_brain.seat_uses_llm(3, 0, 8, mode="realism") is True

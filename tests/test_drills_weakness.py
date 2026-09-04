"""Weakness-targeted drill: theme packs, mining, session entry (no live DeepSeek)."""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from pokergym.drills import (
    THEME_PACKS,
    apply_theme_setup,
    build_drill_session,
    get_theme,
    list_themes,
    mine_weaknesses,
    select_drill_focus,
    weakness_report,
)
from pokergym.live import LiveSession
from pokergym.serialize import dump_state
from pokergym.server import make_server, reset_session


def test_theme_catalog_nonempty():
    themes = list_themes()
    assert len(themes) >= 5
    ids = {t["id"] for t in themes}
    assert "cbet" in ids
    assert "overfold_3bet" in ids
    assert "river_bluff_catch" in ids
    for t in themes:
        assert t["label"] and t["focus"]


def test_mine_from_tags_and_llm_review():
    hands = [
        {"tags": ["overfold_3bet"], "llm_review": None, "review": {"notes": ["面对 3bet 弃了 QQ"]}},
        {"tags": ["overfold_3bet", "overfold_river"], "llm_review": "河牌过弃太狠，有摊牌价值"},
        {"tags": ["calling_station"], "review": {"summary": "空气跟注"}},
    ]
    ranked = mine_weaknesses(hands)
    assert ranked[0]["score"] > 0
    top_ids = [r["id"] for r in ranked if r["score"] > 0]
    assert "overfold_3bet" in top_ids
    assert ranked[0]["id"] in THEME_PACKS


def test_select_explicit_theme_no_llm():
    focus = select_drill_focus("river_bluff_catch", use_llm=False)
    assert focus["id"] == "river_bluff_catch"
    assert focus["source"] == "requested"


def test_select_mined_without_llm():
    hands = [{"tags": ["underopen", "underopen"], "llm_review": "该开却弃"}]
    focus = select_drill_focus(None, hands=hands, use_llm=False)
    assert focus["id"] == "underopen"
    assert focus["source"] == "mined"


def test_select_static_fallback_empty_archive():
    focus = select_drill_focus(None, hands=[], use_llm=False)
    assert focus["id"] in THEME_PACKS
    assert focus["source"] == "static"


def test_llm_picker_mocked(monkeypatch):
    import pokergym.drills as drills

    monkeypatch.setattr(drills, "_pick_theme_llm", lambda candidates: "cbet")
    hands = [{"tags": ["overfold_3bet"], "llm_review": "3bet"}]
    focus = select_drill_focus(None, hands=hands, use_llm=True)
    assert focus["id"] == "cbet"
    assert focus["source"] == "llm"


def test_llm_picker_unavailable_falls_back(monkeypatch):
    import pokergym.deepseek as ds
    import pokergym.drills as drills

    monkeypatch.setattr(ds, "available", lambda: False)

    def boom(*a, **k):
        raise AssertionError("chat_json should not be called")

    monkeypatch.setattr(ds, "chat_json", boom)
    hands = [{"tags": ["no_iso"], "llm_review": "limp iso"}]
    focus = select_drill_focus(None, hands=hands, use_llm=True)
    assert focus["id"] == "no_iso"
    assert focus["source"] == "mined"


def test_build_drill_session_sets_drill():
    sess, focus = build_drill_session(
        theme_id="cbet", seed=42, mode="train", use_llm=False, wait_llm=False
    )
    assert sess.drill is not None
    assert sess.drill["active"] is True
    assert sess.drill["id"] == "cbet"
    assert focus["id"] == "cbet"
    assert sess.hand_open
    data = dump_state(sess)
    assert data["drill"]["id"] == "cbet"
    assert data["drill"]["active"] is True


def test_apply_theme_biases_bots():
    sess = LiveSession(seed=3, mode="train", wait_llm=False)
    theme = get_theme("overfold_3bet")
    apply_theme_setup(sess, theme)
    prefer = set(THEME_PACKS["overfold_3bet"]["bot_prefer"])
    arch = {b.archetype for b in sess.bots.values()}
    assert arch & prefer
    assert sess.drill["id"] == "overfold_3bet"


def test_weakness_report_shape():
    rep = weakness_report(use_llm=False)
    assert "themes" in rep and "ranked" in rep and "focus" in rep
    assert isinstance(rep["has_signal"], bool)


def test_api_weaknesses_and_drill(monkeypatch, tmp_path):
    monkeypatch.setenv("POKERGYM_DB", str(tmp_path / "drill.sqlite"))
    reset_session(seed=1, mode="train")
    httpd = make_server("127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    port = httpd.server_address[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/weaknesses", timeout=5) as r:
            body = json.loads(r.read().decode())
        assert "themes" in body
        assert any(x["id"] == "cbet" for x in body["themes"])

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/drill",
            data=json.dumps({"theme": "overfold_3bet", "seed": 99, "mode": "train"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            state = json.loads(r.read().decode())
        assert state["drill"]["id"] == "overfold_3bet"
        assert state["drill"]["active"] is True
        assert state["waiting"] in ("hero", "bot", "over")
    finally:
        httpd.shutdown()


def test_normal_new_clears_drill():
    reset_session(seed=5, mode="train", theme="cbet", auto_weakness=True)
    from pokergym.server import get_session

    assert get_session().drill and get_session().drill["active"]
    reset_session(seed=6, mode="train")
    assert get_session().drill is None
    data = dump_state(get_session())
    assert data.get("drill") is None

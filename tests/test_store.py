from pokergym.store import get_setting, list_hands, public_settings, save_settings, set_setting


def test_settings_roundtrip():
    save_settings(
        {
            "llm_enabled": False,
            "deepseek_key": "sk-test1234abcd",
            "deepseek_model": "deepseek-chat",
            "llm_brain": True,
            "llm_brain_intensity": "med",
            "llm_brain_timeout": 8,
        }
    )
    info = public_settings()
    assert info["has_key"] is True
    assert info["deepseek_key_masked"].endswith("abcd")
    assert "*" in info["deepseek_key_masked"]
    assert info["llm_enabled"] is False
    assert info["llm_brain"] is True
    assert info["llm_brain_intensity"] == "med"
    assert info["llm_brain_timeout"] == 8.0
    assert get_setting("deepseek_key") == "sk-test1234abcd"


def test_brain_defaults_on_when_key(monkeypatch, tmp_path):
    """未显式写 llm_brain 时：有 Key → 默认开。"""
    import os

    from pokergym import store

    db = tmp_path / "t.sqlite"
    monkeypatch.setenv("POKERGYM_DB", str(db))
    # 清掉模块级可能缓存的路径影响：直接写 key
    store.set_setting("deepseek_key", "sk-abcxyz9999")
    # 不写 llm_brain
    info = store.public_settings()
    assert info["has_key"] is True
    assert info["llm_brain"] is True
    store.apply_env()
    assert os.environ.get("POKERGYM_LLM_BRAIN") == "1"


def test_hands_empty_ok():
    assert isinstance(list_hands(5), list)

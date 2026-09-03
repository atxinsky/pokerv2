from pokergym.store import get_setting, list_hands, public_settings, save_settings, set_setting


def test_settings_roundtrip():
    save_settings(
        {
            "llm_enabled": False,
            "deepseek_key": "sk-test1234abcd",
            "deepseek_model": "deepseek-chat",
        }
    )
    info = public_settings()
    assert info["has_key"] is True
    assert info["deepseek_key_masked"].endswith("abcd")
    assert "*" in info["deepseek_key_masked"]
    assert info["llm_enabled"] is False
    assert get_setting("deepseek_key") == "sk-test1234abcd"


def test_hands_empty_ok():
    assert isinstance(list_hands(5), list)

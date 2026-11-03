from scripts.set_openai_key import write_key
import pytest


def test_local_key_replaces_only_api_key(tmp_path):
    path = tmp_path / ".env"
    path.write_text("BOT_TOKEN=unchanged\nOPENAI_API_KEY=old\nYOOKASSA_SHOP_ID=1363172\n", encoding="utf-8")
    write_key(path, "sk-test_not_a_real_key_12345")
    assert path.read_text(encoding="utf-8") == (
        "BOT_TOKEN=unchanged\nOPENAI_API_KEY=sk-test_not_a_real_key_12345\nYOOKASSA_SHOP_ID=1363172\n")


def test_invalid_key_never_overwrites_existing_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("BOT_TOKEN=unchanged\n",encoding="utf-8")
    with pytest.raises(ValueError):
        write_key(path,"bad key")
    assert path.read_text(encoding="utf-8") == "BOT_TOKEN=unchanged\n"

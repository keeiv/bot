"""加密金鑰必須能跨程序重啟使用，且不可靜默替換舊金鑰。"""

import json
import os

from cryptography.fernet import Fernet
from dotenv import dotenv_values
import pytest

from src.services import genshin_service


@pytest.fixture
def key_files(tmp_path, monkeypatch):
    # Redirect the module-derived .env path too, never touch the real secrets file.
    monkeypatch.setattr(
        genshin_service, "__file__", str(tmp_path / "src/services/genshin_service.py")
    )
    accounts = tmp_path / "accounts.json"
    monkeypatch.setattr(genshin_service, "_DATA_FILE", str(accounts))
    monkeypatch.delenv("GENSHIN_ENCRYPTION_KEY", raising=False)
    return tmp_path / ".env", accounts


def test_first_boot_without_env_preserves_cookie_after_restart(key_files, monkeypatch):
    env_path, _ = key_files
    first = genshin_service.GenshinService()
    cookie = "ltoken=example; ltuid=123;"
    ciphertext = first.encrypt_cookie(cookie)
    first._accounts = {"123": {"encrypted_cookie": ciphertext}}
    first._save_accounts()

    assert env_path.exists(), "Encryption must not use a volatile key"
    saved_key = dotenv_values(env_path)["GENSHIN_ENCRYPTION_KEY"]
    assert saved_key == first._key.decode()
    monkeypatch.delenv("GENSHIN_ENCRYPTION_KEY")
    restarted = genshin_service.GenshinService()
    assert restarted.decrypt_cookie(ciphertext) == cookie


def test_existing_file_key_reused_without_rewriting_env(key_files):
    env_path, _ = key_files
    key = Fernet.generate_key()
    content = "# existing configuration\nDISCORD_TOKEN=placeholder\n"
    content += f"export GENSHIN_ENCRYPTION_KEY='{key.decode()}'\n"
    env_path.write_text(content, encoding="utf-8")
    original_bytes = env_path.read_bytes()
    ciphertext = Fernet(key).encrypt(b"existing-cookie").decode()

    service = genshin_service.GenshinService()

    assert service.decrypt_cookie(ciphertext) == "existing-cookie"
    assert env_path.read_bytes() == original_bytes


def test_missing_key_with_existing_accounts_cannot_generate_replacement(key_files):
    env_path, accounts = key_files
    ciphertext = Fernet(Fernet.generate_key()).encrypt(b"existing-cookie").decode()
    original = json.dumps({"123": {"encrypted_cookie": ciphertext}})
    accounts.write_text(original, encoding="utf-8")

    with pytest.raises(RuntimeError, match="GENSHIN_ENCRYPTION_KEY"):
        genshin_service.GenshinService()

    assert accounts.read_text(encoding="utf-8") == original
    assert not env_path.exists()
    assert "GENSHIN_ENCRYPTION_KEY" not in os.environ


def test_atomic_save_failure_preserves_env_and_does_not_publish_key(
    key_files, monkeypatch
):
    env_path, _ = key_files
    original = "# keep configuration\nDISCORD_TOKEN=placeholder\n"
    env_path.write_text(original, encoding="utf-8")
    original_bytes = env_path.read_bytes()

    def fail_replace(source, target):
        raise PermissionError("simulated disk permission error")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(RuntimeError, match="無法保存 GENSHIN_ENCRYPTION_KEY"):
        genshin_service.GenshinService()

    assert env_path.read_bytes() == original_bytes
    assert "GENSHIN_ENCRYPTION_KEY" not in os.environ
    assert not list(env_path.parent.glob(".tmp_*"))


def test_new_key_preserves_other_env_settings(key_files):
    env_path, _ = key_files
    # Missing trailing newline must not merge the key with another setting.
    original = "# settings\nDISCORD_TOKEN='placeholder'\nOTHER_SETTING=value"
    env_path.write_text(original, encoding="utf-8")

    service = genshin_service.GenshinService()

    saved = dotenv_values(env_path)
    assert saved["DISCORD_TOKEN"] == "placeholder"
    assert saved["OTHER_SETTING"] == "value"
    assert saved["GENSHIN_ENCRYPTION_KEY"] == service._key.decode()
    assert env_path.read_text(encoding="utf-8").startswith(original)


def test_invalid_saved_key_is_not_replaced(key_files):
    env_path, _ = key_files
    env_path.write_text("GENSHIN_ENCRYPTION_KEY=invalid\n", encoding="utf-8")
    original_bytes = env_path.read_bytes()

    with pytest.raises(ValueError):
        genshin_service.GenshinService()

    assert env_path.read_bytes() == original_bytes
    assert "GENSHIN_ENCRYPTION_KEY" not in os.environ


def test_environment_key_keeps_existing_configuration(key_files, monkeypatch):
    env_path, _ = key_files
    env_path.write_text("OTHER_SETTING=value\n", encoding="utf-8")
    original_bytes = env_path.read_bytes()
    key = Fernet.generate_key()
    monkeypatch.setenv("GENSHIN_ENCRYPTION_KEY", key.decode())

    service = genshin_service.GenshinService()

    assert service._key == key
    assert env_path.read_bytes() == original_bytes


@pytest.mark.parametrize("data", ["broken json", "[]", '"unexpected"', "null"])
def test_uncertain_accounts_cannot_trigger_key_regeneration(key_files, data):
    env_path, accounts = key_files
    accounts.write_text(data, encoding="utf-8")

    with pytest.raises(RuntimeError, match="GENSHIN_ENCRYPTION_KEY"):
        genshin_service.GenshinService()

    assert accounts.read_text(encoding="utf-8") == data
    assert not env_path.exists()
    assert "GENSHIN_ENCRYPTION_KEY" not in os.environ

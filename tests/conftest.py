"""所有測試使用臨時資料與金鑰，禁止連線到正式服務。"""

import base64
import os
import socket

import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["GENSHIN_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()
for credential in (
    "DISCORD_TOKEN", "BLACKLIST_API_KEY", "OSU_CLIENT_ID", "OSU_CLIENT_SECRET",
    "GITHUB_TOKEN", "API_KEY",
):
    os.environ.pop(credential, None)


@pytest.fixture(autouse=True)
def isolate_services(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def local_only(original):
        def connect(sock, address):
            if isinstance(address, tuple) and address[0] not in (
                "localhost", "127.0.0.1", "::1",
            ):
                raise RuntimeError("Tests cannot connect to external services")
            return original(sock, address)
        return connect

    monkeypatch.setattr(socket.socket, "connect", local_only(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", local_only(original_connect_ex))

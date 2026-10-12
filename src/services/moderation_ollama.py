"""A small Ollama client, and what the worker needs to get Ollama ready.

Only the local server (``127.0.0.1``) is ever contacted. Installing Ollama and
pulling models are the worker's start-up steps; they report progress through
callbacks so the terminal screen can draw them.
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.request

import aiohttp

BASE_URL = "http://127.0.0.1:11434"
# The official download. Windows' own signature check decides if it is trusted.
INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"  # nosec B310
INSTALL_SECONDS = 900


class OllamaError(Exception):
    """Ollama did not answer, or answered with something unusable."""


class Ollama:
    def __init__(self, base_url=BASE_URL):
        if not base_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("只允許連線本機的 Ollama")
        self.base_url = base_url.rstrip("/")
        self._session = None

    def _client(self):
        if self._session is None or self._session.closed:
            # trust_env=False: never route model traffic through a proxy.
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None, connect=5), trust_env=False
            )
        return self._session

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _json(self, method, path, body=None, seconds=10):
        try:
            async with self._client().request(
                method,
                self.base_url + path,
                json=body,
                timeout=aiohttp.ClientTimeout(total=seconds, connect=5),
            ) as response:
                if response.status != 200:
                    raise OllamaError(f"Ollama 回應 {response.status}")
                return await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            raise OllamaError("無法連線 Ollama") from error

    async def version(self):
        data = await self._json("GET", "/api/version")
        return str(data.get("version", "")) if isinstance(data, dict) else ""

    async def models(self):
        """Names of the models that are downloaded."""
        data = await self._json("GET", "/api/tags")
        found = data.get("models") if isinstance(data, dict) else None
        if not isinstance(found, list):
            raise OllamaError("Ollama 模型清單格式無效")
        return {m["name"] for m in found if isinstance(m, dict) and "name" in m}

    async def chat(self, model, system, prompt, images, *, think, seconds, tokens):
        """One non-streaming chat turn; returns the reply text."""
        body = {
            "model": model,
            "stream": False,
            "think": think,
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": tokens},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt, "images": images},
            ],
        }
        data = await self._json("POST", "/api/chat", body, seconds)
        message = data.get("message") if isinstance(data, dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaError("Ollama 回覆格式無效")
        return message["content"]

    async def pull(self, model, on_progress):
        """Download ``model``; ``on_progress(status, done, total)`` is called often."""
        try:
            async with self._client().post(
                self.base_url + "/api/pull",
                json={"model": model, "stream": True},
                timeout=aiohttp.ClientTimeout(total=None, connect=5, sock_read=300),
            ) as response:
                if response.status != 200:
                    raise OllamaError(f"Ollama 回應 {response.status}")
                async for line in response.content:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise OllamaError("模型下載失敗")
                    on_progress(
                        str(event.get("status", "")),
                        int(event.get("completed") or 0),
                        int(event.get("total") or 0),
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as error:
            raise OllamaError("模型下載中斷") from error


# ── installing and starting Ollama ────────────────────────────────
def find_ollama(which=shutil.which, environ=None):
    """The path of ``ollama.exe`` if it is installed."""
    environ = os.environ if environ is None else environ
    found = which("ollama")
    if found:
        return found
    for base in (environ.get("LOCALAPPDATA"), environ.get("ProgramFiles")):
        if base:
            for parts in (("Programs", "Ollama"), ("Ollama",)):
                path = Path(base).joinpath(*parts, "ollama.exe")
                if path.is_file():
                    return str(path)
    return None


def install_ollama(on_step, *, run=subprocess.run, which=shutil.which, download=None):
    """Install Ollama with winget, or from the official installer if winget is missing.

    The downloaded installer must carry a valid Windows signature before it is
    run; the signer is reported on screen so it can be read.
    """
    if which("winget"):
        on_step("使用 winget 安裝 Ollama")
        result = run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                "Ollama.Ollama",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=INSTALL_SECONDS,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        on_step("winget 沒有成功，改用官方安裝程式")
    with tempfile.TemporaryDirectory(prefix="ollama-setup-") as directory:
        installer = Path(directory) / "OllamaSetup.exe"
        on_step("下載官方安裝程式")
        (download or _download)(INSTALLER_URL, installer)
        signature = run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$s = Get-AuthenticodeSignature -LiteralPath $env:OLLAMA_SETUP;"
                "if ($s.Status -ne 'Valid') { exit 1 };"
                "Write-Output $s.SignerCertificate.Subject",
            ],
            env={**os.environ, "OLLAMA_SETUP": str(installer)},
            capture_output=True,
            text=True,
            timeout=60,
        )
        if signature.returncode != 0:
            raise OllamaError("安裝程式的數位簽章無效，已中止")
        on_step("簽章有效：" + (signature.stdout or "").strip()[:80])
        on_step("安裝 Ollama")
        result = run(
            [str(installer), "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"],
            timeout=INSTALL_SECONDS,
        )
        if result.returncode != 0:
            raise OllamaError("Ollama 安裝失敗")


def _download(url, destination):
    with (
        urllib.request.urlopen(url, timeout=60) as response,  # nosec B310
        Path(destination).open("wb") as stream,
    ):
        shutil.copyfileobj(response, stream, 1024 * 1024)


async def start_server(executable, client, *, spawn=subprocess.Popen, seconds=40):
    """Start ``ollama serve`` if nothing answers, and wait until it does."""
    try:
        await client.version()
        return False
    except OllamaError:
        pass
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    spawn(
        [executable, "serve"],
        env={
            **os.environ,
            # One big model at a time suits an old machine; two images share it.
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "OLLAMA_NUM_PARALLEL": "2",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        try:
            await client.version()
            return True
        except OllamaError:
            continue
    raise OllamaError("Ollama 沒有在時間內啟動")

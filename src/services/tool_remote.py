"""Authenticated, pinned-TLS LAN transport and a standalone single-job worker."""

import argparse
import asyncio
import base64
from contextlib import ExitStack
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
import time
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

if __package__:
    from .tool_protocol import CHUNK_BYTES
    from .tool_protocol import disk
    from .tool_protocol import engine_digest
    from .tool_protocol import MAX_TOTAL_BYTES
    from .tool_protocol import REMOTE_SECONDS
    from .tool_protocol import safe_name
    from .tool_protocol import validate_manifest
    from .tool_protocol import validate_result
else:
    from tool_protocol import CHUNK_BYTES
    from tool_protocol import disk
    from tool_protocol import engine_digest
    from tool_protocol import MAX_TOTAL_BYTES
    from tool_protocol import REMOTE_SECONDS
    from tool_protocol import safe_name
    from tool_protocol import validate_manifest
    from tool_protocol import validate_result


def read_config(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("處理節點設定格式無效")
    return data


class RemoteWorker:
    def __init__(self, config):
        endpoint = config["endpoint"]
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or url.username
            or url.password
            or not ipaddress.ip_address(url.hostname).is_private
        ):
            raise ValueError("處理節點必須使用區域網路 HTTPS 位址")
        self.endpoint = endpoint.rstrip("/")
        if not re.fullmatch(r"[0-9a-f]{64}", config["token"]) or not re.fullmatch(
            r"[0-9a-f]{64}", config["fingerprint"]
        ):
            raise ValueError("處理節點授權設定無效")
        self.headers = {"Authorization": "Bearer " + config["token"]}
        self.fingerprint = aiohttp.Fingerprint(bytes.fromhex(config["fingerprint"]))

    @classmethod
    def configured(cls):
        path = Path(os.getenv("FILE_TOOLS_WORKER_CONFIG", ".file-tools-worker.json"))
        if not path.is_file():
            return None
        config = read_config(path)
        if config.get("enabled") is False:
            return None
        if config.get("enabled") is not True:
            raise ValueError("處理節點啟用設定無效")
        return cls(config)

    def session(self, seconds):
        return aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=seconds, connect=5, sock_read=90),
            trust_env=False,
            auto_decompress=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        )

    async def health(self):
        async with self.session(10) as session:
            async with session.get(
                self.endpoint + "/health",
                ssl=self.fingerprint,
                allow_redirects=False,
            ) as response:
                if (
                    response.status != 200
                    or response.content_length is None
                    or response.content_length > 4096
                ):
                    raise ValueError("處理節點無法驗證")
                data = json.loads(await response.read())
                if (
                    data.get("engineDigest") != engine_digest()
                    or data.get("protocol") != 1
                ):
                    raise ValueError("處理節點引擎版本不一致")
                return data

    async def process(self, root, quote, job_id):
        local = json.loads(
            await disk((root / "request.json").read_text, encoding="utf-8")
        )
        paths = [root / entry["stored"] for entry in local["files"]]
        manifest = validate_manifest(
            {
                "jobId": job_id,
                "files": [
                    {"name": entry["name"], "bytes": path.stat().st_size}
                    for entry, path in zip(local["files"], paths)
                ],
                "operation": local["operation"],
                "quality": local["quality"],
                "maxEdge": local["maxEdge"],
                "timeout": quote["timeout"],
                "engineDigest": engine_digest(),
            }
        )
        destination = root / "result.bin"
        try:
            with ExitStack() as files:
                form = aiohttp.FormData()
                form.add_field(
                    "manifest", json.dumps(manifest), content_type="application/json"
                )
                for index, path in enumerate(paths):
                    form.add_field(
                        f"file-{index}",
                        files.enter_context(path.open("rb")),
                        filename="input",
                        content_type="application/octet-stream",
                    )
                async with self.session(REMOTE_SECONDS) as session:
                    async with session.post(
                        self.endpoint + "/process",
                        data=form,
                        ssl=self.fingerprint,
                        allow_redirects=False,
                    ) as response:
                        if response.status != 200:
                            raise ValueError("處理節點未完成工作")
                        encoded = response.headers.get("X-Tool-Result", "")
                        if len(encoded) > 4096:
                            raise ValueError("處理結果資訊超過上限")
                        result = validate_result(
                            json.loads(base64.b64decode(encoded, validate=True)),
                            quote["timeout"],
                        )
                        if response.content_length != result[
                            "bytes"
                        ] or response.headers.get("Content-Encoding"):
                            raise ValueError("處理結果大小無效")
                        digest = hashlib.sha256()
                        total = 0
                        with destination.open("wb") as stream:
                            async for chunk in response.content.iter_chunked(
                                CHUNK_BYTES
                            ):
                                total += len(chunk)
                                if total > result["bytes"]:
                                    raise ValueError("處理結果超過上限")
                                digest.update(chunk)
                                await disk(stream.write, chunk)
                        if (
                            total != result["bytes"]
                            or digest.hexdigest() != result["sha256"]
                        ):
                            raise ValueError("處理結果校驗失敗")
                        return {
                            key: result[key]
                            for key in ("name", "bytes", "seconds", "changed", "engine")
                        }
        except BaseException:
            await disk(destination.unlink, missing_ok=True)
            raise


class WorkerServer:
    def __init__(self, config, python=sys.executable, temp_dir=None):
        self.token = config["token"]
        if not re.fullmatch(r"[0-9a-f]{64}", self.token):
            raise ValueError("處理節點授權設定無效")
        self.allowed = {
            str(ipaddress.ip_address(value)) for value in config["allowedIPs"]
        }
        if not self.allowed:
            raise ValueError("處理節點未設定允許來源")
        self.python = python
        self.temp_dir = temp_dir
        self.busy = False
        self.seen = {}
        self.tasks = set()

    def create_app(self):
        @web.middleware
        async def authorize(request, handler):
            if request.remote not in self.allowed and request.remote != "127.0.0.1":
                raise web.HTTPForbidden()
            expected = "Bearer " + self.token
            if not hmac.compare_digest(
                request.headers.get("Authorization", "").encode(), expected.encode()
            ):
                raise web.HTTPUnauthorized()
            if request.headers.get("Content-Encoding"):
                raise web.HTTPBadRequest()
            return await handler(request)

        app = web.Application(
            client_max_size=MAX_TOTAL_BYTES + 64 * 1024, middlewares=[authorize]
        )
        app.router.add_get("/health", self.health)
        app.router.add_post("/process", self.handle)
        app.on_shutdown.append(self.shutdown)
        return app

    async def health(self, request):
        return web.json_response(
            {
                "protocol": 1,
                "engineDigest": engine_digest(),
                "concurrency": 1,
                "busy": self.busy,
            }
        )

    async def shutdown(self, app):
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def handle(self, request):
        if request.content_type != "multipart/form-data":
            raise web.HTTPBadRequest()
        if self.busy:
            raise web.HTTPServiceUnavailable()
        self.busy = True
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            return await asyncio.wait_for(self.convert(request), REMOTE_SECONDS)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise web.HTTPBadRequest(text="處理請求或檔案內容無效") from None
        except asyncio.TimeoutError:
            raise web.HTTPGatewayTimeout(text="處理工作超時") from None
        finally:
            self.tasks.discard(task)
            self.busy = False

    async def convert(self, request):
        reader = await request.multipart()
        part = await reader.next()
        if not isinstance(part, aiohttp.BodyPartReader) or part.name != "manifest":
            raise ValueError("處理請求格式無效")
        metadata = bytearray()
        while chunk := await part.read_chunk(CHUNK_BYTES):
            metadata.extend(chunk)
            if len(metadata) > 16 * 1024:
                raise ValueError("處理請求超過上限")
        manifest = validate_manifest(json.loads(metadata))
        if manifest["engineDigest"] != engine_digest():
            raise web.HTTPConflict(text="處理節點引擎版本不一致")
        now = time.monotonic()
        self.seen = {key: value for key, value in self.seen.items() if value > now}
        if manifest["jobId"] in self.seen:
            raise web.HTTPConflict(text="處理請求已接收")
        if len(self.seen) >= 256:
            raise web.HTTPServiceUnavailable()
        self.seen[manifest["jobId"]] = now + 300
        with tempfile.TemporaryDirectory(
            prefix="new-bot-remote-", dir=self.temp_dir
        ) as directory:
            root = Path(directory)
            entries = []
            for index, entry in enumerate(manifest["files"]):
                part = await reader.next()
                if (
                    not isinstance(part, aiohttp.BodyPartReader)
                    or part.name != f"file-{index}"
                    or part.headers.get("Content-Encoding")
                    or part.headers.get("Content-Transfer-Encoding")
                ):
                    raise ValueError("檔案傳輸格式無效")
                stored = f"input-{index}{Path(entry['name']).suffix.lower()}"
                received = 0
                with (root / stored).open("wb") as stream:
                    while chunk := await part.read_chunk(CHUNK_BYTES):
                        received += len(chunk)
                        if received > entry["bytes"]:
                            raise ValueError("檔案大小超過宣告上限")
                        await disk(stream.write, chunk)
                if received != entry["bytes"]:
                    raise ValueError("檔案傳輸不完整")
                entries.append({"name": entry["name"], "stored": stored})
            if await reader.next() is not None:
                raise ValueError("批次超過宣告上限")
            local = {key: manifest[key] for key in ("operation", "quality", "maxEdge")}
            local["files"] = entries
            await disk(
                (root / "request.json").write_text, json.dumps(local), encoding="utf-8"
            )
            flags = {"creationflags": 0x08004000} if os.name == "nt" else {}
            process = await asyncio.create_subprocess_exec(
                self.python,
                str(Path(__file__).with_name("tool_worker.py")),
                str(root),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                **flags,
            )
            try:
                await asyncio.wait_for(process.wait(), manifest["timeout"])
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            if process.returncode != 0:
                raise ValueError("檔案處理失敗")
            result = json.loads(
                await disk((root / "result.json").read_text, encoding="utf-8")
            )
            result["name"] = safe_name(result["name"])
            result["engineDigest"] = engine_digest()
            digest = hashlib.sha256()
            with (root / "result.bin").open("rb") as stream:
                while chunk := await disk(stream.read, CHUNK_BYTES):
                    digest.update(chunk)
            result["sha256"] = digest.hexdigest()
            validate_result(result, manifest["timeout"])
            response = web.StreamResponse(
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(result["bytes"]),
                    "X-Tool-Result": base64.b64encode(
                        json.dumps(result).encode()
                    ).decode(),
                    "Cache-Control": "no-store",
                }
            )
            await response.prepare(request)
            with (root / "result.bin").open("rb") as stream:
                while chunk := await disk(stream.read, CHUNK_BYTES):
                    await response.write(chunk)
            await response.write_eof()
            return response


def main():
    parser = argparse.ArgumentParser(description="NovaGrid LAN worker")
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("worker.json")
    )
    arguments = parser.parse_args()
    config = read_config(arguments.config)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    root = arguments.config.parent
    context.load_cert_chain(root / "worker-cert.pem", root / "worker-key.pem")
    worker = WorkerServer(config)
    print(f"[NovaGrid] HTTPS {config['host']}:{config['port']} · 同時處理上限 1")
    web.run_app(
        worker.create_app(),
        host=config["host"],
        port=config["port"],
        ssl_context=context,
        access_log=None,
        print=None,
        handler_cancellation=True,
        shutdown_timeout=5,
    )


if __name__ == "__main__":
    main()

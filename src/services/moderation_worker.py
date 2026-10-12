"""The image-review worker: an authenticated LAN server in front of local Ollama.

The bot sends one or two images; the worker runs each through the three review
stages and answers with a verdict per image. Images stay in memory (nothing is
written to disk) and are dropped when the request ends. This file is meant to
run on the second computer, from the portable package built by
``python -m src.moderation_worker_setup build``.
"""

import argparse
import asyncio
import hmac
import ipaddress
import json
from pathlib import Path
import re
import ssl
import sys
import time

import aiohttp
from aiohttp import web

if __package__:
    from . import moderation_protocol as protocol
    from .moderation_engine import review_image
    from .moderation_ollama import find_ollama
    from .moderation_ollama import install_ollama
    from .moderation_ollama import Ollama
    from .moderation_ollama import OllamaError
    from .moderation_ollama import start_server
    from .moderation_tui import Dashboard
    from .moderation_tui import FAIL
    from .moderation_tui import OK
    from .moderation_tui import RUNNING
else:
    from moderation_engine import review_image
    from moderation_ollama import find_ollama
    from moderation_ollama import install_ollama
    from moderation_ollama import Ollama
    from moderation_ollama import OllamaError
    from moderation_ollama import start_server
    import moderation_protocol as protocol
    from moderation_tui import Dashboard
    from moderation_tui import FAIL
    from moderation_tui import OK
    from moderation_tui import RUNNING

CHUNK = 64 * 1024
RETRY_SECONDS = 30


def read_config(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("審核節點設定格式無效")
    return data


class ReviewServer:
    def __init__(self, config, ollama, dashboard=None, *, prepare_on_start=True):
        self.token = config["token"]
        if not re.fullmatch(r"[0-9a-f]{64}", self.token):
            raise ValueError("審核節點授權設定無效")
        self.allowed = {str(ipaddress.ip_address(v)) for v in config["allowedIPs"]}
        if not self.allowed:
            raise ValueError("審核節點未設定允許來源")
        self.stages = protocol.stage_config(config.get("models"))
        self.ollama = ollama
        self.dashboard = dashboard or Dashboard(self.stages)
        self.prepare_on_start = prepare_on_start
        self.ready = False
        self.free = list(range(protocol.MAX_IMAGES))  # review slots not in use
        self.seen = {}
        self.tasks = set()

    # ── web app ───────────────────────────────────────────────────
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
            client_max_size=protocol.MAX_IMAGES * protocol.MAX_IMAGE_BYTES + 64 * 1024,
            middlewares=[authorize],
        )
        app.router.add_get("/health", self.health)
        app.router.add_post("/review", self.handle)
        app.on_startup.append(self.startup)
        app.on_shutdown.append(self.shutdown)
        return app

    async def startup(self, app):
        if self.prepare_on_start:
            self.tasks.add(asyncio.create_task(self.prepare()))

    async def shutdown(self, app):
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        await self.ollama.close()

    async def models_present(self):
        have = await self.ollama.models()
        return {s["stage"]: s["model"] in have for s in self.stages}

    async def health(self, request):
        ollama, models = False, {s["stage"]: False for s in self.stages}
        try:
            models = await self.models_present()
            ollama = True
        except OllamaError:
            pass
        return web.json_response(
            {
                "protocol": protocol.PROTOCOL,
                "engineDigest": protocol.engine_digest(),
                "slots": len(self.free),
                "ollama": ollama,
                "ready": self.ready and ollama and all(models.values()),
                "models": {str(k): v for k, v in models.items()},
            }
        )

    # ── review ────────────────────────────────────────────────────
    async def handle(self, request):
        if request.content_type != "multipart/form-data":
            raise web.HTTPBadRequest()
        if not self.ready:
            raise web.HTTPServiceUnavailable(text="審核節點還在準備")
        try:
            manifest, images = await self.receive(request)
            if len(self.free) < len(images):
                raise web.HTTPServiceUnavailable(text="審核槽已滿")
            slots = [self.free.pop(0) for _ in images]
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise web.HTTPBadRequest(text="審核請求或圖片無效") from None
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *(
                        self.review_one(slot, i, entry, data)
                        for i, (slot, entry, data) in enumerate(
                            zip(slots, manifest["files"], images)
                        )
                    )
                ),
                protocol.REVIEW_SECONDS + 30,
            )
        except asyncio.TimeoutError:
            raise web.HTTPGatewayTimeout(text="審核超時") from None
        finally:
            self.tasks.discard(task)
            self.free.extend(slots)
            self.free.sort()
        return web.json_response(
            {"results": list(results), "engineDigest": protocol.engine_digest()},
            headers={"Cache-Control": "no-store"},
        )

    async def review_one(self, slot, index, entry, data):
        self.dashboard.emit("begin", slot=slot, name=entry["name"], bytes=len(data))

        def emit(kind, **details):
            self.dashboard.emit(kind, **{**details, "slot": slot})

        try:
            result = await review_image(self.ollama, self.stages, index, data, emit)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Whatever went wrong, the bot must hear "unavailable", never a guess.
            result = {
                "index": index,
                "verdict": protocol.UNAVAILABLE,
                "stage": 0,
                "categories": [],
                "reason": "審核發生錯誤",
                "stages": [],
            }
        self.dashboard.emit("end", slot=slot, result=result)
        return result

    async def receive(self, request):
        reader = await request.multipart()
        part = await reader.next()
        if not isinstance(part, aiohttp.BodyPartReader) or part.name != "manifest":
            raise ValueError("審核請求格式無效")
        metadata = bytearray()
        while chunk := await part.read_chunk(CHUNK):
            metadata.extend(chunk)
            if len(metadata) > 16 * 1024:
                raise ValueError("審核請求超過上限")
        manifest = protocol.validate_manifest(json.loads(metadata))
        if manifest["engineDigest"] != protocol.engine_digest():
            raise web.HTTPConflict(text="審核節點引擎版本不一致")
        now = time.monotonic()
        self.seen = {k: v for k, v in self.seen.items() if v > now}
        if manifest["jobId"] in self.seen:
            raise web.HTTPConflict(text="審核請求已接收")
        if len(self.seen) >= 256:
            raise web.HTTPServiceUnavailable()
        self.seen[manifest["jobId"]] = now + protocol.REVIEW_SECONDS + 60
        images = []
        for index, entry in enumerate(manifest["files"]):
            part = await reader.next()
            if (
                not isinstance(part, aiohttp.BodyPartReader)
                or part.name != f"file-{index}"
                or part.headers.get("Content-Encoding")
                or part.headers.get("Content-Transfer-Encoding")
            ):
                raise ValueError("圖片傳輸格式無效")
            data = bytearray()
            while chunk := await part.read_chunk(CHUNK):
                data.extend(chunk)
                if len(data) > entry["bytes"]:
                    raise ValueError("圖片大小超過宣告上限")
            if len(data) != entry["bytes"]:
                raise ValueError("圖片傳輸不完整")
            images.append(bytes(data))
        if await reader.next() is not None:
            raise ValueError("圖片數量超過宣告上限")
        return manifest, images

    # ── start-up: Ollama, then the three models ───────────────────
    async def prepare(self):
        """Get Ollama and all three models ready, retrying until it works."""
        while not self.ready:
            try:
                await self.bootstrap()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.dashboard.set_ready(False)
                self.dashboard.step(
                    "稍後重試",
                    FAIL,
                    f"{type(error).__name__}；{RETRY_SECONDS} 秒後再試",
                )
                await asyncio.sleep(RETRY_SECONDS)
        while True:  # keep the header honest afterwards
            await asyncio.sleep(10)
            try:
                present = await self.models_present()
                self.dashboard.ollama = True
                self.dashboard.models = present
            except OllamaError:
                self.dashboard.ollama = False

    async def bootstrap(
        self, *, find=find_ollama, install=install_ollama, start=start_server
    ):
        board = self.dashboard
        board.step("Ollama", RUNNING, "檢查是否已安裝")
        executable = await asyncio.to_thread(find)
        if executable is None:
            await asyncio.to_thread(
                install, lambda detail: board.step("Ollama", RUNNING, detail)
            )
            executable = await asyncio.to_thread(find)
            if executable is None:
                raise OllamaError("安裝後仍找不到 Ollama")
        board.step("Ollama", RUNNING, "啟動服務")
        await start(executable, self.ollama)
        board.ollama = True
        board.step("Ollama", OK, executable)
        have = await self.ollama.models()
        for stage in self.stages:
            label = f"模型 {stage['stage']} {stage['label']}"
            model = stage["model"]
            if model not in have:
                board.step(label, RUNNING, f"{model}　下載中", 0.0)

                def progress(status, done, total, label=label, model=model):
                    fraction = done / total if total else None
                    board.step(label, RUNNING, f"{model}　{status}", fraction)

                await self.ollama.pull(model, progress)
                have = await self.ollama.models()
                if model not in have:
                    raise OllamaError("模型下載後仍不存在")
            board.models[stage["stage"]] = True
            board.step(label, OK, model)
        self.ready = True
        board.set_ready(True)


def main():
    parser = argparse.ArgumentParser(description="BOT. image-review worker")
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("worker.json")
    )
    arguments = parser.parse_args()
    config = read_config(arguments.config)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    root = arguments.config.parent
    context.load_cert_chain(root / "worker-cert.pem", root / "worker-key.pem")
    stages = protocol.stage_config(config.get("models"))
    dashboard = Dashboard(stages, f"{config['host']}:{config['port']}")
    server = ReviewServer(config, Ollama(), dashboard)
    interactive = sys.stdout.isatty()
    dashboard.plain = not interactive
    try:
        if interactive:
            dashboard.__enter__()
        web.run_app(
            server.create_app(),
            host=config["host"],
            port=config["port"],
            ssl_context=context,
            access_log=None,
            print=None,
            handler_cancellation=True,
            shutdown_timeout=5,
        )
    finally:
        if interactive:
            dashboard.__exit__(None, None, None)


if __name__ == "__main__":
    main()

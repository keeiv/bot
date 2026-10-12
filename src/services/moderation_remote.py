"""The bot's side of the image-review worker: pinned-TLS client and the service.

The review has three outcomes. ``approved`` and ``rejected`` come from the
local models on the worker. Everything else (no worker configured, the worker
is off or still preparing, a model failed or timed out, the answer did not
check out) is ``unavailable``, and the caller then falls back to the human
review that existed before. A broken worker can never approve an image.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Optional
import uuid

import aiohttp

from src.services import moderation_protocol as protocol
from src.services.tool_remote import read_config
from src.services.tool_remote import RemoteWorker

logger = logging.getLogger(__name__)

SKIP_SECONDS = 120  # after a failure, go straight to a human for this long
WAIT_SECONDS = 30  # how long an image may wait for one of the two slots


@dataclass(frozen=True)
class Outcome:
    verdict: str  # approved / rejected / unavailable
    stage: int = 0  # the stage that decided (0 when unavailable)
    categories: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""  # for logs and developers, never shown to the requester


UNAVAILABLE = Outcome(protocol.UNAVAILABLE)


class ModerationWorker(RemoteWorker):
    """Same pinned-certificate, bearer-token channel as the file worker."""

    @classmethod
    def configured(cls) -> Optional["ModerationWorker"]:
        path = Path(
            os.getenv("IMAGE_REVIEW_WORKER_CONFIG", ".image-review-worker.json")
        )
        if not path.is_file():
            return None
        config = read_config(path)
        if config.get("enabled") is False:
            return None
        if config.get("enabled") is not True:
            raise ValueError("審核節點啟用設定無效")
        return cls(config)

    def session(self, seconds: float) -> aiohttp.ClientSession:
        # A reply comes only after every stage has run, so reads may be silent
        # for minutes; the overall limit is what bounds the request.
        return aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=seconds, connect=5, sock_read=seconds),
            trust_env=False,
            auto_decompress=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        )

    async def health(self) -> dict[str, Any]:
        async with self.session(10) as session:
            async with session.get(
                self.endpoint + "/health", ssl=self.fingerprint, allow_redirects=False
            ) as response:
                if (
                    response.status != 200
                    or response.content_length is None
                    or response.content_length > 4096
                ):
                    raise ValueError("審核節點無法驗證")
                data = json.loads(await response.read())
                if (
                    data.get("engineDigest") != protocol.engine_digest()
                    or data.get("protocol") != protocol.PROTOCOL
                ):
                    raise ValueError("審核節點引擎版本不一致")
                return data

    async def review(self, images: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
        """Review ``[(name, bytes)]``; returns the validated per-image results."""
        manifest = protocol.validate_manifest(
            {
                "jobId": uuid.uuid4().hex,
                "files": [
                    {"name": protocol.safe_name(name), "bytes": len(data)}
                    for name, data in images
                ],
                "engineDigest": protocol.engine_digest(),
            }
        )
        form = aiohttp.FormData()
        form.add_field(
            "manifest", json.dumps(manifest), content_type="application/json"
        )
        for index, (_, data) in enumerate(images):
            form.add_field(
                f"file-{index}",
                data,
                filename="input",
                content_type="application/octet-stream",
            )
        async with self.session(protocol.REVIEW_SECONDS + 60) as session:
            async with session.post(
                self.endpoint + "/review",
                data=form,
                ssl=self.fingerprint,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise ValueError("審核節點未完成工作")
                body = await response.content.read(64 * 1024 + 1)
                if len(body) > 64 * 1024:
                    raise ValueError("審核結果超過上限")
        return protocol.validate_result(json.loads(body), len(images))["results"]


class ImageReviewService:
    """What the cogs call: ``await service.review(name, bytes)``."""

    def __init__(
        self,
        worker: Optional[Any] = None,
        *,
        configured: Callable[[], Optional[Any]] = ModerationWorker.configured,
    ) -> None:
        self._worker = worker
        self._configured = configured
        self._loaded = worker is not None
        self._slots = asyncio.Semaphore(protocol.MAX_IMAGES)
        self._skip_until = 0.0

    async def _load(self) -> Optional[Any]:
        if not self._loaded:
            self._loaded = True
            try:
                self._worker = await asyncio.to_thread(self._configured)
            except Exception:
                logger.warning("Image-review worker configuration is invalid")
                self._worker = None
        return self._worker

    @property
    def enabled(self) -> bool:
        return self._worker is not None

    async def available(self) -> bool:
        """True when a worker is configured (it may still turn out to be down)."""
        return await self._load() is not None

    async def review(self, name: str, data: bytes) -> Outcome:
        """Judge one image. Never raises; failure is ``unavailable``."""
        worker = await self._load()
        if worker is None or time.monotonic() < self._skip_until:
            return UNAVAILABLE
        try:
            # Two images are judged at a time; a third waits its turn, briefly.
            await asyncio.wait_for(self._slots.acquire(), WAIT_SECONDS)
        except asyncio.TimeoutError:
            return UNAVAILABLE
        try:
            results = await worker.review([(name, data)])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Image-review worker did not answer", exc_info=False)
            self._skip_until = time.monotonic() + SKIP_SECONDS
            return UNAVAILABLE
        finally:
            self._slots.release()
        item = results[0]
        if item["verdict"] == protocol.UNAVAILABLE:
            self._skip_until = time.monotonic() + SKIP_SECONDS // 4
            return UNAVAILABLE
        return Outcome(
            item["verdict"], item["stage"], tuple(item["categories"]), item["reason"]
        )

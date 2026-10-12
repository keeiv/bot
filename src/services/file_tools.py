"""Shared bounded processing pipeline; callers provide authenticated user IDs."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import uuid

from src.services.tool_protocol import REMOTE_SECONDS
from src.services.tool_protocol import safe_name
from src.services.tool_quota import MAX_TOTAL_BYTES
from src.services.tool_quota import ToolQuota
from src.services.tool_remote import RemoteWorker
from src.utils.i18n import text as tx
from src.utils.storage_worker import run_blocking

log = logging.getLogger(__name__)


def cleanup_directory(directory):
    root = Path(directory.name).resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "new-bot-tool-"
    ):
        raise ValueError("Unexpected tool temporary directory")
    directory.cleanup()


class ToolTokens:
    def __init__(self, secret):
        self.secret = secret.encode()

    def issue(self, user_id, purpose, **extra):
        body = dict(
            uid=str(user_id),
            purpose=purpose,
            exp=time.time() + 900,
            nonce=uuid.uuid4().hex,
            **extra,
        )
        payload = (
            base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode()
        )
        signature = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return payload + "." + signature

    def read(self, token, purpose):
        try:
            if len(token) > 12000:
                raise ValueError
            payload, signature = token.rsplit(".", 1)
            expected = hmac.new(
                self.secret, payload.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            data = json.loads(
                base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            )
            if data["exp"] <= time.time() or data["purpose"] != purpose:
                raise ValueError
            return data
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(tx("file_tools.file_authorization_has_expired")) from exc


class FileTools:
    def __init__(self):
        self.quota = None
        self.tasks = {}
        self.results = {}
        self.settlements = {}
        self.directories = {}
        self.slots = asyncio.Semaphore(2)
        self.uploads = asyncio.Semaphore(3)
        self.admission = asyncio.Lock()
        self.cleaner = None
        self.remote = None
        self.tokens = ToolTokens(os.getenv("BOT_API_SECRET") or secrets.token_hex(32))

    async def start(self):
        self.remote = await run_blocking(RemoteWorker.configured)
        if self.remote:
            self.slots = asyncio.Semaphore(1)
        self.quota = await run_blocking(ToolQuota)
        await run_blocking(self.quota.import_history)
        self.cleaner = asyncio.create_task(self._clean())

    async def close(self):
        if self.cleaner:
            self.cleaner.cancel()
            await asyncio.gather(self.cleaner, return_exceptions=True)
        for task in list(self.tasks.values()):
            task.cancel()
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        for directory in list(self.directories.values()):
            await run_blocking(cleanup_directory, directory)
        self.directories.clear()

    async def _clean(self):
        while True:
            await asyncio.sleep(60)
            for job_id in list(self.settlements):
                await self._settle(job_id)
            for job_id, result in list(self.results.items()):
                if result["expiresAt"] < time.time():
                    directory = self.directories.pop(job_id, None)
                    if directory:
                        await run_blocking(cleanup_directory, directory)
                    self.results.pop(job_id, None)
                    self.settlements.pop(job_id, None)

    async def submit(
        self, uid, files, operation, quality=78, max_edge=4096, job_id=None
    ):
        async with self.admission:
            return await self._submit(uid, files, operation, quality, max_edge, job_id)

    async def _submit(self, uid, files, operation, quality, max_edge, job_id):
        if self.quota is None:
            raise ValueError(tx("file_tools.the_file_service_is_not_ready"))
        if len(self.tasks) >= (2 if self.remote else 6) or len(self.directories) >= 32:
            raise ValueError(tx("file_tools.the_processing_queue_is_full_retry"))
        if (
            type(quality) is not int
            or not 40 <= quality <= 95
            or type(max_edge) is not int
            or not 256 <= max_edge <= 8192
        ):
            raise ValueError(tx("file_tools.output_quality_or_dimensions_are_outside"))
        if len(files) > 16 or sum(len(data) for _, data in files) > MAX_TOTAL_BYTES:
            raise ValueError(tx("file_tools.the_batch_exceeds_the_processing_limit"))
        quote = await run_blocking(
            self.quota.quote, uid, [len(data) for _, data in files], operation
        )
        if self.remote:
            quote["remoteDeadline"] = time.monotonic() + 240
        job_id = await run_blocking(self.quota.reserve, uid, quote, job_id)
        try:
            directory = tempfile.TemporaryDirectory(prefix="new-bot-tool-")
            self.directories[job_id] = directory
            root = Path(directory.name)
            entries = []
            for index, (name, data) in enumerate(files):
                name = safe_name(name)
                stored = f"input-{index}{Path(name).suffix.lower()}"
                await run_blocking((root / stored).write_bytes, data)
                entries.append({"name": name, "stored": stored})
            manifest = {
                "files": entries,
                "operation": operation,
                "quality": quality,
                "maxEdge": max_edge,
            }
            await run_blocking(
                (root / "request.json").write_text,
                json.dumps(manifest),
                encoding="utf-8",
            )
            self.results[job_id] = {
                "id": job_id,
                "userId": str(uid),
                "state": "pending",
                "expiresAt": time.time() + 1200,
                "maximumPoints": quote["maximumPoints"],
            }
            task = asyncio.create_task(self._process(uid, job_id, root, quote))
            self.tasks[job_id] = task
            task.add_done_callback(lambda _task: self.tasks.pop(job_id, None))
            return job_id
        except BaseException:
            await run_blocking(self.quota.finish, uid, job_id)
            directory = self.directories.pop(job_id, None)
            if directory:
                await run_blocking(cleanup_directory, directory)
            raise

    async def _process(self, uid, job_id, root, quote):
        process = None
        output = None
        cancelled = False
        try:
            if self.remote:
                remaining = quote["remoteDeadline"] - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError
                output = await asyncio.wait_for(
                    self._remote_process(root, quote, job_id), remaining
                )
                return
            async with self.slots:
                flags = {"creationflags": 0x08000000} if os.name == "nt" else {}
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(Path(__file__).with_name("tool_worker.py")),
                    str(root),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    **flags,
                )
                await asyncio.wait_for(process.wait(), timeout=quote["timeout"])
                if process.returncode != 0:
                    raise ValueError(
                        tx("file_tools.conversion_failed_format_content_or_processing")
                    )
                output = json.loads(
                    await run_blocking(
                        (root / "result.json").read_text, encoding="utf-8"
                    )
                )
        except (Exception, asyncio.CancelledError) as exc:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            cancelled = isinstance(exc, asyncio.CancelledError)
        finally:
            self.settlements[job_id] = (uid, output)
            await self._settle(job_id)
            for path in root.glob("input-*"):
                await run_blocking(path.unlink, missing_ok=True)
            await run_blocking((root / "request.json").unlink, missing_ok=True)
        if cancelled:
            raise asyncio.CancelledError

    async def _remote_process(self, root, quote, job_id):
        async with self.slots:
            return await asyncio.wait_for(
                self.remote.process(root, quote, job_id), REMOTE_SECONDS
            )

    async def _settle(self, job_id):
        """Retry the same outcome after a lost commit acknowledgement, never refund it."""
        uid, output = self.settlements[job_id]
        for attempt in range(3):
            try:
                charge = await run_blocking(
                    self.quota.finish,
                    uid,
                    job_id,
                    output["seconds"] if output else 0,
                    output is not None,
                    output["changed"] if output else True,
                )
                if output:
                    self.results[job_id].update(
                        state="done",
                        points=charge,
                        expiresAt=time.time() + 1200,
                        **output,
                    )
                else:
                    self.results[job_id].update(
                        state="failed",
                        points=0,
                        error=tx("file_tools.file_processing_failed_or_timed_out"),
                    )
                self.settlements.pop(job_id, None)
                return
            except Exception:
                if attempt == 2:
                    log.exception("Tool settlement awaiting retry: %s", job_id)
        self.results[job_id].update(
            state="settling",
            error=tx("file_tools.usage_records_are_being_verified_downloads"),
        )

    def result(self, uid, job_id):
        data = self.results.get(job_id)
        if not data or data["userId"] != str(uid) or data["expiresAt"] <= time.time():
            raise ValueError(tx("file_tools.the_file_job_does_not_exist"))
        return dict(data)

    def download(self, uid, job_id):
        data = self.result(uid, job_id)
        if data["state"] != "done":
            raise ValueError(tx("file_tools.the_file_is_not_ready"))
        return Path(self.directories[job_id].name) / "result.bin", safe_name(
            data["name"]
        )

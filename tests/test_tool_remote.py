"""LAN worker isolation, authentication, transfer and quota regressions."""

import asyncio
import base64
import json
import ssl
import threading
from types import SimpleNamespace
import uuid

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from src.services.file_tools import FileTools
from src.services.tool_protocol import disk
from src.services.tool_protocol import engine_digest
from src.services.tool_protocol import MAX_TOTAL_BYTES
from src.services.tool_protocol import validate_manifest
from src.services.tool_protocol import validate_result
from src.services.tool_quota import points
from src.services.tool_remote import RemoteWorker
from src.services.tool_remote import WorkerServer
from src.tool_worker_setup import check_worker
from src.tool_worker_setup import generate_certificate
from src.tool_worker_setup import write_config

TOKEN = "1" * 64


@pytest.fixture
async def worker(tmp_path):
    fingerprint = generate_certificate(tmp_path, "127.0.0.1")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "worker-cert.pem", tmp_path / "worker-key.pem")
    temporary = tmp_path / "worker-temp"
    temporary.mkdir()
    backend = WorkerServer(
        {"token": TOKEN, "allowedIPs": ["127.0.0.1"]}, temp_dir=temporary
    )
    server = TestServer(backend.create_app(), scheme="https")
    # aiohttp's TestServer already enables cancellation on disconnect.
    await server.start_server(ssl=context)
    config = {
        "enabled": True,
        "endpoint": str(server.make_url("/")).rstrip("/"),
        "token": TOKEN,
        "fingerprint": fingerprint,
    }
    try:
        yield SimpleNamespace(
            backend=backend, config=config, client=RemoteWorker(config), temp=temporary
        )
    finally:
        await server.close()
    assert not list(temporary.iterdir())


def manifest(size=7):
    return {
        "jobId": uuid.uuid4().hex,
        "files": [{"name": "table.csv", "bytes": size}],
        "operation": "json",
        "quality": 78,
        "maxEdge": 4096,
        "timeout": 4,
        "engineDigest": engine_digest(),
    }


def form(data, contents=b"name\na\n"):
    body = aiohttp.FormData()
    body.add_field("manifest", json.dumps(data), content_type="application/json")
    body.add_field(
        "file-0",
        contents,
        filename="../not-a-storage-path.csv",
        content_type="application/octet-stream",
    )
    return body


async def post(worker, data, contents=b"name\na\n"):
    async with worker.client.session(10) as session:
        response = await session.post(
            worker.client.endpoint + "/process",
            data=form(data, contents),
            ssl=worker.client.fingerprint,
        )
        await response.read()
        return response


async def test_worker_requires_own_key_and_pinned_certificate(worker):
    assert (await worker.client.health())["concurrency"] == 1
    bad = RemoteWorker({**worker.config, "token": "2" * 64})
    with pytest.raises(ValueError):
        await bad.health()
    wrong_cert = RemoteWorker({**worker.config, "fingerprint": "0" * 64})
    with pytest.raises(aiohttp.ServerFingerprintMismatch):
        await wrong_cert.health()
    async with worker.client.session(10) as session:
        response = await session.get(
            worker.client.endpoint + "/health",
            ssl=worker.client.fingerprint,
            headers={"Authorization": "Bearer 無效"},
        )
        assert response.status == 401


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:8787",
        "https://example.com",
        "https://8.8.8.8",
        "https://127.0.0.1/path",
        "https://user:pass@127.0.0.1",
    ],
)
def test_only_private_https_endpoints_are_allowed(endpoint):
    with pytest.raises(ValueError):
        RemoteWorker({"endpoint": endpoint, "token": TOKEN, "fingerprint": "0" * 64})


async def test_actual_image_conversion_and_activation_probe(worker):
    await check_worker(worker.config)
    assert len(worker.backend.seen) == 1
    assert not list(worker.temp.iterdir())


async def test_source_version_mismatch_and_replay_are_rejected(worker):
    data = manifest()
    mismatch = {**data, "engineDigest": "0" * 64}
    response = await post(worker, mismatch)
    assert response.status == 409
    assert not worker.backend.seen
    response = await post(worker, data)
    assert response.status == 200
    assert json.loads(await response.read()) == [{"name": "a"}]
    response = await post(worker, data)
    assert response.status == 409


@pytest.mark.parametrize(
    "change",
    [
        {"files": [{"name": "../secret.json", "bytes": 7}]},
        {"files": [{"name": "x.csv", "bytes": MAX_TOTAL_BYTES + 1}]},
        {"files": [{"name": "x.csv", "bytes": True}]},
        {"timeout": 61},
        {"quality": True},
        {"maxEdge": 9000},
        {"jobId": "../external"},
        {"operation": "execute"},
    ],
)
async def test_invalid_limits_and_paths_never_start_a_process(
    worker, change, monkeypatch
):
    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid request launched a subprocess")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    response = await post(worker, {**manifest(), **change})
    assert response.status == 400
    assert not list(worker.temp.iterdir())


async def test_declared_file_size_is_enforced_during_streaming(worker):
    response = await post(worker, manifest(1))
    assert response.status == 400
    assert not list(worker.temp.iterdir())
    async with worker.client.session(10) as session:
        response = await session.post(
            worker.client.endpoint + "/process", json={}, ssl=worker.client.fingerprint
        )
        assert response.status == 400


async def test_only_one_work_runs_at_once(worker):
    worker.backend.busy = True
    try:
        response = await post(worker, manifest())
        assert response.status == 503
        assert not worker.backend.seen
    finally:
        worker.backend.busy = False


async def test_remote_pipeline_preserves_quota_and_removes_inputs(
    worker, monkeypatch, tmp_path
):
    config = tmp_path / "pairing.json"
    write_config(config, worker.config)
    monkeypatch.setenv("FILE_TOOLS_WORKER_CONFIG", str(config))
    service = FileTools()
    await service.start()
    try:
        assert service.remote is not None
        assert service.slots._value == 1
        job = await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.tasks[job]
        result = service.result("101", job)
        assert result["state"] == "done"
        assert result["points"] == points(7, result["seconds"])
        assert service.quota.snapshot("101")["weekly"]["used"] == result["points"]
        assert job in worker.backend.seen
        output, _ = service.download("101", job)
        assert json.loads(output.read_text()) == [{"name": "a"}]
        assert not list(output.parent.glob("input-*"))
    finally:
        await service.close()


async def test_remote_failure_does_not_run_local_worker_or_charge(
    worker, monkeypatch, tmp_path
):
    config = tmp_path / "pairing.json"
    write_config(config, {**worker.config, "token": "2" * 64})
    monkeypatch.setenv("FILE_TOOLS_WORKER_CONFIG", str(config))
    service = FileTools()
    await service.start()

    async def forbidden(*args, **kwargs):
        pytest.fail("Disconnected remote worker fell back to local processing")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    try:
        job = await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.tasks[job]
        assert service.result("101", job)["state"] == "failed"
        snapshot = service.quota.snapshot("101")
        assert snapshot["weekly"]["used"] == snapshot["reserved"] == 0
    finally:
        await service.close()


async def test_remote_timeout_kills_and_reaps_subprocess(worker, monkeypatch):
    stopped = asyncio.Event()

    class Process:
        returncode = None
        killed = False

        async def wait(self):
            await stopped.wait()
            self.returncode = -1

        def kill(self):
            self.killed = True
            stopped.set()

    process = Process()

    async def spawn(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    response = await post(worker, {**manifest(), "timeout": 1})
    assert response.status == 504
    assert process.killed and process.returncode == -1
    assert not list(worker.temp.iterdir())


async def test_corrupted_download_never_leaves_accepted_output(
    worker, tmp_path, monkeypatch
):
    root = tmp_path / "request"
    root.mkdir()
    (root / "input.csv").write_bytes(b"name\na\n")
    (root / "request.json").write_text(
        json.dumps(
            {
                "files": [{"name": "table.csv", "stored": "input.csv"}],
                "operation": "json",
                "quality": 78,
                "maxEdge": 4096,
            }
        )
    )

    async def corrupt(request):
        await request.read()
        payload = b"partial"
        result = {
            "name": "table.json",
            "bytes": len(payload),
            "seconds": 0.1,
            "changed": True,
            "engine": None,
            "sha256": "0" * 64,
            "engineDigest": engine_digest(),
        }
        return web.Response(
            body=payload,
            headers={
                "X-Tool-Result": base64.b64encode(json.dumps(result).encode()).decode()
            },
        )

    monkeypatch.setattr(worker.backend, "convert", corrupt)
    with pytest.raises(ValueError):
        await worker.client.process(root, {"timeout": 4}, uuid.uuid4().hex)
    assert not (root / "result.bin").exists()


def test_result_validation_rejects_non_finite_time_and_traversal():
    data = {
        "name": "x.png",
        "bytes": 10,
        "seconds": 0.1,
        "changed": True,
        "engine": "NovaGrid/2",
        "sha256": "0" * 64,
        "engineDigest": engine_digest(),
    }
    for change in (
        {"seconds": float("nan")},
        {"seconds": 61},
        {"bytes": MAX_TOTAL_BYTES + 1},
        {"name": "../x.png"},
        {"changed": 1},
        {"engineDigest": "0" * 64},
    ):
        with pytest.raises(ValueError):
            validate_result({**data, **change}, 60)
    assert validate_manifest(manifest())["timeout"] == 4


def test_disabled_pairing_does_not_change_local_mode(monkeypatch, tmp_path):
    config = tmp_path / "pairing.json"
    write_config(config, {"enabled": False})
    monkeypatch.setenv("FILE_TOOLS_WORKER_CONFIG", str(config))
    assert RemoteWorker.configured() is None


async def test_expired_remote_deadline_is_refunded_before_sending(
    worker, monkeypatch, tmp_path
):
    config = tmp_path / "pairing.json"
    write_config(config, worker.config)
    monkeypatch.setenv("FILE_TOOLS_WORKER_CONFIG", str(config))
    service = FileTools()
    await service.start()
    # Simulate file preparation overrunning the total budget after reservation.
    quote = service.quota.quote("101", [7], "json")
    quote["remoteDeadline"] = 0
    job = service.quota.reserve("101", quote)
    root = tmp_path / "request"
    root.mkdir()
    service.results[job] = {"state": "pending"}
    try:
        await service._process("101", job, root, quote)
        assert service.results[job]["state"] == "failed"
        assert not worker.backend.seen
        assert service.quota.snapshot("101")["reserved"] == 0
    finally:
        await service.close()


async def test_remote_admission_is_bounded_and_cancelled_jobs_release_quota(
    worker, monkeypatch, tmp_path
):
    config = tmp_path / "pairing.json"
    write_config(config, worker.config)
    monkeypatch.setenv("FILE_TOOLS_WORKER_CONFIG", str(config))
    service = FileTools()
    await service.start()
    wait = asyncio.Event()

    async def pending(*args):
        await wait.wait()

    monkeypatch.setattr(service.remote, "process", pending)
    try:
        await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.submit("102", [("table.csv", b"name\na\n")], "json")
        with pytest.raises(ValueError):
            await service.submit("103", [("table.csv", b"name\na\n")], "json")
    finally:
        await service.close()
    for uid in ("101", "102", "103"):
        snapshot = service.quota.snapshot(uid)
        assert snapshot["reserved"] == snapshot["weekly"]["used"] == 0


async def test_client_disconnect_stops_worker_and_cleans_input(worker, monkeypatch):
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Process:
        returncode = None

        async def wait(self):
            await stopped.wait()
            self.returncode = -1

        def kill(self):
            stopped.set()

    process = Process()

    async def spawn(*args, **kwargs):
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    async with worker.client.session(10) as session:

        async def send():
            async with session.post(
                worker.client.endpoint + "/process",
                data=form(manifest()),
                ssl=worker.client.fingerprint,
            ) as response:
                await response.read()

        task = asyncio.create_task(send())
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.wait_for(stopped.wait(), 2)
        await worker.backend.shutdown(None)
    assert process.returncode == -1
    assert not list(worker.temp.iterdir())


async def test_repeated_cancellation_waits_for_disk_write_to_finish():
    started = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def write():
        started.set()
        release.wait(timeout=3)
        completed.set()

    task = asyncio.create_task(disk(write))
    await asyncio.to_thread(started.wait, 2)
    try:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert completed.is_set()

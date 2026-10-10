"""Quota accounting, failure recovery and private transfer regressions."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

from aiohttp import FormData
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.test_utils import TestServer
from PIL import Image
import pytest

from src.config.constants import DEVELOPER_IDS
from src.services.file_tools import FileTools
from src.services.file_tools import ToolTokens
from src.services.tool_card import usage_card
from src.services.tool_quota import MIB
from src.services.tool_quota import TAIPEI
from src.services.tool_quota import ToolQuota
from src.services.tool_routes import install_routes
from src.services.tool_worker import convert

OWNER = next(iter(DEVELOPER_IDS))


@pytest.fixture
def quota(tmp_path):
    now = [datetime(2026, 10, 11, 23, 59, tzinfo=TAIPEI).timestamp()]
    service = ToolQuota(tmp_path / "quota.db", clock=lambda: now[0])
    return service, now


def complete(service, uid="101", size=1, seconds=0):
    quote = service.quote(uid, [size], "png")
    job = service.reserve(uid, quote)
    charged = service.finish(uid, job, seconds, True)
    return job, charged


def test_free_is_immediately_available_and_tiers_never_require_payment(quota):
    service, now = quota
    assert service.snapshot("101")["tier"]["name"] == "Free."
    complete(service)
    assert service.snapshot("101")["weekly"]["used"] == 1
    for days, name in [
        (29, "Free."),
        (30, "Run."),
        (60, "Dash."),
        (120, "Grow."),
        (180, "Ultra."),
    ]:
        first = service.snapshot("101")["firstSeen"]
        now[0] = first + days * 86400
        assert service.snapshot("101")["tier"]["name"] == name


def test_week_boundary_and_rolling_window_are_independent(quota):
    service, now = quota
    complete(service)
    now[0] += 120
    data = service.snapshot("101")
    assert data["weekly"]["used"] == 0
    assert data["rolling"]["used"] == 1
    now[0] += 10800
    assert service.snapshot("101")["rolling"]["used"] == 0


def test_dynamic_points_failures_no_savings_and_idempotent_settlement(quota):
    service, _ = quota
    job, charged = complete(service, size=MIB, seconds=1.1)
    assert charged == 4
    assert service.finish("101", job, 3, True) == 4
    quote = service.quote("102", [MIB], "compress")
    failed = service.reserve("102", quote)
    assert service.finish("102", failed, 2, False) == 0
    unchanged = service.reserve("102", quote)
    assert service.finish("102", unchanged, 2, True, False) == 0


def test_reservations_enforce_limits_and_expire_after_worker_loss(quota):
    service, now = quota
    quote = service.quote("101", [2 * MIB], "png")
    job = service.reserve("101", quote, "unique")
    assert service.snapshot("101")["reserved"] == 10
    with pytest.raises(ValueError):
        service.reserve("101", quote)
    with pytest.raises(ValueError):
        service.reserve("102", quote, "unique")
    now[0] += 301
    assert service.snapshot("101")["reserved"] == 0
    assert service.finish("101", job, 1, True) == 0


def test_concurrent_requests_cannot_double_reserve(quota):
    service, _ = quota
    quote = service.quote("101", [MIB], "png")

    def submit(_):
        try:
            return service.reserve("101", quote)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(submit, range(5)))
    assert sum(result is not None for result in results) == 1


def test_coupon_ownership_single_use_history_and_scope(quota):
    service, _ = quota
    complete(service, "101")
    complete(service, "102")
    assert service.admin(OWNER, "issue", "grant") == 2
    assert service.admin(OWNER, "issue", "grant") == 2
    coupon = service.inventory("101")["items"][0]["id"]
    with pytest.raises(ValueError):
        service.redeem("102", coupon)
    first_seen = service.snapshot("101")["firstSeen"]
    service.redeem("101", coupon)
    assert service.snapshot("101")["weekly"]["used"] == 0
    assert service.snapshot("101")["firstSeen"] == first_seen
    assert service.snapshot("102")["weekly"]["used"] == 1
    assert service.inventory("101", True)["total"] == 1
    with pytest.raises(ValueError):
        service.redeem("101", coupon)
    assert service.jobs("101")[0]["points"] == 1


def test_admin_authorization_scoped_and_global_reset_preserve_tenure(quota):
    service, _ = quota
    complete(service, "101")
    complete(service, "102")
    with pytest.raises(PermissionError):
        service.admin("123", "reset", "bad")
    service.admin(OWNER, "reset", "server", ["101"], "999")
    assert service.snapshot("101")["weekly"]["used"] == 0
    assert service.snapshot("102")["weekly"]["used"] == 1
    service.admin(OWNER, "reset", "all")
    assert service.snapshot("102")["weekly"]["used"] == 0


def test_reset_during_processing_does_not_make_inflight_work_free(quota):
    service, _ = quota
    job = service.reserve("101", service.quote("101", [1], "png"))
    service.admin(OWNER, "reset", "reset")
    assert service.snapshot("101")["reserved"] > 0
    service.finish("101", job, 0, True)
    assert service.snapshot("101")["weekly"]["used"] == 1


def test_batch_and_file_size_limits_are_enforced_by_server(quota):
    service, now = quota
    service.register("101")
    for sizes in ([1, 1], [2 * MIB + 1], [0], [True]):
        with pytest.raises(ValueError):
            service.quote("101", sizes, "png")
    now[0] += 60 * 86400
    assert service.quote("101", [1, 1, 1], "png")["count"] == 3


def test_historical_achievements_seed_existing_tenure_without_modifying_source(
    quota, tmp_path
):
    service, now = quota
    directory = tmp_path / "data/storage"
    directory.mkdir(parents=True)
    source = directory / "achievements.json"
    content = json.dumps(
        {
            "101": {
                "99": {
                    "unlocked_at_first_interaction": datetime.fromtimestamp(
                        now[0] - 60 * 86400, TAIPEI
                    ).isoformat()
                }
            }
        }
    )
    source.write_text(content, encoding="utf-8")
    service.import_history()
    service.import_history()
    assert service.snapshot("101")["tier"]["name"] == "Dash."
    assert source.read_text(encoding="utf-8") == content


def test_signed_tickets_cannot_be_repurposed_or_tampered():
    tokens = ToolTokens("x" * 32)
    ticket = tokens.issue("101", "upload", sizes=[1])
    assert tokens.read(ticket, "upload")["uid"] == "101"
    with pytest.raises(ValueError):
        tokens.read(ticket, "download")
    with pytest.raises(ValueError):
        tokens.read(ticket + "x", "upload")


def test_real_image_conversion_strips_metadata_and_rejects_animation(tmp_path):
    source = tmp_path / "image.png"
    Image.new("RGBA", (120, 80), (255, 0, 0, 128)).save(source)
    output = tmp_path / "result.bin"
    suffix, changed = convert(source, output, "jpg")
    assert suffix == ".jpg" and changed
    with Image.open(output) as image:
        assert image.format == "JPEG" and image.mode == "RGB"
    animated = tmp_path / "animation.gif"
    Image.new("RGB", (10, 10), "red").save(
        animated, save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")]
    )
    with pytest.raises(ValueError):
        convert(animated, output, "png")


def test_table_conversion_preserves_unicode_and_rejects_nested_json(tmp_path):
    source = tmp_path / "table.csv"
    source.write_text('名稱,內容\n測試,"逗號,內容"\n', encoding="utf-8")
    output = tmp_path / "out.json"
    convert(source, output, "json")
    assert json.loads(output.read_text(encoding="utf-8"))[0]["內容"] == "逗號,內容"
    output.write_text('[{"x": {"nested": true}}]', encoding="utf-8")
    with pytest.raises(ValueError):
        convert(output, tmp_path / "out.csv", "csv")


def test_usage_card_is_a_real_image(quota):
    service, _ = quota
    with Image.open(usage_card(service.snapshot("101"))) as image:
        assert image.size == (1100, 620)


async def test_processing_pipeline_and_private_api_upload(tmp_path):
    service = FileTools()
    await service.start()
    bot = SimpleNamespace(get_cog=lambda name: SimpleNamespace(engine=service))
    app = web.Application(client_max_size=1024)
    install_routes(app, bot)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        # A streamed transfer exceeds the metadata application's body limit.
        data = b"name,value\n" + b"a,1\n" * 6000
        ticket = service.tokens.issue(
            "101",
            "upload",
            sizes=[len(data)],
            operation="json",
            quality=78,
            maxEdge=4096,
        )
        form = FormData()
        form.add_field("files", data, filename="table.csv", content_type="text/csv")
        response = await client.post(
            "/tools/upload",
            data=form,
            headers={"X-Tool-Token": ticket, "Origin": "https://botweb.shizune.life"},
        )
        assert response.status == 202
        job = (await response.json())["id"]
        task = service.tasks.get(job)
        if task:
            await task
        result = service.result("101", job)
        assert result["state"] == "done"
        assert result["points"] >= 1
        with pytest.raises(ValueError):
            service.download("102", job)
        signed = service.tokens.issue("101", "download", jobId=job)
        response = await client.get("/tools/download", headers={"X-Tool-Token": signed})
        assert response.status == 200
        assert json.loads(await response.text())[0]["name"] == "a"
        response = await client.get(
            "/tools/download",
            headers={"X-Tool-Token": signed, "Origin": "https://evil.example"},
        )
        assert response.status == 403
        response = await client.get("/tools/download")
        assert response.status == 400
        assert not list(Path(service.directories[job].name).glob("input-*"))
    finally:
        await client.close()
        await service.close()


async def test_invalid_input_is_not_charged():
    service = FileTools()
    await service.start()
    try:
        job = await service.submit("101", [("broken.png", b"not an image")], "png")
        await service.tasks[job]
        assert service.result("101", job)["state"] == "failed"
        assert service.quota.snapshot("101")["weekly"]["used"] == 0
        assert service.quota.snapshot("101")["reserved"] == 0
    finally:
        await service.close()


async def test_lost_commit_acknowledgement_retries_same_charge(monkeypatch):
    service = FileTools()
    await service.start()
    finish = service.quota.finish
    attempts = []

    def uncertain(*args):
        charge = finish(*args)
        attempts.append(args)
        if len(attempts) == 1:
            raise OSError("commit acknowledgement lost")
        return charge

    monkeypatch.setattr(service.quota, "finish", uncertain)
    try:
        job = await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.tasks[job]
        result = service.result("101", job)
        assert result["state"] == "done"
        assert attempts[0] == attempts[1]
        assert service.quota.snapshot("101")["weekly"]["used"] == result["points"] > 0
    finally:
        await service.close()


async def test_settlement_outage_is_not_reported_as_free_failure(monkeypatch):
    service = FileTools()
    await service.start()
    finish = service.quota.finish

    def unavailable(*args):
        raise OSError("temporary database outage")

    monkeypatch.setattr(service.quota, "finish", unavailable)
    try:
        job = await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.tasks[job]
        assert service.result("101", job)["state"] == "settling"
        assert "points" not in service.result("101", job)
        with pytest.raises(ValueError):
            service.download("101", job)
        monkeypatch.setattr(service.quota, "finish", finish)
        await service._settle(job)
        assert service.result("101", job)["state"] == "done"
    finally:
        await service.close()


async def test_dashboard_metadata_requires_secret_and_verified_user(monkeypatch):
    from src.cogs.core.dashboard_api import DashboardAPI

    service = FileTools()
    await service.start()
    bot = SimpleNamespace(
        get_cog=lambda name: SimpleNamespace(engine=service), is_ready=lambda: True
    )
    client = TestClient(TestServer(DashboardAPI(bot).create_app("test-secret")))
    await client.start_server()
    try:
        assert (await client.get("/tools/usage")).status == 401
        assert (
            await client.get(
                "/tools/usage", headers={"Authorization": "Bearer test-secret"}
            )
        ).status == 400
        response = await client.get(
            "/tools/usage",
            headers={"Authorization": "Bearer test-secret", "X-Discord-User": "101"},
        )
        assert response.status == 200
        assert (await response.json())["tier"]["name"] == "Free."
        assert (await client.post("/tools/upload")).status == 400
    finally:
        await client.close()
        await service.close()


def test_coupon_concurrent_redemption_has_one_winner(quota):
    service, _ = quota
    complete(service)
    service.admin(OWNER, "issue", "coupon-race", ["101"])
    coupon = service.inventory("101")["items"][0]["id"]

    def redeem():
        try:
            service.redeem("101", coupon)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: redeem(), range(2))) == [False, True]
    assert service.inventory("101", used=True)["total"] == 1


async def test_worker_timeout_kills_process_and_releases_reservation(monkeypatch):
    service = FileTools()
    await service.start()

    class Process:
        returncode = None
        killed = False

        async def wait(self):
            if self.returncode is None:
                await asyncio.sleep(10)

        def kill(self):
            self.killed = True
            self.returncode = -1

    process = Process()

    async def spawn(*args, **kwargs):
        return process

    quote = service.quota.quote

    def short_quote(*args):
        return {**quote(*args), "timeout": 0.01}

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(service.quota, "quote", short_quote)
    try:
        job = await service.submit("101", [("table.csv", b"name\na\n")], "json")
        await service.tasks[job]
        assert process.killed
        assert service.result("101", job)["state"] == "failed"
        state = service.quota.snapshot("101")
        assert state["weekly"]["used"] == state["reserved"] == 0
        assert not list(Path(service.directories[job].name).glob("input-*"))
    finally:
        await service.close()


async def test_batch_outputs_are_downloadable_zip(quota):
    import zipfile

    ledger, now = quota
    ledger.register("101")
    now[0] += 60 * 86400
    service = FileTools()
    service.quota = ledger
    try:
        job = await service.submit(
            "101", [("a.csv", b"name\na\n"), ("b.csv", b"name\nb\n")], "json"
        )
        await service.tasks[job]
        path, name = service.download("101", job)
        assert name.endswith(".zip")
        with zipfile.ZipFile(path) as archive:
            assert len(archive.namelist()) == 2
            assert json.loads(archive.read("02-b.json"))[0]["name"] == "b"
    finally:
        await service.close()

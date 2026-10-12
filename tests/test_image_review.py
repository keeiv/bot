"""The three-stage AI image review: policy, cascade, worker, bot side and fallback.

No test talks to a real Ollama: a scripted fake plays the models, so what is
checked is the decision logic and the transport, not any model's judgement.
"""

import asyncio
import io
import json
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
from aiohttp.test_utils import TestServer
import discord
from PIL import Image
import pytest

from src.cogs.core.bot_appearance import BotAppearance
from src.services import moderation_engine as engine
from src.services import moderation_protocol as protocol
from src.services.moderation_ollama import find_ollama
from src.services.moderation_ollama import install_ollama
from src.services.moderation_ollama import Ollama
from src.services.moderation_ollama import OllamaError
from src.services.moderation_remote import ImageReviewService
from src.services.moderation_remote import ModerationWorker
from src.services.moderation_remote import Outcome
from src.services.moderation_remote import UNAVAILABLE
from src.services.moderation_worker import ReviewServer
from src.services.tool_remote import RemoteWorker
from src.tool_worker_setup import generate_certificate

TOKEN = "2" * 64
STAGES = protocol.stage_config()
FAST, MIDDLE, STRICT = (s["model"] for s in STAGES)


def png(size=(64, 48), colour=(30, 120, 240)):
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()


def reply(verdict, categories=(), reason="r"):
    return json.dumps(
        {"verdict": verdict, "categories": list(categories), "reason": reason}
    )


class FakeOllama:
    """Plays the three models: ``script[model]`` is a list of replies or errors."""

    def __init__(self, script, models=None):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls = []
        self.present = set(models if models is not None else (FAST, MIDDLE, STRICT))
        self.pulled = []

    async def chat(self, model, system, prompt, images, *, think, seconds, tokens):
        self.calls.append((model, think, len(images), system))
        step = self.script[model].pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return await step()
        return step

    async def models(self):
        return set(self.present)

    async def pull(self, model, on_progress):
        self.pulled.append(model)
        on_progress("pulling", 5, 10)
        on_progress("pulling", 10, 10)
        self.present.add(model)

    async def version(self):
        return "0.0"

    async def close(self):
        pass


def safe_script():
    return {m: [reply("safe")] for m in (FAST, MIDDLE, STRICT)}


# ── policy and contract ───────────────────────────────────────────
def test_the_three_stages_are_fast_then_thinking_models():
    assert [s["think"] for s in STAGES] == [False, True, True]
    assert len({s["model"] for s in STAGES}) == 3
    for stage in STAGES:
        assert protocol.MODEL_PATTERN.fullmatch(stage["model"])
    for number, prompt in protocol.PROMPTS.items():
        for word in ("sexual", "violence", "tos", "Discord"):
            assert word in prompt, (number, word)
    assert "first pass" in protocol.PROMPTS[2] and "last and" in protocol.PROMPTS[3]


def test_models_can_be_replaced_but_not_by_junk():
    assert protocol.stage_config({"2": "llava:7b"})[1]["model"] == "llava:7b"
    for bad in ({"4": "a:b"}, {"1": "no-tag"}, {"1": "x:y; rm"}, ["a:b"]):
        with pytest.raises(ValueError):
            protocol.stage_config(bad)


def manifest(**override):
    data = {
        "jobId": "job1",
        "files": [{"name": "a.png", "bytes": 10}],
        "engineDigest": protocol.engine_digest(),
    }
    data.update(override)
    return data


def test_a_request_holds_one_or_two_images_only():
    protocol.validate_manifest(manifest())
    two = [{"name": "a.png", "bytes": 1}, {"name": "b.png", "bytes": 1}]
    protocol.validate_manifest(manifest(files=two))
    for files in (
        [],
        two + [two[0]],
        [{"name": "a.png", "bytes": 0}],
        [{"name": "a.png", "bytes": protocol.MAX_IMAGE_BYTES + 1}],
        [{"name": "../a.png", "bytes": 1}],
    ):
        with pytest.raises(ValueError):
            protocol.validate_manifest(manifest(files=files))


def item(verdict, stage, stages, **extra):
    base = {
        "index": 0,
        "verdict": verdict,
        "stage": stage,
        "categories": [],
        "reason": "",
        "stages": stages,
    }
    base.update(extra)
    return base


def stages_of(*verdicts):
    return [
        {"stage": i + 1, "verdict": v, "seconds": 1.0} for i, v in enumerate(verdicts)
    ]


def test_a_forged_approval_without_three_clean_stages_is_refused():
    digest = protocol.engine_digest()
    ok = {
        "results": [item("approved", 3, stages_of("safe", "safe", "safe"))],
        "engineDigest": digest,
    }
    protocol.validate_result(ok, 1)
    for stages in (
        stages_of(),
        stages_of("safe"),
        stages_of("safe", "safe"),
        stages_of("safe", "unsafe", "safe"),
        stages_of("safe", "safe", "uncertain"),
        stages_of("safe", "safe", "error"),
    ):
        forged = {"results": [item("approved", 3, stages)], "engineDigest": digest}
        with pytest.raises(ValueError):
            protocol.validate_result(forged, 1)
    with pytest.raises(ValueError):  # wrong count, wrong engine
        protocol.validate_result(ok, 2)
    with pytest.raises(ValueError):
        protocol.validate_result({**ok, "engineDigest": "0" * 64}, 1)


# ── reading a model's answer ──────────────────────────────────────
@pytest.mark.parametrize(
    "text,expected",
    [
        (reply("safe"), ("safe", [], "r")),
        (
            "```json\n" + reply("unsafe", ["sexual"]) + "\n```",
            ("unsafe", ["sexual"], "r"),
        ),
        # a thinking model may write braces while it reasons; the last verdict wins
        ("I think {maybe} unsafe. " + reply("safe"), ("safe", [], "r")),
        (
            reply("unsafe", ["violence", "violence", "nonsense"]),
            ("unsafe", ["violence"], "r"),
        ),
        (
            '{"verdict": "uncertain", "categories": "x", "reason": "a\\nb"}',
            ("uncertain", [], "a b"),
        ),
    ],
)
def test_parse_verdict(text, expected):
    assert engine.parse_verdict(text) == expected


@pytest.mark.parametrize("text", ["", "safe", "{}", '{"verdict": "fine"}', "{not json"])
def test_an_unreadable_answer_is_an_error_never_a_pass(text):
    with pytest.raises(ValueError):
        engine.parse_verdict(text)


def test_images_are_downscaled_and_animations_sampled():
    frames = engine.prepare_image(png((4000, 3000)))
    assert len(frames) == 1
    import base64

    with Image.open(io.BytesIO(base64.b64decode(frames[0]))) as shown:
        assert max(shown.size) == engine.MAX_EDGE
    out = io.BytesIO()
    first = Image.new("RGB", (10, 10), "red")
    first.save(
        out,
        "GIF",
        save_all=True,
        append_images=[
            Image.new("RGB", (10, 10), c) for c in ("green", "blue", "white", "black")
        ],
        duration=50,
    )
    assert len(engine.prepare_image(out.getvalue())) == engine.MAX_FRAMES
    with pytest.raises(OSError):  # PIL.UnidentifiedImageError
        engine.prepare_image(b"not an image")


# ── the cascade ───────────────────────────────────────────────────
async def run(script, data=None, **kwargs):
    fake = FakeOllama(script)
    events = []
    result = await engine.review_image(
        fake, STAGES, 0, data or png(), lambda kind, **d: events.append((kind, d))
    )
    return result, fake, events


async def test_an_image_all_three_stages_call_safe_is_approved():
    result, fake, events = await run(safe_script())
    assert result["verdict"] == protocol.APPROVED and result["stage"] == 3
    assert [c[0] for c in fake.calls] == [FAST, MIDDLE, STRICT]
    assert [c[1] for c in fake.calls] == [False, True, True]
    assert [s["verdict"] for s in result["stages"]] == ["safe"] * 3
    assert [e[1]["state"] for e in events if e[0] == "stage"] == [
        "running",
        "safe",
        "running",
        "safe",
        "running",
        "safe",
    ]
    protocol.validate_result(
        {"results": [result], "engineDigest": protocol.engine_digest()}, 1
    )


@pytest.mark.parametrize("stage,model", [(1, FAST), (2, MIDDLE), (3, STRICT)])
async def test_the_first_unsafe_stage_rejects_and_stops_the_rest(stage, model):
    script = safe_script()
    script[model] = [reply("unsafe", ["violence"], "blood")]
    result, fake, _ = await run(script)
    assert result["verdict"] == protocol.REJECTED and result["stage"] == stage
    assert result["categories"] == ["violence"]
    assert len(fake.calls) == stage  # later, slower models never run


async def test_unsure_at_the_last_stage_is_a_rejection_but_earlier_it_moves_on():
    script = safe_script()
    script[STRICT] = [reply("uncertain")]
    result, _, _ = await run(script)
    assert result["verdict"] == protocol.REJECTED and result["categories"] == ["tos"]
    script = safe_script()
    script[FAST] = [reply("uncertain")]
    result, fake, _ = await run(script)
    assert result["verdict"] == protocol.APPROVED  # stages 2 and 3 looked harder
    assert len(fake.calls) == 3


async def test_a_stage_that_fails_makes_the_whole_review_unavailable():
    script = safe_script()
    script[MIDDLE] = [OllamaError("down")]
    result, fake, _ = await run(script)
    assert result["verdict"] == protocol.UNAVAILABLE and result["stage"] == 2
    assert result["stages"][-1]["verdict"] == "error"
    assert STRICT not in [c[0] for c in fake.calls]


async def test_a_rambling_model_gets_one_retry_then_counts_as_a_failure():
    script = safe_script()
    script[FAST] = ["no json here", reply("safe")]
    result, _, _ = await run(script)
    assert result["verdict"] == protocol.APPROVED
    script = safe_script()
    script[FAST] = ["no json", "still none"]
    result, _, _ = await run(script)
    assert result["verdict"] == protocol.UNAVAILABLE


async def test_a_stage_that_never_answers_times_out_into_unavailable(monkeypatch):
    monkeypatch.setattr(protocol, "STAGE_SECONDS", (0.05, 0.05, 0.05))

    async def stuck():
        await asyncio.sleep(30)

    script = safe_script()
    script[FAST] = [stuck]
    monkeypatch.setattr(
        engine.asyncio, "wait_for", _short_wait(engine.asyncio.wait_for)
    )
    result, _, _ = await run(script)
    assert result["verdict"] == protocol.UNAVAILABLE and result["stage"] == 1


def _short_wait(real):
    async def wait(awaitable, timeout):
        return await real(awaitable, min(timeout, 0.2))

    return wait


async def test_an_unreadable_image_is_unavailable_not_approved():
    result, fake, _ = await run(safe_script(), data=b"GIF89a-broken")
    assert result["verdict"] == protocol.UNAVAILABLE and fake.calls == []


# ── the worker server ─────────────────────────────────────────────
@pytest.fixture
async def worker(tmp_path):
    fingerprint = generate_certificate(tmp_path, "127.0.0.1")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "worker-cert.pem", tmp_path / "worker-key.pem")
    made = []

    async def start(script, ready=True):
        fake = FakeOllama(script)
        backend = ReviewServer(
            {"token": TOKEN, "allowedIPs": ["127.0.0.1"]}, fake, prepare_on_start=False
        )
        backend.ready = ready
        server = TestServer(backend.create_app(), scheme="https")
        await server.start_server(ssl=context)
        made.append(server)
        config = {
            "enabled": True,
            "endpoint": str(server.make_url("/")).rstrip("/"),
            "token": TOKEN,
            "fingerprint": fingerprint,
        }
        return SimpleNamespace(
            backend=backend, fake=fake, config=config, client=ModerationWorker(config)
        )

    yield start
    for server in made:
        await server.close()


async def test_the_worker_reports_whether_it_is_ready(worker):
    node = await worker(safe_script())
    health = await node.client.health()
    assert health["ready"] and health["slots"] == protocol.MAX_IMAGES
    assert health["models"] == {"1": True, "2": True, "3": True}
    node.fake.present.discard(STRICT)
    assert not (await node.client.health())["ready"]
    cold = await worker(safe_script(), ready=False)
    assert not (await cold.client.health())["ready"]
    with pytest.raises(ValueError):  # a worker still preparing does no reviews
        await cold.client.review([("a.png", png())])


async def test_two_images_are_reviewed_at_the_same_time(worker):
    both_started = asyncio.Event()
    seen = []

    async def rendezvous():
        seen.append(1)
        if len(seen) == 2:
            both_started.set()
        # a worker that handled the images one by one would wait here forever
        await asyncio.wait_for(both_started.wait(), 5)
        return reply("safe")

    script = {
        FAST: [rendezvous, rendezvous],
        MIDDLE: [reply("safe")] * 2,
        STRICT: [reply("safe"), reply("unsafe", ["sexual"])],
    }
    node = await worker(script)
    results = await node.client.review([("a.png", png()), ("b.png", png((8, 8)))])
    assert [r["index"] for r in results] == [0, 1]
    assert {r["verdict"] for r in results} == {protocol.APPROVED, protocol.REJECTED}
    assert len(node.backend.free) == protocol.MAX_IMAGES  # both slots given back


async def test_a_busy_worker_refuses_instead_of_queueing(worker):
    release = asyncio.Event()

    async def hold():
        await release.wait()
        return reply("safe")

    node = await worker(
        {FAST: [hold, hold], MIDDLE: [reply("safe")] * 2, STRICT: [reply("safe")] * 2}
    )
    first = asyncio.create_task(
        node.client.review([("a.png", png()), ("b.png", png())])
    )
    while len(node.backend.free) != 0:
        await asyncio.sleep(0.01)
    with pytest.raises(ValueError):
        await node.client.review([("c.png", png())])
    release.set()
    assert len(await first) == 2


async def test_authentication_and_replay(worker):
    node = await worker(safe_script())
    image = png()
    sized = [{"name": "a.png", "bytes": len(image)}]
    async with aiohttp.ClientSession() as session:
        async with session.get(
            node.client.endpoint + "/health", ssl=node.client.fingerprint
        ) as r:
            assert r.status == 401
    async with node.client.session(20) as session:

        def post(data, images=(image,)):
            return session.post(
                node.client.endpoint + "/review",
                data=_form(data, images),
                ssl=node.client.fingerprint,
            )

        async with post(manifest(files=sized)) as r:
            assert r.status == 200
        async with post(manifest(files=sized)) as r:  # the same job id again
            assert r.status == 409
        async with post(manifest(jobId="j2", files=sized, engineDigest="0" * 64)) as r:
            assert r.status == 409
        wrong = [{"name": "a.png", "bytes": len(image) + 5}]
        async with post(manifest(jobId="j3", files=wrong)) as r:
            assert r.status == 400  # fewer bytes than declared


def _form(data, images):
    body = aiohttp.FormData()
    body.add_field("manifest", json.dumps(data), content_type="application/json")
    for index, image in enumerate(images):
        body.add_field(
            f"file-{index}",
            image,
            filename="input",
            content_type="application/octet-stream",
        )
    return body


# ── getting Ollama and the models ready ───────────────────────────
async def test_bootstrap_installs_ollama_starts_it_and_pulls_only_missing_models():
    fake = FakeOllama({}, models={FAST})
    server = ReviewServer(
        {"token": TOKEN, "allowedIPs": ["127.0.0.1"]}, fake, prepare_on_start=False
    )
    installed, started, found = [], [], iter([None, "C:/ollama.exe"])
    server.dashboard.plain = False

    async def start(executable, client):
        started.append(executable)

    await server.bootstrap(
        find=lambda: next(found),
        install=lambda step: (step("下載"), installed.append(1)),
        start=start,
    )
    assert installed == [1] and started == ["C:/ollama.exe"]
    assert fake.pulled == [MIDDLE, STRICT]  # the fast model was already there
    assert server.ready and server.dashboard.ready
    assert all(s["state"] == "ok" for s in server.dashboard.steps)


async def test_a_failed_download_leaves_the_worker_not_ready_and_it_retries(
    monkeypatch,
):
    from src.services import moderation_worker as module

    monkeypatch.setattr(module, "RETRY_SECONDS", 0.01)
    fake = FakeOllama({}, models=set())
    attempts = []
    real_pull = fake.pull

    async def flaky(model, on_progress):
        attempts.append(model)
        if len(attempts) == 1:
            raise OllamaError("network")
        await real_pull(model, on_progress)

    fake.pull = flaky
    server = ReviewServer(
        {"token": TOKEN, "allowedIPs": ["127.0.0.1"]}, fake, prepare_on_start=False
    )

    async def start(executable, client):
        return None

    real = server.bootstrap

    async def once():
        await real(find=lambda: "ollama.exe", install=None, start=start)

    server.bootstrap = once
    task = asyncio.create_task(server.prepare())
    for _ in range(200):
        if server.ready:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    assert server.ready and len(attempts) >= 4  # one failure, then everything


def test_find_ollama_looks_on_the_path_then_in_the_usual_folders(tmp_path):
    assert (
        find_ollama(which=lambda _: "C:/x/ollama.exe", environ={}) == "C:/x/ollama.exe"
    )
    exe = tmp_path / "Programs" / "Ollama" / "ollama.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert find_ollama(
        which=lambda _: None, environ={"LOCALAPPDATA": str(tmp_path)}
    ) == str(exe)
    assert find_ollama(which=lambda _: None, environ={}) is None


def test_install_prefers_winget_and_checks_the_signature_of_a_download():
    calls = []

    def run(argv, **kw):
        calls.append(argv[0])
        return SimpleNamespace(returncode=0, stdout="CN=Ollama")

    install_ollama(lambda _: None, run=run, which=lambda _: "winget")
    assert calls == ["winget"]

    calls.clear()
    downloaded = []
    install_ollama(
        lambda _: None,
        run=run,
        which=lambda _: None,
        download=lambda url, path: downloaded.append(url),
    )
    assert calls[0] == "powershell" and calls[1].endswith("OllamaSetup.exe")
    assert downloaded == ["https://ollama.com/download/OllamaSetup.exe"]


def test_an_installer_with_a_bad_signature_is_never_run():
    calls = []

    def run(argv, **kw):
        calls.append(argv[0])
        return SimpleNamespace(
            returncode=1 if argv[0] == "powershell" else 0, stdout=""
        )

    with pytest.raises(OllamaError):
        install_ollama(
            lambda _: None,
            run=run,
            which=lambda _: None,
            download=lambda url, path: None,
        )
    assert calls == ["powershell"]


def test_ollama_is_only_ever_reached_on_this_machine():
    Ollama("http://127.0.0.1:11434")
    for url in ("http://10.0.0.5:11434", "https://evil.example"):
        with pytest.raises(ValueError):
            Ollama(url)


# ── the bot's side: fallback to a human ───────────────────────────
class FakeWorker:
    def __init__(self, results=None, error=None, delay=0):
        self.results, self.error, self.delay, self.calls = results, error, delay, 0
        self.running = self.peak = 0

    async def review(self, images):
        self.calls += 1
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return self.results
        finally:
            self.running -= 1


def verdict(kind, stage=3, categories=()):
    return [
        {
            "index": 0,
            "verdict": kind,
            "stage": stage,
            "categories": list(categories),
            "reason": "x",
            "stages": [],
        }
    ]


async def test_service_without_a_worker_leaves_everything_to_a_human():
    service = ImageReviewService(configured=lambda: None)
    assert not await service.available()
    assert await service.review("a.png", b"x") == UNAVAILABLE


async def test_service_passes_decisions_through_and_hides_nothing_on_failure():
    service = ImageReviewService(FakeWorker(verdict("rejected", 2, ["sexual"])))
    outcome = await service.review("a.png", b"x")
    assert (outcome.verdict, outcome.stage, outcome.categories) == (
        "rejected",
        2,
        ("sexual",),
    )
    service = ImageReviewService(FakeWorker(error=ValueError("down")))
    assert await service.review("a.png", b"x") == UNAVAILABLE
    # after a failure the next requests go straight to a human for a while
    assert await service.review("b.png", b"x") == UNAVAILABLE
    assert service._worker.calls == 1


async def test_service_reviews_two_images_at_once_and_a_third_waits():
    worker = FakeWorker(verdict("approved"), delay=0.05)
    service = ImageReviewService(worker)
    outcomes = await asyncio.gather(
        *(service.review(f"{i}.png", b"x") for i in range(3))
    )
    assert all(o.verdict == "approved" for o in outcomes)
    assert worker.peak == protocol.MAX_IMAGES and worker.calls == 3


async def test_a_third_image_that_waits_too_long_goes_to_a_human(monkeypatch):
    from src.services import moderation_remote

    monkeypatch.setattr(moderation_remote, "WAIT_SECONDS", 0.05)
    worker = FakeWorker(verdict("approved"), delay=0.3)
    service = ImageReviewService(worker)
    outcomes = await asyncio.gather(
        *(service.review(f"{i}.png", b"x") for i in range(3))
    )
    assert sorted(o.verdict for o in outcomes) == [
        "approved",
        "approved",
        "unavailable",
    ]


def test_configuration_comes_from_its_own_file_and_off_means_off(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_REVIEW_WORKER_CONFIG", str(tmp_path / "missing.json"))
    assert ModerationWorker.configured() is None
    path = tmp_path / "w.json"
    config = {
        "enabled": False,
        "endpoint": "https://10.0.0.2:8788",
        "fingerprint": "a" * 64,
        "token": "b" * 64,
    }
    path.write_text(json.dumps(config))
    monkeypatch.setenv("IMAGE_REVIEW_WORKER_CONFIG", str(path))
    assert ModerationWorker.configured() is None
    path.write_text(json.dumps({**config, "enabled": True}))
    assert isinstance(ModerationWorker.configured(), RemoteWorker)
    path.write_text(json.dumps({**config, "enabled": "yes"}))
    with pytest.raises(ValueError):
        ModerationWorker.configured()
    # a bad configuration never takes the bot down: the service just has no AI
    service = ImageReviewService(configured=ModerationWorker.configured)
    assert asyncio.run(service.available()) is False


# ── the appearance command: AI first, human only on failure ───────
def appearance(outcome):
    cog = object.__new__(BotAppearance)
    cog.service = SimpleNamespace(add_request=lambda *a: None)
    cog.review = SimpleNamespace(
        available=AsyncMock(return_value=outcome is not None),
        review=AsyncMock(return_value=outcome),
    )
    cog.apply_change = AsyncMock()
    cog.tell_developers = AsyncMock()
    cog.bot = SimpleNamespace()
    return cog


def event():
    return SimpleNamespace(
        user=SimpleNamespace(id=7),
        guild=SimpleNamespace(id=9, name="Guild"),
        guild_id=9,
        locale=discord.Locale.taiwan_chinese,
        client=SimpleNamespace(get_guild=lambda guild_id: object()),
        edit_original_response=AsyncMock(),
    )


def attachment():
    return SimpleNamespace(
        filename="a.png", content_type="image/png", url="https://x/a.png"
    )


async def test_an_approved_image_is_applied_without_a_human():
    cog, interaction = appearance(Outcome("approved", 3)), event()
    assert await cog.review_with_ai(interaction, "avatar", attachment(), b"img") is True
    cog.apply_change.assert_awaited_once_with(9, "avatar", b"img", "image/png")
    assert (
        interaction.edit_original_response.await_count == 2
    )  # "reviewing", then "done"
    cog.tell_developers.assert_awaited_once()


async def test_a_rejected_image_is_not_applied_and_names_the_category_only():
    cog, interaction = (
        appearance(Outcome("rejected", 2, ("sexual",), "secret model text")),
        event(),
    )
    assert await cog.review_with_ai(interaction, "banner", attachment(), b"img") is True
    cog.apply_change.assert_not_awaited()
    shown = interaction.edit_original_response.await_args.kwargs["embed"].description
    assert "色情內容" in shown and "secret model text" not in shown


async def test_when_the_ai_cannot_decide_the_human_review_still_happens():
    cog, interaction = appearance(UNAVAILABLE), event()
    assert (
        await cog.review_with_ai(interaction, "avatar", attachment(), b"img") is False
    )
    cog.apply_change.assert_not_awaited()
    cog = appearance(None)  # no worker configured at all
    assert await cog.review_with_ai(event(), "avatar", attachment(), b"img") is False
    cog.review.review.assert_not_awaited()


async def test_a_failed_apply_after_approval_is_reported_not_swallowed():
    cog, interaction = appearance(Outcome("approved", 3)), event()
    cog.apply_change = AsyncMock(side_effect=RuntimeError("Forbidden"))
    assert await cog.review_with_ai(interaction, "avatar", attachment(), b"img") is True
    last = interaction.edit_original_response.await_args.kwargs["embed"].description
    assert "Forbidden" in last

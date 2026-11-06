"""BOT. checks Mori.black, the owner's shared blacklist, between its own and CatHome.

The bot keeps a copy of the whole Mori.black list, read again at most once a minute:
asking about every member who speaks would use up the token's 120 requests a minute.
"""

import asyncio
from types import SimpleNamespace

import discord
import pytest

from src.utils.blacklist_manager import BlacklistManager

USER = 123456789012345678
OTHER = 223456789012345678
MORI_URL = "https://mori.example/api/mori/v1"
FIRST_PAGE = f"{MORI_URL}/entries?limit=500"


class Session:
    """aiohttp's session for the remote blacklists: (method, url) -> (status, json)."""

    def __init__(self, routes, gate=None):
        self.routes = routes
        self.calls = []
        self.gate = gate  # holds the first list read while it is being answered

    def _respond(self, method, url, headers):
        self.calls.append((method, url, dict(headers)))
        status, body = self.routes.get((method, url), (404, {}))
        gate = self.gate if method == "GET" and "/entries?" in url else None
        if gate:
            self.gate = None

        class Response:
            def __init__(self):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def json(self, content_type=None):
                if gate:
                    await gate.wait()
                return body

            def raise_for_status(self):
                if status >= 400:
                    raise RuntimeError(f"HTTP {status}")

        return Response()

    def get(self, url, headers):
        return self._respond("GET", url, headers)

    def delete(self, url, headers):
        return self._respond("DELETE", url, headers)


def manager(routes, mori=True, cathome=True, gate=None):
    made = BlacklistManager(
        "cat-key" if cathome else None,
        "https://cat.example/v1/blacklist" if cathome else None,
        mori_token="mb_test" if mori else None,
        mori_url=MORI_URL,
    )
    made.session = Session(routes, gate)
    made.local_check = lambda user_id: None
    return made


def page(entries, next_cursor=None):
    return (200, {"entries": entries, "next_cursor": next_cursor})


BANNED = [
    {
        "id": "7",
        "user_id": str(USER),
        "mode": "block",
        "reason": "spam",
        "source": "botA",
    },
    {
        "id": "9",
        "user_id": str(USER),
        "mode": "global_ban",
        "reason": "raids",
        "source": "botB",
    },
]


@pytest.fixture(autouse=True)
def inline_storage(monkeypatch):
    from src.utils import blacklist_manager as module

    async def run_now(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(module, "run_storage", run_now)


async def test_the_whole_list_is_read_once_and_the_most_severe_mode_wins():
    made = manager({("GET", FIRST_PAGE): page(BANNED)})
    assert await made.mori_check(USER) == {
        "user_id": str(USER),
        "mode": "global_ban",
        "reason": "raids",
        "entry_ids": ["7", "9"],
        "reported_by": "botB",
    }
    assert await made.mori_check(OTHER) is None
    assert len(made.session.calls) == 1
    assert made.session.calls[0][2] == {"Authorization": "Bearer mb_test"}


async def test_many_members_speaking_cost_one_request_a_minute():
    made = manager({("GET", FIRST_PAGE): page(BANNED)})
    await asyncio.gather(*(made.mori_check(100000000000000000 + i) for i in range(500)))
    assert len(made.session.calls) == 1  # far under the 120 a minute
    made._mori_synced_at -= BlacklistManager.MORI_SYNC_SECONDS
    await made.mori_check(USER)
    assert len(made.session.calls) == 2  # read again once it is a minute old


async def test_every_page_of_the_list_is_read():
    second = f"{FIRST_PAGE}&cursor=9"
    made = manager(
        {
            ("GET", FIRST_PAGE): page(BANNED, next_cursor="9"),
            ("GET", second): page(
                [{"id": "10", "user_id": str(OTHER), "mode": "block", "reason": "x"}]
            ),
        }
    )
    assert (await made.mori_check(OTHER))["mode"] == "block"
    assert (await made.mori_check(USER))["mode"] == "global_ban"


async def test_an_outage_keeps_the_last_list_and_backs_off():
    made = manager({("GET", FIRST_PAGE): page(BANNED)})
    await made.mori_check(USER)
    made.session.routes[("GET", FIRST_PAGE)] = (503, {})
    made._mori_synced_at -= BlacklistManager.MORI_SYNC_SECONDS
    assert (await made.mori_check(USER))["mode"] == "global_ban"  # still known
    await made.mori_check(USER)
    assert len(made.session.calls) == 2  # left alone after the failure


async def test_the_check_order_is_local_then_mori_black_then_cathome():
    cat = ("GET", f"https://cat.example/v1/blacklist/{USER}")
    cat_item = (200, {"item": {"mode": "block", "reason": "cat"}})
    both = manager({("GET", FIRST_PAGE): page(BANNED), cat: cat_item})
    found = await both.check(USER)
    assert (found["source"], found["mode"]) == ("mori", "global_ban")

    only_cat = manager({("GET", FIRST_PAGE): page([]), cat: cat_item})
    found = await only_cat.check(USER)
    assert (found["source"], found["reason"]) == ("api", "cat")

    local = manager({("GET", FIRST_PAGE): page(BANNED)})
    local.local_check = lambda user_id: {"mode": "block", "reason": "ours"}
    assert (await local.check(USER))["source"] == "local"
    assert local.session.calls == []


async def test_without_a_token_mori_black_is_skipped():
    made = manager({}, mori=False, cathome=False)
    assert await made.check(USER) is None
    assert made.session.calls == []


async def test_a_block_from_either_source_is_used_without_waiting_for_the_other(
    monkeypatch,
):
    made = manager({})

    async def slow(*args):
        await asyncio.sleep(5)
        return None

    async def cat_blocks(source, user_id):
        return {"mode": "global_ban", "reason": "cat"}

    monkeypatch.setattr(made, "mori_check", slow)
    monkeypatch.setattr(made, "_remote", cat_blocks)
    found = await asyncio.wait_for(made.check(USER), timeout=0.5)
    assert found["source"] == "api"

    async def mori_blocks(user_id):
        return {"mode": "block", "reason": "mori"}

    monkeypatch.setattr(made, "mori_check", mori_blocks)
    monkeypatch.setattr(made, "_remote", slow)
    found = await asyncio.wait_for(made.check(USER), timeout=0.5)
    assert found["source"] == "mori"


async def test_an_accepted_appeal_revokes_every_entry_even_if_one_fails():
    made = manager(
        {
            ("GET", FIRST_PAGE): page(BANNED),
            ("GET", f"{MORI_URL}/users/{USER}"): (200, {"entries": BANNED}),
            ("DELETE", f"{MORI_URL}/entries/7"): (200, {"revoked": True}),
            ("DELETE", f"{MORI_URL}/entries/9"): (503, {}),
        }
    )
    await made.mori_check(USER)
    with pytest.raises(RuntimeError):
        await made.mori_revoke(USER, ["7", "9"])
    assert await made.mori_check(USER) is None  # not blocked here any more
    made.session.routes[("DELETE", f"{MORI_URL}/entries/9")] = (404, {})
    assert await made.mori_revoke(USER, ["7", "9"]) == 1  # 7 again, 9 already gone


async def test_a_sync_from_before_a_revoke_cannot_bring_the_entries_back():
    gate = asyncio.Event()
    made = manager(
        {
            ("GET", FIRST_PAGE): page(BANNED),
            ("GET", f"{MORI_URL}/users/{USER}"): (200, {"entries": BANNED}),
            ("DELETE", f"{MORI_URL}/entries/7"): (200, {}),
            ("DELETE", f"{MORI_URL}/entries/9"): (200, {}),
        },
        gate=gate,
    )
    reading = asyncio.ensure_future(made.mori_check(USER))
    await asyncio.sleep(0.01)  # the sync has asked and waits on the answer
    assert await made.mori_revoke(USER, ["7", "9"]) == 2
    gate.set()
    assert await reading is None
    assert await made.mori_check(USER) is None


async def test_revoking_without_a_token_is_an_error_not_a_success():
    made = manager({}, mori=False)
    with pytest.raises(RuntimeError):
        await made.mori_revoke(USER, ["7"])


async def test_an_appeal_revokes_only_the_entries_it_was_filed_about():
    later = {"id": "11", "user_id": str(USER), "mode": "global_ban", "reason": "new"}
    made = manager(
        {
            ("GET", FIRST_PAGE): page(BANNED + [later]),
            ("DELETE", f"{MORI_URL}/entries/7"): (200, {}),
            ("DELETE", f"{MORI_URL}/entries/9"): (200, {}),
        }
    )
    await made.mori_check(USER)
    assert await made.mori_revoke(USER, ["7", "9"]) == 2
    deleted = [c[1] for c in made.session.calls if c[0] == "DELETE"]
    assert all(not url.endswith("/11") for url in deleted)
    still = await made.mori_check(USER)
    assert (still["mode"], still["entry_ids"]) == ("global_ban", ["11"])


def test_an_appeal_keeps_the_entry_ids_it_was_filed_about():
    made = manager({})
    made.save_appeals = lambda appeals: saved.update(appeals)
    made.load_appeals = lambda: {}
    saved = {}
    assert made.add_appeal(USER, "raids", source="mori", entry_ids=["7", "9"])
    assert saved[str(USER)]["entry_ids"] == ["7", "9"]


def test_people_see_mori_black_named_as_the_source():
    from src.bot import blacklist_embed
    from src.services.blacklist_service import BlacklistService
    from src.services.blacklist_service import source_label

    assert source_label("mori") == "Mori.black"
    assert source_label("local") != source_label("api")
    embed = blacklist_embed("zh", {"source": "mori", "reason": "raids"})
    assert "Mori.black" in embed.description
    service = BlacklistService()
    accepted = service.build_notify_embed(accepted=True, source="mori")
    pending = service.build_notify_embed(accepted=True, source="mori_pending")
    assert "Mori.black" in accepted.description and "Mori.black" in pending.description
    assert accepted.description != pending.description
    review = service.build_review_embed(
        SimpleNamespace(id=USER, __str__=lambda self: "x"),
        {"source": "mori", "reason": "raids", "mode": "global_ban"},
    )
    assert any(field.value == "Mori.black" for field in review.fields)
    assert isinstance(review, discord.Embed)

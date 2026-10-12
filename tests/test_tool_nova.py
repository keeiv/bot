"""Private entitlement isolation, preserved account state and Discord parsing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.cogs.features.file_tools import FileToolsCog
from src.config.constants import DEVELOPER_IDS
from src.services.language_service import language_service
from src.services.tool_card import usage_card
from src.services.tool_quota import MIB
from src.services.tool_quota import TIERS
from src.services.tool_quota import ToolQuota

OWNER = next(iter(DEVELOPER_IDS))


def test_default_nova_is_private_and_exactly_twenty_times_ultra(tmp_path):
    quota = ToolQuota(tmp_path / "quota.db")
    for developer in DEVELOPER_IDS:
        state = quota.snapshot(developer)
        assert state["tier"]["name"] == "Nova 20x."
        assert state["weekly"]["limit"] == 20 * TIERS[-1]["weekly"]
        assert state["rolling"]["limit"] == 20 * TIERS[-1]["rolling"]
        assert state["tier"]["batch"] == TIERS[-1]["batch"]
        assert state["tier"]["max_mb"] == TIERS[-1]["max_mb"]
        assert state["nextTier"] is None and state["nextUnlockAt"] is None
        assert [t["name"] for t in state["tiers"]] == [t["name"] for t in TIERS]
        assert usage_card(state).getbuffer().nbytes > 0
        with pytest.raises(ValueError):
            quota.quote(developer, [64 * MIB + 1], "compress")
    assert quota.snapshot("123")["tier"]["name"] == "Free."


def test_grant_persists_without_developer_privilege_or_erasing_state(tmp_path):
    now = [1800000000.0]
    path = tmp_path / "quota.db"
    quota = ToolQuota(path, clock=lambda: now[0])
    original = quota.snapshot("123")
    job = quota.reserve("123", quota.quote("123", [1], "png"))
    quota.finish("123", job, 0.1, True)
    quota.admin(OWNER, "issue", "coupon", ["123"])
    state = quota.set_nova(OWNER, "123", event_id="grant")
    assert state["weekly"]["used"] == 1 and state["coupons"] == 1
    assert state["firstSeen"] == original["firstSeen"]
    now[0] += 10 * 86400
    assert (
        ToolQuota(path, clock=lambda: now[0]).snapshot("123")["tier"]["name"]
        == "Nova 20x."
    )
    for operation in (
        lambda: quota.set_nova("123", "124"),
        lambda: quota.set_test_tier("123", "Ultra."),
        lambda: quota.admin("123", "reset", "unauthorized"),
    ):
        with pytest.raises(PermissionError):
            operation()
    quota.set_nova(OWNER, "123", False, "revoke")
    # Re-delivering an old grant cannot undo a newer revocation.
    assert quota.set_nova(OWNER, "123", event_id="grant")["tier"]["name"] == "Free."
    with pytest.raises(ValueError):
        quota.set_nova(OWNER, "124", event_id="grant")
    state = quota.snapshot("123")
    assert state["firstSeen"] == original["firstSeen"] and state["coupons"] == 1
    assert quota.jobs("123")[0]["points"] == 1
    now[0] = original["firstSeen"] + 180 * 86400
    assert quota.snapshot("123")["tier"]["name"] == "Ultra."
    with pytest.raises(ValueError):
        quota.set_nova(OWNER, OWNER, False)
    assert quota.snapshot(OWNER)["tier"]["name"] == "Nova 20x."


@pytest.mark.parametrize(
    "command",
    [
        ">>>ireset",
        ">>>reset",
        ">>>ureset 123",
        ">>>sreset 999",
        ">>>nova 123",
        ">>>unova 123",
    ],
)
async def test_discord_no_space_commands_and_reply_only_to_request(command, tmp_path):
    language_service().set_user_lang(OWNER, "zh")  # a Chinese-speaking developer
    quota = ToolQuota(tmp_path / "quota.db")
    quota.register("123")
    guild = SimpleNamespace(
        id=999, chunk=AsyncMock(return_value=[SimpleNamespace(id=123, bot=False)])
    )
    cog = FileToolsCog.__new__(FileToolsCog)
    cog.engine = SimpleNamespace(quota=quota)
    cog.bot = SimpleNamespace(guilds=[guild], get_guild=lambda _: guild)
    message = SimpleNamespace(
        guild=None,
        author=SimpleNamespace(bot=False, id=OWNER),
        content=command,
        id=123456,
        reply=AsyncMock(),
    )
    await cog.on_message(message)
    assert message.reply.await_count == 1
    response = message.reply.call_args.args[0]
    assert "完成" in response or "已更新" in response
    if command == ">>>ireset":
        assert quota.inventory("123")["total"] == 1
        await cog.on_message(message)
        assert quota.inventory("123")["total"] == 1


async def test_spaced_prefix_is_not_a_command_and_non_developer_is_rejected(tmp_path):
    language_service().set_user_lang(OWNER, "zh")
    language_service().set_user_lang(123, "zh")
    quota = ToolQuota(tmp_path / "quota.db")
    cog = FileToolsCog.__new__(FileToolsCog)
    cog.engine = SimpleNamespace(quota=quota)
    cog.bot = SimpleNamespace(guilds=[])
    message = SimpleNamespace(
        guild=None,
        author=SimpleNamespace(bot=False, id=OWNER),
        content=">>> ireset",
        id=1,
        reply=AsyncMock(),
    )
    await cog.on_message(message)
    message.reply.assert_not_awaited()
    message.content = ">>>nova 124"
    message.author.id = 123
    await cog.on_message(message)
    assert "僅限開發者" in message.reply.call_args.args[0]
    assert quota.snapshot("124")["tier"]["name"] == "Free."


def test_revocation_between_estimate_and_reservation_requires_new_quote(tmp_path):
    quota = ToolQuota(tmp_path / "quota.db")
    quota.set_nova(OWNER, "123")
    quote = quota.quote("123", [MIB * 3], "compress")
    quota.set_nova(OWNER, "123", False)
    with pytest.raises(ValueError, match="等級已更新"):
        quota.reserve("123", quote)
    assert quota.snapshot("123")["reserved"] == 0
    with pytest.raises(ValueError, match="檔案大小"):
        quota.quote("123", [MIB * 3], "compress")

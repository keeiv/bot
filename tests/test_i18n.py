"""English/Chinese support: catalogue, command localizations, language rules.

Cog modules are inspected with ``ast`` instead of being imported where possible;
loading cogs starts background work that tests must not trigger.
"""

import ast
import asyncio
from pathlib import Path
import string
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import discord
from discord import app_commands
import pytest

from src.locales import MESSAGES
from src.locales.commands import CONTEXT_MENU_NAMES
from src.locales.commands import TEXT
from src.locales.help import CATEGORIES
from src.services import language_service as language_module
from src.services.language_service import LanguageService
from src.utils.command_translator import CommandTranslator
from src.utils.i18n import from_locale
from src.utils.i18n import LANGS
from src.utils.i18n import t
from src.utils.lang_context import _resolve

COGS = Path(__file__).resolve().parents[1] / "src" / "cogs"
APP_COMMAND_CALLS = {"command", "hybrid_command", "Group", "group", "hybrid_group"}


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _command_metadata():
    """Every literal description / describe() / Choice name of an app command."""
    for path in sorted(COGS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else ""
            owner = getattr(getattr(func, "value", None), "id", "")
            # commands.command / commands.group are prefix-only: no slash metadata.
            prefix_only = owner == "commands" and name in ("command", "group")
            if name in APP_COMMAND_CALLS and not prefix_only:
                keywords = [k for k in node.keywords if k.arg == "description"]
            elif name == "describe":
                keywords = node.keywords
            elif name == "Choice":
                keywords = [k for k in node.keywords if k.arg == "name"]
            else:
                continue
            for keyword in keywords:
                value = keyword.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    yield f"{path.name}:{node.lineno}", value.value


def _context_menu_names():
    for path in sorted(COGS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "ContextMenu"
            ):
                for keyword in node.keywords:
                    if keyword.arg == "name":
                        yield keyword.value.value


# ── message catalogue ─────────────────────────────────────────────
@pytest.mark.parametrize("key", sorted(MESSAGES))
def test_every_message_has_both_languages_with_same_placeholders(key):
    entry = MESSAGES[key]
    assert set(entry) == set(LANGS)
    assert entry["en"].strip() and entry["zh"].strip()
    assert _fields(entry["en"]) == _fields(entry["zh"])


def test_t_falls_back_and_formats():
    assert t("zh", "language.server_set", language="中文")
    assert "{" not in t("en", "translate.title", target="Japanese")
    with pytest.raises(KeyError):
        t("en", "no.such.key")


def test_help_sections_match_between_languages():
    zh = [c.key for c in CATEGORIES["zh"]]
    en = [c.key for c in CATEGORIES["en"]]
    assert zh == en and "overview" in zh
    for zh_cat, en_cat in zip(CATEGORIES["zh"], CATEGORIES["en"]):
        assert len(zh_cat.blocks) == len(en_cat.blocks), zh_cat.key
        # Select menu limits.
        for cat in (zh_cat, en_cat):
            assert len(cat.label) <= 100 and len(cat.description) <= 100


# ── command localizations ─────────────────────────────────────────
def test_command_metadata_is_english_and_translated():
    missing, chinese = [], []
    for where, text in _command_metadata():
        if _has_cjk(text):
            chinese.append((where, text))
        elif text not in TEXT:
            missing.append((where, text))
    assert not chinese, chinese
    assert not missing, missing


def test_translations_fit_discord_limits():
    for english, chinese in TEXT.items():
        assert 1 <= len(english) <= 100, english
        assert 1 <= len(chinese) <= 100, chinese


def test_context_menus_have_chinese_names():
    names = set(_context_menu_names())
    assert names == set(CONTEXT_MENU_NAMES)
    for english, chinese in CONTEXT_MENU_NAMES.items():
        assert len(english) <= 32 and len(chinese) <= 32


async def _menu_callback(interaction: discord.Interaction, message: discord.Message):
    pass


async def test_translator_only_localizes_for_chinese_clients():
    translator = CommandTranslator()
    location = app_commands.TranslationContextLocation
    desc = app_commands.TranslationContext(location.command_description, None)
    sample = next(iter(TEXT))

    assert await translator.translate(
        app_commands.locale_str(sample), discord.Locale.taiwan_chinese, desc
    ) == (TEXT[sample])
    assert (
        await translator.translate(
            app_commands.locale_str(sample), discord.Locale.japanese, desc
        )
        is None
    )

    menu = app_commands.ContextMenu(name="Report message", callback=_menu_callback)
    menu_ctx = app_commands.TranslationContext(location.command_name, menu)
    assert (
        await translator.translate(
            app_commands.locale_str("Report message"), discord.Locale.chinese, menu_ctx
        )
        == CONTEXT_MENU_NAMES["Report message"]
    )
    # Slash command names stay English for everyone.
    slash_ctx = app_commands.TranslationContext(location.command_name, object())
    assert (
        await translator.translate(
            app_commands.locale_str("help"), discord.Locale.taiwan_chinese, slash_ctx
        )
        is None
    )


# ── language rules ────────────────────────────────────────────────
@pytest.fixture
def service(monkeypatch):
    instance = LanguageService()
    monkeypatch.setattr(language_module, "_service", instance)
    return instance


def test_from_locale():
    assert from_locale(discord.Locale.taiwan_chinese) == "zh"
    assert from_locale(discord.Locale.chinese) == "zh"
    assert from_locale(discord.Locale.american_english) == "en"
    assert from_locale(None) == "en"


def test_existing_servers_keep_chinese_and_new_ones_get_english(service):
    # Before the first start records the baseline, every server is an old one.
    assert service.guild_lang(1) == "zh"
    assert service.baseline([1, 2]) == [1, 2]
    assert service.baseline([3]) == []  # only once
    assert service.guild_lang(1) == "zh"
    assert service.guild_lang(3) == "en"
    assert service.has_guild(1) and not service.has_guild(3)

    assert service.mark_new_guild(3) is True
    assert service.mark_new_guild(3) is False
    assert service.mark_new_guild(1) is False
    assert service.guild_lang(3) == "en"


def test_settings_survive_a_fresh_service(service):
    service.baseline([])
    service.set_guild_lang(5, "zh")
    service.set_user_lang(9, "zh")
    service.record_guide(5, 10, 11)
    fresh = LanguageService()
    assert fresh.guild_lang(5) == "zh"
    assert fresh.user_lang(9) == "zh"
    assert fresh.guide(5) == (10, 11)
    with pytest.raises(ValueError):
        service.set_user_lang(9, "fr")


def test_resolve_order(service):
    service.baseline([])
    service.set_guild_lang(5, "zh")
    # A server the bot is in: the server's language wins over the user's.
    service.set_user_lang(9, "en")
    assert _resolve(5, 9, discord.Locale.taiwan_chinese) == "zh"
    # Elsewhere: the user's choice, then the client language.
    assert _resolve(None, 9, discord.Locale.taiwan_chinese) == "en"
    assert _resolve(None, 8, discord.Locale.taiwan_chinese) == "zh"
    assert _resolve(None, 8, None) == "en"


# ── /language ─────────────────────────────────────────────────────
def _interaction(*, in_bot_guild: bool, manager: bool, guild_id=5):
    if in_bot_guild:
        user = MagicMock(spec=discord.Member)
        user.guild_permissions = discord.Permissions(manage_guild=manager)
    else:
        user = MagicMock(spec=discord.User)
    user.id = 9
    client = MagicMock()
    client.get_guild.return_value = MagicMock() if in_bot_guild else None
    return SimpleNamespace(
        client=client,
        guild_id=guild_id,
        guild=MagicMock(),
        user=user,
        locale=discord.Locale.american_english,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )


def _choice(value):
    return app_commands.Choice(name=value, value=value)


@pytest.fixture
def cog(service):
    from src.cogs.core.language import Language

    instance = Language(MagicMock())
    instance.refresh_guide = AsyncMock()
    return instance


async def test_language_needs_manage_server_in_a_server(cog, service):
    service.baseline([])
    interaction = _interaction(in_bot_guild=True, manager=False)
    await type(cog).language.callback(cog, interaction, _choice("zh"))
    # Acknowledged before any storage work (Discord's 3-second window).
    interaction.response.defer.assert_awaited_once()
    assert service.guild_lang(5) == "en"
    text = interaction.followup.send.await_args.args[0]
    assert text == t("en", "language.denied")


async def test_manager_changes_the_server_language(cog, service):
    service.baseline([])
    interaction = _interaction(in_bot_guild=True, manager=True)
    await type(cog).language.callback(cog, interaction, _choice("zh"))
    assert service.guild_lang(5) == "zh"
    assert service.user_lang(9) is None
    cog.refresh_guide.assert_awaited_once()


async def test_personal_app_changes_only_the_users_language(cog, service):
    service.baseline([])
    # A server where BOT. is only installed as a personal app.
    interaction = _interaction(in_bot_guild=False, manager=False)
    await type(cog).language.callback(cog, interaction, _choice("zh"))
    assert service.user_lang(9) == "zh"
    assert not service.has_guild(5)
    text = interaction.followup.send.await_args.args[0]
    assert text == t("zh", "language.personal_set", language="中文")


# ── guide posting ─────────────────────────────────────────────────
def _guild(guild_id=5, *, can_create=True, fail_send=False):
    sent = MagicMock(id=77)
    sent.edit = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 66
    channel.send = AsyncMock(
        side_effect=(
            discord.HTTPException(MagicMock(status=500), "boom") if fail_send else None
        ),
        return_value=sent,
    )
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.unavailable = False
    guild.me = MagicMock(spec=discord.Member)
    guild.me.guild_permissions = discord.Permissions(manage_channels=can_create)
    guild.create_text_channel = AsyncMock(return_value=channel)
    guild.get_channel = MagicMock(return_value=None)
    guild.system_channel = None
    guild.text_channels = []
    return guild, channel


def _bot_with(*guilds):
    bot = MagicMock()
    bot.guilds = list(guilds)
    return bot


async def test_first_start_records_existing_servers_and_posts_nothing(service):
    from src.cogs.core.language import Language

    guild, channel = _guild()
    cog = Language(_bot_with(guild))
    await cog.on_ready()
    assert service.guild_lang(5) == "zh"
    guild.create_text_channel.assert_not_awaited()
    channel.send.assert_not_awaited()


async def test_new_server_gets_an_english_guide(service):
    from src.cogs.core.language import Language

    service.baseline([])
    guild, channel = _guild()
    cog = Language(_bot_with())
    await cog.on_guild_join(guild)
    assert service.guild_lang(5) == "en"
    assert service.guide(5) == (66, 77)
    assert not service.guide_pending(5)
    assert channel.send.await_args.kwargs["embed"].title == t("en", "guide.title")
    # Joining again (kicked and re-invited) does not post a second guide.
    await cog.on_guild_join(guild)
    assert channel.send.await_count == 1


async def test_failed_guide_is_retried_and_reuses_the_channel(service):
    from src.cogs.core.language import Language

    service.baseline([])
    guild, channel = _guild(fail_send=True)
    cog = Language(_bot_with(guild))
    await cog.on_guild_join(guild)
    assert service.guide_pending(5)
    assert service.guide(5) == (66, None)

    # Next ready (restart or reconnect): the created channel is reused.
    channel.send.side_effect = None
    guild.get_channel.return_value = channel
    await cog.on_ready()
    guild.create_text_channel.assert_awaited_once()
    assert service.guide(5) == (66, 77)
    assert not service.guide_pending(5)


async def test_server_joined_while_disconnected_is_welcomed_on_reconnect(service):
    from src.cogs.core.language import Language

    old, _ = _guild(1)
    cog = Language(_bot_with(old))
    await cog.on_ready()  # first start: baseline only
    new, channel = _guild(2)
    cog.bot.guilds.append(new)
    await cog.on_ready()  # second READY after a reconnect
    assert service.guild_lang(1) == "zh"
    assert service.guild_lang(2) == "en"
    channel.send.assert_awaited_once()
    old.create_text_channel.assert_not_awaited()


async def test_lookup_returns_in_time_even_if_storage_is_already_running(
    service, monkeypatch
):
    """Real run_storage: a read already in its thread cannot be cancelled."""
    from src.utils import lang_context

    real = service.user_lang

    def slow_read(user_id):
        time.sleep(0.8)
        return real(user_id)

    monkeypatch.setattr(service, "user_lang", slow_read)
    monkeypatch.setattr(lang_context, "LOOKUP_TIMEOUT", 0.1)
    interaction = _interaction(in_bot_guild=False, manager=False)
    interaction.locale = discord.Locale.taiwan_chinese
    started = time.monotonic()
    assert await lang_context.interaction_lang(interaction) == "zh"
    assert time.monotonic() - started < 0.5
    # The abandoned read still completes and is released.
    await asyncio.gather(*lang_context._abandoned)
    assert not lang_context._abandoned


def test_language_set_before_the_welcome_keeps_the_guide_pending(service):
    service.baseline([])
    service.set_guild_lang(5, "zh")
    assert service.guide_pending(5)
    assert service.needs_welcome([5]) == [5]
    assert service.guild_lang(5) == "zh"
    # Changing it again before the guide is posted keeps it pending.
    service.set_guild_lang(5, "en")
    assert service.guide_pending(5)


def test_language_change_on_a_legacy_server_does_not_make_it_pending(service):
    service.baseline([1])
    service.set_guild_lang(1, "en")
    assert not service.guide_pending(1)
    assert service.needs_welcome([1, 2]) == [2]


async def test_concurrent_welcomes_post_one_guide(service):
    from src.cogs.core.language import Language

    service.baseline([])
    guild, channel = _guild()
    gate = asyncio.Event()

    async def slow_create(*args, **kwargs):
        await gate.wait()
        return channel

    guild.create_text_channel = AsyncMock(side_effect=slow_create)
    cog = Language(_bot_with(guild))
    first = asyncio.create_task(cog.on_guild_join(guild))
    second = asyncio.create_task(cog.on_ready())
    await asyncio.sleep(0.05)
    gate.set()
    await asyncio.gather(first, second)
    guild.create_text_channel.assert_awaited_once()
    channel.send.assert_awaited_once()
    assert service.guide(5) == (66, 77)


async def test_guide_select_defers_then_edits_after_saving(service):
    from src.cogs.core.language import GuideLanguageSelect

    service.baseline([])
    select = GuideLanguageSelect(MagicMock(), "en")
    select._values = ["zh"]
    interaction = _interaction(in_bot_guild=True, manager=True)
    interaction.guild = SimpleNamespace(id=5)
    await select.callback(interaction)
    interaction.response.defer.assert_awaited_once()
    assert service.guild_lang(5) == "zh"
    embed = interaction.edit_original_response.await_args.kwargs["embed"]
    assert embed.title == t("zh", "guide.title")


async def test_language_changed_while_the_guide_was_posting(service):
    from src.cogs.core.language import Language

    service.baseline([])
    guild, channel = _guild()
    gate = asyncio.Event()

    async def slow_create(*args, **kwargs):
        await gate.wait()
        return channel

    guild.create_text_channel = AsyncMock(side_effect=slow_create)
    cog = Language(_bot_with(guild))
    welcoming = asyncio.create_task(cog.on_guild_join(guild))
    await asyncio.sleep(0.05)
    # /language runs now: no guide message exists yet to refresh.
    service.set_guild_lang(5, "zh")
    gate.set()
    await welcoming
    message = channel.send.return_value
    assert channel.send.await_args.kwargs["embed"].title == t("en", "guide.title")
    assert message.edit.await_args.kwargs["embed"].title == t("zh", "guide.title")


async def test_cancelled_caller_still_tracks_the_lookup(service, monkeypatch):
    from src.utils import lang_context

    release = threading.Event()

    def blocked_read(user_id):
        release.wait(5)
        raise RuntimeError("storage broke")

    monkeypatch.setattr(service, "user_lang", blocked_read)
    interaction = _interaction(in_bot_guild=False, manager=False)
    caller = asyncio.create_task(lang_context.interaction_lang(interaction))
    await asyncio.sleep(0.05)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    assert len(lang_context._abandoned) == 1
    release.set()
    await asyncio.gather(*lang_context._abandoned, return_exceptions=True)
    await asyncio.sleep(0)
    assert not lang_context._abandoned


async def test_lookups_stop_queueing_when_too_many_are_stuck(service, monkeypatch):
    from src.utils import lang_context

    called = MagicMock()
    monkeypatch.setattr(lang_context, "run_storage", called)
    monkeypatch.setattr(lang_context, "_abandoned", set(range(64)))
    interaction = _interaction(in_bot_guild=False, manager=False)
    interaction.locale = discord.Locale.taiwan_chinese
    assert await lang_context.interaction_lang(interaction) == "zh"
    called.assert_not_called()


# ── /user_info and /server_info ───────────────────────────────────
def _view_text(view) -> str:
    texts = []

    def walk(item):
        content = getattr(item, "content", None)
        if isinstance(content, str):
            texts.append(content)
        description = getattr(item, "description", None)
        if isinstance(description, str):
            texts.append(description)
        for child in getattr(item, "children", []) or []:
            walk(child)
        for child in getattr(item, "items", []) or []:
            walk(child)
        accessory = getattr(item, "accessory", None)
        if accessory is not None:
            walk(accessory)

    for item in view.children:
        walk(item)
    return "\n".join(texts)


def _info_cog():
    from src.cogs.features.user_server_info import UserServerInfo

    return object.__new__(UserServerInfo)


def _fake_user():
    avatar = SimpleNamespace(url="https://example.test/a.png")
    return SimpleNamespace(
        id=1,
        name="kei",
        mention="<@1>",
        display_avatar=avatar,
        banner=SimpleNamespace(url="https://example.test/b.png"),
    )


@pytest.mark.parametrize("lang", LANGS)
def test_user_info_view_is_fully_in_one_language(lang):
    view = _info_cog().build_user_info_view(
        _fake_user(),
        "Kei",
        "2016/10/29",
        t(lang, "info.user.joined_unknown"),
        t(lang, "info.user.regular"),
        t(lang, "info.none"),
        "0/10",
        t(lang, "info.user.osu_linked", name="x"),
        "2026/10/11",
        lang,
    )
    text = _view_text(view)
    assert t(lang, "info.user.title") in text
    assert t(lang, "info.user.created") in text
    assert t(lang, "info.user.banner") in text
    if lang == "en":
        assert not _has_cjk(text), text
    else:
        assert "用戶資訊" in text and "基本資料" in text and "帳號創立時間" in text


@pytest.mark.parametrize("lang", LANGS)
def test_server_info_view_is_fully_in_one_language(lang):
    guild = SimpleNamespace(
        id=5,
        name="Test",
        member_count=3,
        icon=SimpleNamespace(url="https://example.test/i.png"),
        banner=SimpleNamespace(url="https://example.test/b.png"),
    )
    view = _info_cog().build_server_info_view(
        guild,
        "<@1> (kei)",
        "2026/01/01",
        "\n".join(t(lang, k, count=1) for k in ("info.server.members_total",)),
        "\n".join(t(lang, k, count=2) for k in ("info.server.channels_text",)),
        4,
        "Low",
        t(lang, "info.server.boost_tier", tier=1),
        "About",
        "2026/10/11",
        lang,
    )
    text = _view_text(view)
    assert t(lang, "info.server.title") in text
    assert t(lang, "info.server.members") in text
    assert t(lang, "info.server.banner") in text
    if lang == "en":
        assert not _has_cjk(text), text
    else:
        assert "伺服器資訊" in text and "成員統計" in text


def test_info_chinese_text_is_the_original_wording():
    # Chinese servers must see exactly what they saw before.
    assert t("zh", "info.user.title") == "用戶資訊"
    assert t("zh", "info.user.status_line", status="普通用戶") == "狀態：普通用戶"
    assert t("zh", "info.server.members_bots", count=2) == "Bot: 2"
    assert t("zh", "info.user.error") == "[錯誤] 無法獲取用戶資訊，請稍後重試。"


# ── defaults that used to be hard-coded Chinese ───────────────────
@pytest.mark.parametrize("lang", LANGS)
def test_empty_edit_text_is_hidden_next_to_an_image_in_both_languages(lang):
    from src.services.message_log_service import MessageLogService
    from src.utils.i18n import language_scope

    service = MessageLogService.__new__(MessageLogService)
    with language_scope(lang):
        embed = service.build_edit_embed(
            1,
            2,
            3,
            4,
            "kei",
            "guild",
            "",
            "",
            1,
            before_attachments=["https://cdn.example.test/a.png"],
            after_attachments=["https://cdn.example.test/b.png"],
        )
    names = [field.name for field in embed.fields]
    assert t(lang, "message_log_service.before_edit_text") not in names
    assert t(lang, "message_log_service.after_edit_text") not in names


def _command_defaults(path: str, function: str) -> dict[str, object]:
    tree = ast.parse((COGS / path).read_text(encoding="utf-8"))
    found: dict[str, object] = {}
    # A cog can have several functions with this name (e.g. the module-level
    # ``setup(bot)`` next to a ``setup`` command); the one with the parameter wins.
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function:
            args = node.args
            pairs = zip(args.args[len(args.args) - len(args.defaults) :], args.defaults)
            for arg, default in pairs:
                if isinstance(default, ast.Constant):
                    found[arg.arg] = default.value
    assert found, function
    return found


@pytest.mark.parametrize(
    "path, function, parameter",
    [
        ("core/admin.py", "kick", "reason"),
        ("core/admin.py", "ban", "reason"),
        ("core/admin.py", "mute", "reason"),
        ("core/admin.py", "warn", "reason"),
        ("features/management.py", "welcome_setup", "message"),
        ("features/temp_voice.py", "setup", "name_template"),
    ],
)
def test_command_defaults_are_resolved_per_language_not_hard_coded(
    path, function, parameter
):
    defaults = _command_defaults(path, function)
    assert defaults[parameter] is None, defaults[parameter]


def test_language_defaults_have_both_languages():
    assert t("en", "admin.no_reason_given") == "No reason given"
    assert t("zh", "admin.no_reason_given") == "沒有提供原因"
    assert t("zh", "management.welcome_to") == "歡迎 {user} 來到 {server}！"
    assert t("zh", "temp_voice.s_room") == "{username}的家"
    assert t("en", "temp_voice.s_room") == "{username}'s room"


# ── catalogue coverage ────────────────────────────────────────────
def _literal_keys_used():
    src = COGS.parent
    for path in sorted(src.rglob("*.py")):
        if "locales" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            if name in ("tx", "text") and node.args:
                arg = node.args[0]
            elif name == "t" and len(node.args) >= 2:
                arg = node.args[1]
            else:
                continue
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield f"{path.name}:{node.lineno}", arg.value


def test_every_message_key_used_in_code_exists():
    missing = [
        (where, key) for where, key in _literal_keys_used() if key not in MESSAGES
    ]
    assert not missing, missing


def test_dynamic_keys_are_covered():
    from src.cogs.core.settings import SETTING_CATEGORIES
    from src.services.achievement_service import ACHIEVEMENTS

    keys = []
    for achievement_id, achievement in ACHIEVEMENTS.items():
        keys += [
            f"achievement.{achievement_id}.name",
            f"achievement.{achievement_id}.description",
            f"rarity.{achievement['rarity']}",
        ]
    for category in SETTING_CATEGORIES:
        keys += [
            f"settings.category.{category}",
            f"settings.category.{category}.description",
        ]
    assert [key for key in keys if key not in MESSAGES] == []
    # Select menu option limits (label and description: 100 characters).
    for category in SETTING_CATEGORIES:
        for suffix in ("", ".description"):
            entry = MESSAGES[f"settings.category.{category}{suffix}"]
            assert all(len(text) <= 100 for text in entry.values())

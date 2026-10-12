"""Decide which language to answer in.

Rules, in order:
1. In a server the bot is a member of, the server's language (set by its admins).
2. Everywhere else (DMs, group DMs, servers where only the personal app is used),
   the user's own choice from ``/language``.
3. With no choice stored, the user's Discord client language.

Lookups share the serialized storage queue with every other feature. Discord
only waits 3 seconds for an interaction's first reply, so a lookup that takes
longer than ``LOOKUP_TIMEOUT`` (or fails) falls back to the client language
instead of making the interaction fail.

``interaction.guild`` cannot be used for rule 1: for a personal-app command in a
server the bot is not in, discord.py returns a partial guild built from the
interaction. Only ``client.get_guild`` proves the bot is actually there.
"""

import asyncio
from functools import wraps
import inspect
import logging
from typing import Any, Optional

import discord

from src.services.language_service import language_service
from src.utils.i18n import from_locale
from src.utils.i18n import Lang
from src.utils.i18n import language_scope
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

LOOKUP_TIMEOUT = 1.5
# While this many lookups are still stuck in storage, answer from the client
# language without queueing more.
MAX_ABANDONED = 64

# Lookups given up on keep running (storage finishes what it started); hold a
# reference so they are not garbage-collected mid-flight.
_abandoned: set["asyncio.Task[Lang]"] = set()


def _abandon(task: "asyncio.Task[Lang]") -> None:
    _abandoned.add(task)
    task.add_done_callback(_forget)


def _forget(task: "asyncio.Task[Lang]") -> None:
    _abandoned.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.warning("Abandoned language lookup failed: %r", task.exception())


def bot_guild_id(client: discord.Client, guild_id: Optional[int]) -> Optional[int]:
    """The server id if the bot is a member of it, otherwise None."""
    if guild_id is None or client.get_guild(guild_id) is None:
        return None
    return guild_id


def _resolve(
    guild_id: Optional[int], user_id: int, locale: Optional[discord.Locale]
) -> Lang:
    service = language_service()
    if guild_id is not None:
        return service.guild_lang(guild_id)
    return service.user_lang(user_id) or from_locale(locale)


async def _lookup(
    guild_id: Optional[int],
    user_id: int,
    locale: Optional[discord.Locale],
    *,
    timeout: Optional[float] = None,
) -> Lang:
    cached, lang = language_service().cached_language(guild_id, user_id)
    if cached:
        return lang or from_locale(locale)
    if len(_abandoned) >= MAX_ABANDONED:
        return from_locale(locale)
    # Not wait_for: cancelling run_storage waits for its thread to finish, which
    # can take longer than the timeout. Stop waiting instead and let it finish.
    task = asyncio.ensure_future(run_storage(_resolve, guild_id, user_id, locale))
    try:
        done, _ = await asyncio.wait(
            {task}, timeout=LOOKUP_TIMEOUT if timeout is None else timeout
        )
    except asyncio.CancelledError:
        _abandon(task)
        raise
    if not done:
        _abandon(task)
        logger.warning("Language lookup timed out; using the client language")
        return from_locale(locale)
    try:
        lang: Lang = task.result()
    except Exception:
        logger.warning("Language lookup failed; using the client language")
        return from_locale(locale)
    return lang


async def interaction_lang(
    interaction: discord.Interaction, *, timeout: Optional[float] = None
) -> Lang:
    guild_id = bot_guild_id(interaction.client, interaction.guild_id)
    return await _lookup(
        guild_id, interaction.user.id, interaction.locale, timeout=timeout
    )


async def context_lang(ctx: Any) -> Lang:
    """Language for a hybrid/prefix command context."""
    if getattr(ctx, "interaction", None) is not None:
        return await interaction_lang(ctx.interaction)
    guild = getattr(ctx, "guild", None)
    guild_id = guild.id if guild is not None else None
    return await _lookup(guild_id, ctx.author.id, None)


async def message_lang(guild: Optional[discord.Guild], user_id: int) -> Lang:
    """Language for replying to a plain message (no interaction locale known)."""
    guild_id = guild.id if guild is not None else None
    return await _lookup(guild_id, user_id, None)


async def guild_lang(guild: discord.Guild) -> Lang:
    """Language of a scheduled notification addressed to a server."""
    return await _lookup(guild.id, 0, None)


async def guild_language(guild_id: int) -> Lang:
    """Resolve a server's language when only its stored id is available."""
    return await _lookup(int(guild_id), 0, None)


def localized(parameter: Optional[str] = None):
    """Scope a Discord entry point's copy without sharing state between users.

    ``parameter`` identifies an interaction, command context, message, member
    or guild. With no parameter, a view timeout uses its creation language.
    Storage waits before an initial interaction response are limited to 350 ms;
    fresh choices use the nonblocking cache. Existing deferred commands may
    still resolve their language explicitly after acknowledging Discord.
    """

    def decorate(function):
        signature = inspect.signature(function, eval_str=True)

        @wraps(function)
        async def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            if parameter is None:
                lang = bound.arguments["self"].lang
            else:
                source = bound.arguments[parameter]
                if parameter == "interaction":
                    lang = await interaction_lang(source, timeout=0.35)
                elif parameter in {"ctx", "context"}:
                    lang = await context_lang(source)
                elif parameter == "guild_id":
                    lang = await guild_language(source)
                elif parameter in {"user_id", "discord_user_id"}:
                    lang = await message_lang(None, int(source))
                elif parameter == "message" or hasattr(source, "author"):
                    lang = await message_lang(source.guild, source.author.id)
                elif parameter == "guild":
                    lang = await guild_lang(source)
                else:
                    lang = await message_lang(source.guild, source.id)
            with language_scope(lang):
                return await function(*args, **kwargs)

        # Discord resolves callback annotations in the callback's global scope.
        # Resolving here also supports cogs that use postponed annotations.
        wrapped.__annotations__ = {
            name: value.annotation
            for name, value in signature.parameters.items()
            if value.annotation is not inspect.Signature.empty
        }
        if signature.return_annotation is not inspect.Signature.empty:
            wrapped.__annotations__["return"] = signature.return_annotation
        return wrapped

    return decorate

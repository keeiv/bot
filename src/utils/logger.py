from datetime import datetime
from typing import Any, Optional

import discord

from src.utils.i18n import text as tx
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET


def is_image_or_gif(url: str) -> bool:
    """Check whether a link is an image or a GIF."""
    if not url:
        return False
    url_lower = url.lower()
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
    return any(url_lower.endswith(ext) for ext in image_extensions) or any(
        ext in url_lower for ext in ("media", "image", "cdn")
    )


def get_first_image_url(attachment_urls: list[Any]) -> Optional[str]:
    """The first image or GIF URL in a list of attachment URLs."""
    if not attachment_urls:
        return None
    for url in attachment_urls:
        if is_image_or_gif(url):
            result_value = url
            if result_value is None:
                return None
            if not isinstance(result_value, str):
                raise TypeError("Unexpected stored or API value: expected str")
            return result_value
    return None


def create_edit_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    message_id: int,
    before_content: str,
    after_content: str,
    edit_count: int = 1,
    before_attachments: list[Any] | None = None,
    after_attachments: list[Any] | None = None,
) -> discord.Embed:
    """Build the embed for an edited message."""
    embed = discord.Embed(
        title=tx("message_log_service.edited_message_edited"),
        color=discord.Color.from_rgb(52, 152, 219),
        timestamp=datetime.now(TZ_OFFSET),
    )

    # Add the basic information
    embed.add_field(
        name=tx("audit_log.user"), value=f"<@{user_id}> ({user_id})", inline=False
    )
    embed.add_field(
        name=tx("bot_appearance.server"),
        value=f"{guild_name} ({guild_id})",
        inline=False,
    )
    embed.add_field(
        name=tx("audit_log.channel"),
        value=f"<#{channel_id}> ({channel_id})",
        inline=False,
    )
    embed.add_field(name=tx("protection.28"), value=str(message_id), inline=False)

    # Check the attachments from before the edit
    before_image_url = (
        get_first_image_url(before_attachments) if before_attachments else None
    )

    # Add the content from before the edit
    if before_image_url:
        # With an image, no code block
        before_text = (
            before_content[:1024] if before_content else tx("message_log_service.empty")
        )
        if before_text and before_text != tx("message_log_service.empty"):
            embed.add_field(
                name=tx("message_log_service.before_edit_text"),
                value=before_text,
                inline=False,
            )
    else:
        # With no image, wrap the text in a code block
        before_text = (
            before_content[:1024] if before_content else tx("message_log_service.empty")
        )
        embed.add_field(
            name=tx("message_log_service.before_edit"),
            value=f"```\n{before_text}\n```",
            inline=False,
        )

    # Check the attachments from after the edit
    after_image_url = (
        get_first_image_url(after_attachments) if after_attachments else None
    )

    # Add the content from after the edit
    if after_image_url:
        # With an image, no code block
        after_text = (
            after_content[:1024] if after_content else tx("message_log_service.empty")
        )
        if after_text and after_text != tx("message_log_service.empty"):
            embed.add_field(
                name=tx("message_log_service.after_edit_text"),
                value=after_text,
                inline=False,
            )
    else:
        # With no image, wrap the text in a code block
        after_text = (
            after_content[:1024] if after_content else tx("message_log_service.empty")
        )
        embed.add_field(
            name=tx("message_log_service.after_edit"),
            value=f"```\n{after_text}\n```",
            inline=False,
        )

    # If the edited message has an image, add it to the embed
    if after_image_url:
        embed.set_image(url=after_image_url)

    embed.add_field(
        name=tx("message_log_service.edit_count"), value=str(edit_count), inline=True
    )
    embed.add_field(
        name=tx("audit_log.time"), value=get_current_time_str(), inline=True
    )

    embed.set_footer(text=tx("audit_log.user_941f2d", v0=(user_name)))

    return embed


def create_delete_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    message_id: int,
    content: str,
    attachments: list[Any] | None = None,
) -> discord.Embed:
    """Build the embed for a deleted message."""
    embed = discord.Embed(
        title=tx("message_log_service.deleted_message_deleted"),
        color=discord.Color.from_rgb(231, 76, 60),
        timestamp=datetime.now(TZ_OFFSET),
    )

    # Add the basic information
    embed.add_field(
        name=tx("audit_log.user"), value=f"<@{user_id}> ({user_id})", inline=False
    )
    embed.add_field(
        name=tx("bot_appearance.server"),
        value=f"{guild_name} ({guild_id})",
        inline=False,
    )
    embed.add_field(
        name=tx("audit_log.channel"),
        value=f"<#{channel_id}> ({channel_id})",
        inline=False,
    )
    embed.add_field(
        name=tx("message_log_service.message_id"), value=str(message_id), inline=False
    )

    # Check for an image attachment
    image_url = get_first_image_url(attachments) if attachments else None

    # Add the message content from before the deletion
    if image_url:
        # With an image, no code block
        content_text = content[:1024] if content else tx("message_log_service.empty")
        if content_text and content_text != tx("message_log_service.empty"):
            embed.add_field(
                name=tx("message_log_service.before_deletion_text"),
                value=content_text,
                inline=False,
            )
    else:
        # With no image, wrap the text in a code block
        content_text = content[:1024] if content else tx("message_log_service.empty")
        embed.add_field(
            name=tx("message_log_service.message_before_deletion"),
            value=f"```\n{content_text}\n```",
            inline=False,
        )

    # If there is an image, add it to the embed
    if image_url:
        embed.set_image(url=image_url)

    embed.add_field(
        name=tx("audit_log.time"), value=get_current_time_str(), inline=True
    )

    embed.set_footer(text=tx("audit_log.user_941f2d", v0=(user_name)))

    return embed

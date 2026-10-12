from datetime import datetime
from typing import Any, Optional

import discord

from src.utils.i18n import text as tx
from src.utils.time_utils import get_current_time_str
from src.utils.time_utils import TZ_OFFSET


def is_image_or_gif(url: str) -> bool:
    """檢查連結是否為圖片或 GIF"""
    if not url:
        return False
    url_lower = url.lower()
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
    return any(url_lower.endswith(ext) for ext in image_extensions) or any(
        ext in url_lower for ext in ("media", "image", "cdn")
    )


def get_first_image_url(attachment_urls: list[Any]) -> Optional[str]:
    """從附件 URL 列表中取得第一個圖片或 GIF 的 URL"""
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
    """建立編輯訊息的 Embed"""
    embed = discord.Embed(
        title=tx("message_log_service.edited_message_edited"),
        color=discord.Color.from_rgb(52, 152, 219),
        timestamp=datetime.now(TZ_OFFSET),
    )

    # 新增基本資訊
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

    # 檢查編輯前的附件
    before_image_url = (
        get_first_image_url(before_attachments) if before_attachments else None
    )

    # 新增編輯前內容
    if before_image_url:
        # 如果有圖片，不用程式碼框
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
        # 如果沒有圖片，用程式碼框包裹文字
        before_text = (
            before_content[:1024] if before_content else tx("message_log_service.empty")
        )
        embed.add_field(
            name=tx("message_log_service.before_edit"),
            value=f"```\n{before_text}\n```",
            inline=False,
        )

    # 檢查編輯後的附件
    after_image_url = (
        get_first_image_url(after_attachments) if after_attachments else None
    )

    # 新增編輯後內容
    if after_image_url:
        # 如果有圖片，不用程式碼框
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
        # 如果沒有圖片，用程式碼框包裹文字
        after_text = (
            after_content[:1024] if after_content else tx("message_log_service.empty")
        )
        embed.add_field(
            name=tx("message_log_service.after_edit"),
            value=f"```\n{after_text}\n```",
            inline=False,
        )

    # 如果有編輯後的圖片，新增到 Embed
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
    """建立刪除訊息的embed"""
    embed = discord.Embed(
        title=tx("message_log_service.deleted_message_deleted"),
        color=discord.Color.from_rgb(231, 76, 60),
        timestamp=datetime.now(TZ_OFFSET),
    )

    # 新增基本資訊
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

    # 檢查是否有圖片附件
    image_url = get_first_image_url(attachments) if attachments else None

    # 新增刪除前的訊息內容
    if image_url:
        # 如果有圖片，不用代碼框
        content_text = content[:1024] if content else tx("message_log_service.empty")
        if content_text and content_text != tx("message_log_service.empty"):
            embed.add_field(
                name=tx("message_log_service.before_deletion_text"),
                value=content_text,
                inline=False,
            )
    else:
        # 如果沒有圖片，用代碼框包裹文字
        content_text = content[:1024] if content else tx("message_log_service.empty")
        embed.add_field(
            name=tx("message_log_service.message_before_deletion"),
            value=f"```\n{content_text}\n```",
            inline=False,
        )

    # 如果有圖片，新增到embed
    if image_url:
        embed.set_image(url=image_url)

    embed.add_field(
        name=tx("audit_log.time"), value=get_current_time_str(), inline=True
    )

    embed.set_footer(text=tx("audit_log.user_941f2d", v0=(user_name)))

    return embed

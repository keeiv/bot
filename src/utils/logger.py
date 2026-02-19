import discord
from datetime import datetime, timezone, timedelta
from typing import Optional

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

def get_current_time_str() -> str:
    """獲取格式化的當前時間 (月/日 時:分)"""
    now = datetime.now(TZ_OFFSET)
    return now.strftime("%m/%d %H:%M")

def is_image_or_gif(url: str) -> bool:
    """檢查連結是否為圖片或GIF"""
    if not url:
        return False
    url_lower = url.lower()
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')
    return any(url_lower.endswith(ext) for ext in image_extensions) or \
           any(ext in url_lower for ext in ('media', 'image', 'cdn'))

def get_first_image_url(attachment_urls: list) -> Optional[str]:
    """從附件URL列表中獲取第一個圖片或GIF的URL"""
    if not attachment_urls:
        return None
    for url in attachment_urls:
        if is_image_or_gif(url):
            return url
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
    before_attachments: list = None,
    after_attachments: list = None
) -> discord.Embed:
    """建立編輯訊息的embed"""
    embed = discord.Embed(
        title="[編輯] 訊息已編輯",
        color=discord.Color.from_rgb(52, 152, 219),
        timestamp=datetime.now(TZ_OFFSET)
    )
    
    # 添加基本信息
    embed.add_field(name="用戶", value=f"<@{user_id}> ({user_id})", inline=False)
    embed.add_field(name="伺服器", value=f"{guild_name} ({guild_id})", inline=False)
    embed.add_field(name="頻道", value=f"<#{channel_id}> ({channel_id})", inline=False)
    embed.add_field(name="訊息ID", value=str(message_id), inline=False)
    
    # 檢查編輯前的附件
    before_image_url = get_first_image_url(before_attachments) if before_attachments else None
    
    # 添加編輯前內容
    if before_image_url:
        # 如果有圖片，不用代碼框
        before_text = before_content[:1024] if before_content else "(空)"
        if before_text and before_text != "(空)":
            embed.add_field(name="編輯前 (文字)", value=before_text, inline=False)
    else:
        # 如果沒有圖片，用代碼框包裹文字
        before_text = before_content[:1024] if before_content else "(空)"
        embed.add_field(name="編輯前", value=f"```\n{before_text}\n```", inline=False)
    
    # 檢查編輯後的附件
    after_image_url = get_first_image_url(after_attachments) if after_attachments else None
    
    # 添加編輯後內容
    if after_image_url:
        # 如果有圖片，不用代碼框
        after_text = after_content[:1024] if after_content else "(空)"
        if after_text and after_text != "(空)":
            embed.add_field(name="編輯後 (文字)", value=after_text, inline=False)
    else:
        # 如果沒有圖片，用代碼框包裹文字
        after_text = after_content[:1024] if after_content else "(空)"
        embed.add_field(name="編輯後", value=f"```\n{after_text}\n```", inline=False)
    
    # 如果有編輯後的圖片，添加到embed
    if after_image_url:
        embed.set_image(url=after_image_url)
    
    embed.add_field(name="編輯次數", value=str(edit_count), inline=True)
    embed.add_field(name="時間", value=get_current_time_str(), inline=True)
    
    embed.set_footer(text=f"用戶 {user_name}")
    
    return embed

def create_delete_embed(
    user_id: int,
    user_name: str,
    guild_id: int,
    guild_name: str,
    channel_id: int,
    message_id: int,
    content: str,
    attachments: list = None
) -> discord.Embed:
    """建立刪除訊息的embed"""
    embed = discord.Embed(
        title="[刪除] 訊息已刪除",
        color=discord.Color.from_rgb(231, 76, 60),
        timestamp=datetime.now(TZ_OFFSET)
    )
    
    # 添加基本信息
    embed.add_field(name="用戶", value=f"<@{user_id}> ({user_id})", inline=False)
    embed.add_field(name="伺服器", value=f"{guild_name} ({guild_id})", inline=False)
    embed.add_field(name="頻道", value=f"<#{channel_id}> ({channel_id})", inline=False)
    embed.add_field(name="訊息ID", value=str(message_id), inline=False)
    
    # 檢查是否有圖片附件
    image_url = get_first_image_url(attachments) if attachments else None
    
    # 添加刪除前的訊息內容
    if image_url:
        # 如果有圖片，不用代碼框
        content_text = content[:1024] if content else "(空)"
        if content_text and content_text != "(空)":
            embed.add_field(name="刪除前的訊息 (文字)", value=content_text, inline=False)
    else:
        # 如果沒有圖片，用代碼框包裹文字
        content_text = content[:1024] if content else "(空)"
        embed.add_field(name="刪除前的訊息", value=f"```\n{content_text}\n```", inline=False)
    
    # 如果有圖片，添加到embed
    if image_url:
        embed.set_image(url=image_url)
    
    embed.add_field(name="時間", value=get_current_time_str(), inline=True)
    
    embed.set_footer(text=f"用戶 {user_name}")
    
    return embed

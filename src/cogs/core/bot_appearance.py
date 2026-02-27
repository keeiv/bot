import io

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# 開發者 ID
DEVELOPER_ID = 241619561760292866


class BotAppearance(commands.Cog):
    """機器人外觀設定 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    appearance_group = app_commands.Group(
        name="bot_appearance",
        description="機器人外觀設定",
        default_permissions=discord.Permissions(administrator=True),
    )

    @appearance_group.command(name="name", description="更改機器人在此伺服器的名稱")
    @app_commands.describe(name="新的暱稱 (留空則還原預設)")
    async def change_name(
        self, interaction: discord.Interaction, name: str = None
    ):
        """更改機器人在伺服器中的暱稱"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "[失敗] 你需要管理員權限", ephemeral=True
            )
            return

        try:
            bot_member = interaction.guild.me
            await bot_member.edit(nick=name)

            if name:
                embed = discord.Embed(
                    title="[成功] 名稱已更改",
                    description=f"機器人在此伺服器的名稱已更改為: **{name}**",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            else:
                embed = discord.Embed(
                    title="[成功] 名稱已還原",
                    description="機器人名稱已還原為預設",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            await interaction.response.send_message(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "[失敗] 機器人缺少更改暱稱的權限", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"[失敗] 無法更改名稱: {e}", ephemeral=True
            )

    @appearance_group.command(name="avatar", description="更改機器人的頭像 (全域)")
    @app_commands.describe(image="新的頭像圖片")
    async def change_avatar(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        """更改機器人頭像 (僅開發者)"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[失敗] 只有開發者可以更改機器人頭像", ephemeral=True
            )
            return

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "[失敗] 請上傳有效的圖片檔案", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            image_bytes = await image.read()
            await self.bot.user.edit(avatar=image_bytes)

            embed = discord.Embed(
                title="[成功] 頭像已更改",
                description="機器人頭像已更新",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            await interaction.followup.send(embed=embed)

        except discord.HTTPException as e:
            await interaction.followup.send(
                f"[失敗] 更改頭像失敗: {e}", ephemeral=True
            )

    @appearance_group.command(name="banner", description="更改機器人的橫幅 (全域)")
    @app_commands.describe(image="新的橫幅圖片 (留空則移除橫幅)")
    async def change_banner(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment = None,
    ):
        """更改機器人橫幅 (僅開發者)"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[失敗] 只有開發者可以更改機器人橫幅", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            if image:
                if not image.content_type or not image.content_type.startswith(
                    "image/"
                ):
                    await interaction.followup.send(
                        "[失敗] 請上傳有效的圖片檔案", ephemeral=True
                    )
                    return

                image_bytes = await image.read()
                await self.bot.user.edit(banner=image_bytes)

                embed = discord.Embed(
                    title="[成功] 橫幅已更改",
                    description="機器人橫幅已更新",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            else:
                await self.bot.user.edit(banner=None)
                embed = discord.Embed(
                    title="[成功] 橫幅已移除",
                    description="機器人橫幅已清除",
                    color=discord.Color.from_rgb(46, 204, 113),
                )

            await interaction.followup.send(embed=embed)

        except discord.HTTPException as e:
            await interaction.followup.send(
                f"[失敗] 更改橫幅失敗: {e}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(BotAppearance(bot))

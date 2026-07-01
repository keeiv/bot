"""年齡守門員 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.services.age_guard_service import AgeGuardService
from src.utils.config_manager import get_guild_log_channel

TZ_OFFSET = timezone(timedelta(hours=8))


class AgeGuard(commands.Cog):
    """年齡守門員 — 偵測成員公開宣告未成年，移除成人身份組並附加懲罰身份組"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AgeGuardService()

    age_guard = app_commands.Group(
        name="age_guard",
        description="年齡守門員設定",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @age_guard.command(
        name="set_adult_role",
        description="設定成人/18+ 身份組（偵測到未成年宣告時將被移除）",
    )
    @app_commands.describe(role="成人/18+ 身份組")
    async def set_adult_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        self.service.set_adult_role(interaction.guild_id, role.id)
        embed = discord.Embed(
            title="[成功] 成人身份組已設定",
            description=f"成人身份組已設為 {role.mention}\n偵測到未成年宣告時將自動移除此身份組。",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @age_guard.command(
        name="set_punishment_role",
        description="設定懲罰身份組（偵測到未成年宣告時附加）",
    )
    @app_commands.describe(role="懲罰身份組")
    async def set_punishment_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        self.service.set_punishment_role(interaction.guild_id, role.id)
        embed = discord.Embed(
            title="[成功] 懲罰身份組已設定",
            description=f"懲罰身份組已設為 {role.mention}\n偵測到未成年宣告時將自動附加此身份組。",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @age_guard.command(name="toggle", description="開啟或關閉年齡守門員")
    async def toggle(self, interaction: discord.Interaction) -> None:
        new_state = self.service.toggle_enabled(interaction.guild_id)
        state_str = "開啟" if new_state else "關閉"
        color = (
            discord.Color.from_rgb(46, 204, 113)
            if new_state
            else discord.Color.from_rgb(231, 76, 60)
        )
        embed = discord.Embed(
            title=f"[成功] 年齡守門員已{state_str}",
            color=color,
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @age_guard.command(name="status", description="查看年齡守門員目前設定")
    async def status(self, interaction: discord.Interaction) -> None:
        cfg = self.service.get_config(interaction.guild_id)
        enabled = cfg.get("enabled", False)
        adult_role_id = cfg.get("adult_role_id")
        punishment_role_id = cfg.get("punishment_role_id")

        adult_role = (
            interaction.guild.get_role(adult_role_id) if adult_role_id else None
        )
        punishment_role = (
            interaction.guild.get_role(punishment_role_id)
            if punishment_role_id
            else None
        )

        embed = discord.Embed(
            title="[設定] 年齡守門員",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="狀態", value="[啟用]" if enabled else "[停用]", inline=True
        )
        embed.add_field(
            name="成人身份組",
            value=adult_role.mention if adult_role else "[未設定]",
            inline=True,
        )
        embed.add_field(
            name="懲罰身份組",
            value=punishment_role.mention if punishment_role else "[未設定]",
            inline=True,
        )
        embed.set_footer(text=f"伺服器: {interaction.guild.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """監聽訊息，偵測未成年年齡宣告"""
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return

        cfg = self.service.get_config(message.guild.id)
        if not cfg.get("enabled", False):
            return

        adult_role_id = cfg.get("adult_role_id")
        punishment_role_id = cfg.get("punishment_role_id")
        if not adult_role_id and not punishment_role_id:
            return

        age = self.service.detect_underage(message.content or "")
        if age is None:
            return

        member = message.author
        guild = message.guild
        adult_role = guild.get_role(adult_role_id) if adult_role_id else None
        punishment_role = (
            guild.get_role(punishment_role_id) if punishment_role_id else None
        )

        actions_taken: list[str] = []

        if adult_role is not None and adult_role in member.roles:
            try:
                await member.remove_roles(
                    adult_role, reason=f"年齡守門員: 成員宣告 {age} 歲 (未成年)"
                )
                actions_taken.append(f"移除成人身份組 {adult_role.mention}")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if punishment_role is not None and punishment_role not in member.roles:
            try:
                await member.add_roles(
                    punishment_role, reason=f"年齡守門員: 成員宣告 {age} 歲 (未成年)"
                )
                actions_taken.append(f"附加懲罰身份組 {punishment_role.mention}")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if not actions_taken:
            return

        log_channel_id = get_guild_log_channel(guild.id)
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        content = message.content or ""
        excerpt = content if len(content) <= 200 else content[:197] + "..."
        embed = discord.Embed(
            title="[年齡守門員] 偵測到未成年宣告",
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="成員", value=f"{member.mention} (`{member.id}`)", inline=True
        )
        embed.add_field(name="宣告年齡", value=str(age), inline=True)
        embed.add_field(name="頻道", value=message.channel.mention, inline=True)
        embed.add_field(name="原始訊息", value=excerpt, inline=False)
        embed.add_field(name="已執行動作", value="\n".join(actions_taken), inline=False)
        embed.set_footer(text=f"伺服器: {guild.name} | 使用者 ID: {member.id}")
        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AgeGuard(bot))

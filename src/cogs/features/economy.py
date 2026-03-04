from __future__ import annotations
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.economy_manager import economy_manager


class Economy(commands.Cog):
    """簡單經濟系統：查詢餘額、贈送、排行榜"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="查詢你的 CT 餘額")
    async def balance(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        bal = await economy_manager.get_balance(target.id)
        embed = discord.Embed(
            title="CT 餘額",
            description=f"{target.mention} 目前有 {bal} CT",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="give", description="將 CT 贈送給其他成員")
    @app_commands.describe(member="接收者", amount="數量 (正整數)")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.bot:
            await interaction.response.send_message("不能贈送給機器人", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("數量需大於 0", ephemeral=True)
            return

        success, from_after, to_after = await economy_manager.transfer(interaction.user.id, member.id, amount)
        if not success:
            await interaction.response.send_message(f"餘額不足，你目前有 {from_after} CT", ephemeral=True)
            return

        embed = discord.Embed(
            title="轉帳成功",
            description=f"{interaction.user.mention} 已贈送 {amount} CT 給 {member.mention}",
            color=discord.Color.green(),
        )
        embed.add_field(name="你的餘額", value=str(from_after))
        embed.add_field(name=f"{member.display_name} 的餘額", value=str(to_after))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="CT 排行榜")
    async def leaderboard(self, interaction: discord.Interaction):
        items = await economy_manager.leaderboard(10)
        if not items:
            await interaction.response.send_message("排行榜目前為空")
            return
        desc_lines = []
        for rank, (uid, bal) in enumerate(items, start=1):
            member = interaction.guild.get_member(uid) if interaction.guild else None
            name = member.display_name if member else f"{uid}"
            desc_lines.append(f"{rank}. {name} — {bal} CT")

        embed = discord.Embed(title="CT 排行榜", description="\n".join(desc_lines), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))

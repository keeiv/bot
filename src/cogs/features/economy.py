from __future__ import annotations
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.economy_manager import economy_manager
from src.utils.daily_manager import daily_manager
from pathlib import Path
import json

SHOP_PATH = Path(__file__).parents[2].joinpath("data", "storage", "shop.json")


def _load_shop():
    try:
        with SHOP_PATH.open("r", encoding="utf-8") as f:
            return json.load(f).get("items", [])
    except Exception:
        return []



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

    @app_commands.command(name="daily", description="每日簽到，連續簽到會有額外獎勵")
    async def daily(self, interaction: discord.Interaction):
        res = await daily_manager.claim_daily(interaction.user.id)
        if not res.get("claimed"):
            await interaction.response.send_message("您今天已簽到過了", ephemeral=True)
            return
        reward = res.get("reward", 0)
        streak = res.get("streak", 1)
        await economy_manager.add_balance(interaction.user.id, reward)
        embed = discord.Embed(title="每日簽到", description=f"簽到成功！獲得 {reward} CT（連續 {streak} 天）", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hourly", description="每小時領取小額 CT（冷卻 1 小時）")
    async def hourly(self, interaction: discord.Interaction):
        res = await daily_manager.claim_hourly(interaction.user.id)
        if not res.get("claimed"):
            rem = res.get("remaining_seconds", 0)
            await interaction.response.send_message(f"冷卻中，請等待 {rem} 秒後再試", ephemeral=True)
            return
        reward = res.get("reward", 0)
        await economy_manager.add_balance(interaction.user.id, reward)
        await interaction.response.send_message(f"獲得 {reward} CT（每小時領取）")

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

    @app_commands.command(name="shop", description="查看商店商品")
    async def shop(self, interaction: discord.Interaction):
        items = _load_shop()
        if not items:
            await interaction.response.send_message("商店目前無商品")
            return
        desc = []
        for it in items:
            desc.append(f"{it['name']} — {it['price']} CT — {it.get('desc','')}")
        embed = discord.Embed(title="商店", description="\n".join(desc), color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="購買商店商品（範例）")
    @app_commands.describe(item_id="商品 ID")
    async def buy(self, interaction: discord.Interaction, item_id: str):
        items = _load_shop()
        item = next((i for i in items if i.get("id") == item_id), None)
        if not item:
            await interaction.response.send_message("找不到該商品", ephemeral=True)
            return
        price = int(item.get("price", 0))
        ok, new_bal = await economy_manager.deduct_balance(interaction.user.id, price)
        if not ok:
            await interaction.response.send_message(f"購買失敗，餘額不足（你有 {new_bal} CT）", ephemeral=True)
            return
        embed = discord.Embed(title="購買成功", description=f"你購買了 {item['name']}，花費 {price} CT", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))


"""女裝請願書功能。"""

import os
from typing import Any

import discord
from discord.ext import commands

from src.services.petition_service import PetitionService

_TARGET_USER_ID = 865537073607606293
_IMAGE_FILE = "data/storage/petition.png"


class Petition(commands.Cog):
    """提供女裝請願書的 prefix 指令。"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = PetitionService()

    @commands.command(name="請求zas女裝")
    async def sign_petition(self, context: commands.Context[Any]) -> None:
        """副署請願書並顯示連續副署天數。"""
        streak = self.service.sign(context.author.id)
        embed = discord.Embed(
            description=(
                f"# {context.author.name} 副署了 <@{_TARGET_USER_ID}> 女裝請願書"
            ),
            color=discord.Color.from_rgb(255, 192, 203),
        )
        embed.set_footer(text=f"已連續 [{streak}] 天")

        if not os.path.exists(_IMAGE_FILE):
            embed.set_footer(text=f"已連續 [{streak}] 天 (圖片遺失)")
            await context.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        file = discord.File(_IMAGE_FILE, filename="petition.png")
        embed.set_image(url="attachment://petition.png")
        await context.send(
            file=file,
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Petition(bot))

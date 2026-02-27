import discord
from discord import app_commands
from discord.ext import commands


class Developer(commands.Cog):
    """開發者專用指令 Cog - 只有開發者可見和使用"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.developer_id = 241619561760292866  # 開發者ID

    def is_developer_slash(self, interaction: discord.Interaction) -> bool:
        """斜杠指令的開發者檢查"""
        return interaction.user.id == self.developer_id

    @app_commands.command(name="dev-status", description="查看開發者狀態")
    async def dev_status_slash(self, interaction: discord.Interaction):
        """開發者狀態檢查"""
        if not self.is_developer_slash(interaction):
            await interaction.response.send_message(
                "[拒絕] 你沒有權限使用此指令", ephemeral=True
            )
            return

        embed = discord.Embed(title="[開發者] 系統狀態", color=discord.Color.purple())
        embed.add_field(name="開發者ID", value=f"`{self.developer_id}`", inline=True)
        embed.add_field(name="機器人狀態", value="運行中", inline=True)
        embed.set_footer(text=f"請求者: {interaction.user.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="dev-status", description="開發者狀態檢查")
    @commands.check(lambda ctx: ctx.author.id == 241619561760292866)
    async def dev_status_command(self, ctx):
        """開發者狀態檢查"""
        embed = discord.Embed(title="[開發者] 系統狀態", color=discord.Color.purple())
        embed.add_field(name="開發者ID", value=f"`{self.developer_id}`", inline=True)
        embed.add_field(name="機器人狀態", value="運行中", inline=True)
        embed.set_footer(text=f"請求者: {ctx.author.name}")

        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Developer(bot))

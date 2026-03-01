from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands, ui
from discord.ext import commands
from src.utils.blacklist_manager import blacklist_manager

TZ_OFFSET = timezone(timedelta(hours=8))
DEVELOPER_ID = 241619561760292866


class AppealModal(ui.Modal, title="黑名單申訴"):
    reason = ui.TextInput(
        label="申訴原因",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        entry = await interaction.client.check_blacklist_api(interaction.user.id)

        if not entry:
            await interaction.response.send_message(
                "您不在黑名單中。", ephemeral=True
            )
            return

        success = blacklist_manager.add_appeal(
            interaction.user.id,
            self.reason.value
        )

        if not success:
            await interaction.response.send_message(
                "您已有待處理申訴。", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "申訴已提交。", ephemeral=True
        )


class Blacklist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="申訴", description="申訴黑名單")
    async def appeal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AppealModal())

    @app_commands.command(name="申訴狀態", description="查看申訴狀態")
    async def appeal_status(self, interaction: discord.Interaction):
        appeal = blacklist_manager.get_appeal(interaction.user.id)

        if not appeal:
            await interaction.response.send_message(
                "沒有申訴紀錄。", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="申訴狀態",
            description=f"狀態: {appeal['status']}\n原因: {appeal['reason']}",
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))

"""Rust Anchor Station: the roulette table and the dive, played as the bot's activity.

Both games run inside Discord as an embedded activity served by the website; these
two commands open it. The activity is the same for both, and the table is chosen
inside it.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.i18n import text as tx
from src.utils.lang_context import localized

log = logging.getLogger(__name__)


class Station(commands.Cog):
    """Open Rust Anchor Station, the activity that holds both tables."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _open(self, interaction: discord.Interaction, table: str) -> None:
        """Launch the activity, or explain where it can be opened instead."""
        try:
            await interaction.response.launch_activity()
        except discord.HTTPException as error:
            # Activities not enabled for the app, or a place that cannot host one.
            log.info("Activity launch refused: %s", error)
            await interaction.response.send_message(
                tx("station.cannot_launch", v0=tx(f"station.{table}")),
                ephemeral=True,
            )

    @app_commands.command(
        name="russian-roulette",
        description="Open the Rust Wheel, the roulette table, as an activity",
    )
    @localized("interaction")
    async def roulette(self, interaction: discord.Interaction) -> None:
        """Open the Rust Wheel."""
        await self._open(interaction, "roulette")

    @app_commands.command(
        name="deep-sea-oxygen",
        description="Open the Sunken Bell, the shared-air dive, as an activity",
    )
    @localized("interaction")
    async def dive(self, interaction: discord.Interaction) -> None:
        """Open the Sunken Bell."""
        await self._open(interaction, "dive")


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(Station(bot))

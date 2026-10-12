from datetime import datetime
from datetime import timezone
import platform
import sys
from typing import Any, Optional, Sequence

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import ActionRow
from discord.ui import Container
from discord.ui import LayoutView
from discord.ui import Section
from discord.ui import Select
from discord.ui import Separator
from discord.ui import TextDisplay
from discord.ui import Thumbnail

from src.config.constants import DEVELOPER_IDS
from src.utils.i18n import text as tx
from src.utils.lang_context import localized


def _dev_markdown(title: str, lines: Sequence[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {title}\n{body}"


class DevInfoSectionSelect(Select[Any]):
    def __init__(self, parent_view: "DevInfoLayoutView") -> None:
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=tx("developer.overview"),
                value="overview",
                description=tx("developer.basic_statistics_and_status"),
                default=parent_view.section == "overview",
            ),
            discord.SelectOption(
                label=tx("developer.server_list"),
                value="guilds",
                description=tx("developer.all_joined_servers"),
                default=parent_view.section == "guilds",
            ),
            discord.SelectOption(
                label=tx("developer.system_info"),
                value="system",
                description=tx("developer.runtime_and_version_details"),
                default=parent_view.section == "system",
            ),
        ]
        super().__init__(
            placeholder=tx("developer.choose_an_information_section"),
            min_values=1,
            max_values=1,
            options=options,
        )

    @localized("interaction")
    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                tx("developer.denied_developers_only"), ephemeral=True
            )
            return
        next_view = DevInfoLayoutView(bot=self.parent_view.bot, section=self.values[0])
        next_view.message = interaction.message
        self.parent_view.stop()
        await interaction.response.edit_message(view=next_view)


class DevInfoLayoutView(LayoutView):
    def __init__(self, bot: commands.Bot, section: str = "overview") -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.section = (
            section if section in ("overview", "guilds", "system") else "overview"
        )
        self.message: Optional[discord.Message] = None
        self._section_select = DevInfoSectionSelect(self)
        self._build()

    def _build(self) -> None:
        container = Container[Any](accent_color=discord.Color.from_rgb(155, 89, 182))

        total_guilds = len(self.bot.guilds)

        section_labels = {
            "overview": tx("developer.overview"),
            "guilds": tx("developer.server_list"),
            "system": tx("developer.system_info"),
        }
        section_label = section_labels[self.section]

        if self.bot.user is not None:
            container.add_item(
                Section(
                    TextDisplay(tx("developer.developer_panel")),
                    TextDisplay(
                        tx(
                            "developer.current_section_servers",
                            v0=(section_label),
                            v1=(total_guilds),
                        )
                    ),
                    accessory=Thumbnail(
                        self.bot.user.display_avatar.url,
                        description=tx("developer.bot_avatar"),
                    ),
                )
            )

        container.add_item(
            Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        if self.section == "overview":
            uptime_str = tx("audit_log.unknown")
            start_time: Optional[datetime] = getattr(self.bot, "_start_time", None)
            if start_time is not None:
                delta = datetime.now(timezone.utc) - start_time
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(rem, 60)
                uptime_str = f"{hours}h {minutes}m {seconds}s"

            latency_ms = round(self.bot.latency * 1000, 2)
            overview_lines = (
                tx("developer.servers", v0=(total_guilds)),
                tx("developer.latency_ms", v0=(latency_ms)),
                tx("developer.uptime", v0=(uptime_str)),
            )
            container.add_item(
                TextDisplay(
                    _dev_markdown(tx("developer.basic_statistics"), overview_lines)
                )
            )

        elif self.section == "guilds":
            guild_lines = [
                tx("developer.id_members", v0=(g.name), v1=(g.id), v2=(g.member_count))
                for g in sorted(
                    self.bot.guilds,
                    key=lambda x: x.member_count or 0,
                    reverse=True,
                )
            ]
            if not guild_lines:
                guild_lines = [tx("developer.no_servers_joined")]

            container.add_item(
                TextDisplay(
                    _dev_markdown(
                        tx("developer.server_list_697b0c", v0=(total_guilds)),
                        guild_lines[:20],
                    )
                )
            )
            if len(guild_lines) > 20:
                container.add_item(
                    TextDisplay(
                        tx("developer.and_other_servers", v0=(len(guild_lines) - 20))
                    )
                )

        elif self.section == "system":
            bot_id = str(self.bot.user.id) if self.bot.user else tx("audit_log.unknown")
            bot_name = self.bot.user.name if self.bot.user else tx("audit_log.unknown")
            system_lines = (
                tx("developer.python_version", v0=(sys.version.split()[0])),
                tx("developer.discord_py_version", v0=(discord.__version__)),
                tx(
                    "developer.operating_system",
                    v0=(platform.system()),
                    v1=(platform.release()),
                ),
                tx("developer.bot_id", v0=(bot_id)),
                tx("developer.bot_name", v0=(bot_name)),
            )
            container.add_item(
                TextDisplay(_dev_markdown(tx("developer.system_info"), system_lines))
            )

        action_row = ActionRow[Any]()
        action_row.add_item(self._section_select)
        container.add_item(
            Separator(visible=True, spacing=discord.SeparatorSpacing.large)
        )
        container.add_item(action_row)

        self.add_item(container)

    async def on_timeout(self) -> None:
        self._section_select.disabled = True
        if self.message is None:
            return
        try:
            await self.message.edit(view=self)
        except (discord.HTTPException, discord.NotFound):
            pass


class Developer(commands.Cog):
    """開發者專用指令 Cog - 只有開發者可見和使用"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def is_developer_slash(self, interaction: discord.Interaction) -> bool:
        """斜杠指令的開發者檢查"""
        return interaction.user.id in DEVELOPER_IDS

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """記錄機器人啟動時間"""
        if not hasattr(self.bot, "_start_time"):
            self.bot._start_time = datetime.now(timezone.utc)

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """處理 >>>info 開發者面板指令"""
        if message.author.bot:
            return
        if not message.content.strip().startswith(">>>info"):
            return
        if message.author.id not in DEVELOPER_IDS:
            await message.reply(
                tx("developer.denied_this_command_is_restricted_to"), delete_after=5
            )
            return

        view = DevInfoLayoutView(bot=self.bot)
        msg = await message.reply(view=view)
        view.message = msg

    @app_commands.command(name="dev-status", description="Show developer status")
    @localized("interaction")
    async def dev_status_slash(self, interaction: discord.Interaction) -> None:
        """開發者狀態檢查"""
        if not self.is_developer_slash(interaction):
            await interaction.response.send_message(
                tx("developer.denied_permission_to_use_this_command"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("developer.developer_system_status"),
            color=discord.Color.from_rgb(155, 89, 182),
        )
        embed.add_field(
            name=tx("developer.developer_ids"),
            value=f"`{', '.join(str(d) for d in DEVELOPER_IDS)}`",
            inline=True,
        )
        embed.add_field(
            name=tx("developer.bot_status"), value=tx("developer.running"), inline=True
        )
        embed.set_footer(text=tx("developer.requested_by", v0=(interaction.user.name)))

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="dev-status", description="開發者狀態檢查")
    @commands.check(lambda ctx: ctx.author.id in DEVELOPER_IDS)
    @localized("ctx")
    async def dev_status_command(self, ctx: Any) -> None:
        """開發者狀態檢查"""
        embed = discord.Embed(
            title=tx("developer.developer_system_status"),
            color=discord.Color.from_rgb(155, 89, 182),
        )
        embed.add_field(
            name=tx("developer.developer_ids"),
            value=f"`{', '.join(str(d) for d in DEVELOPER_IDS)}`",
            inline=True,
        )
        embed.add_field(
            name=tx("developer.bot_status"), value=tx("developer.running"), inline=True
        )
        embed.set_footer(text=tx("developer.requested_by", v0=(ctx.author.name)))

        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(Developer(bot))

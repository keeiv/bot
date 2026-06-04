import platform
import sys
from datetime import datetime, timezone
from typing import Optional, Sequence

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


def _dev_markdown(title: str, lines: Sequence[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {title}\n{body}"


class DevInfoSectionSelect(Select):
    def __init__(self, parent_view: "DevInfoLayoutView"):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label="總覽",
                value="overview",
                description="基本統計與運行狀態",
                default=parent_view.section == "overview",
            ),
            discord.SelectOption(
                label="伺服器列表",
                value="guilds",
                description="已加入的所有伺服器",
                default=parent_view.section == "guilds",
            ),
            discord.SelectOption(
                label="系統資訊",
                value="system",
                description="執行環境與版本資訊",
                default=parent_view.section == "system",
            ),
        ]
        super().__init__(
            placeholder="選擇資訊分區",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                "[拒絕] 僅限開發者使用", ephemeral=True
            )
            return
        next_view = DevInfoLayoutView(bot=self.parent_view.bot, section=self.values[0])
        next_view.message = interaction.message
        self.parent_view.stop()
        await interaction.response.edit_message(view=next_view)


class DevInfoLayoutView(LayoutView):
    def __init__(self, bot: commands.Bot, section: str = "overview"):
        super().__init__(timeout=600)
        self.bot = bot
        self.section = section if section in ("overview", "guilds", "system") else "overview"
        self.message: Optional[discord.Message] = None
        self._section_select = DevInfoSectionSelect(self)
        self._build()

    def _build(self) -> None:
        container = Container(accent_color=discord.Color.from_rgb(155, 89, 182))

        total_guilds = len(self.bot.guilds)

        section_labels = {
            "overview": "總覽",
            "guilds": "伺服器列表",
            "system": "系統資訊",
        }
        section_label = section_labels[self.section]

        if self.bot.user is not None:
            container.add_item(
                Section(
                    TextDisplay("## 開發者面板"),
                    TextDisplay(
                        f"目前分區：**{section_label}**\n"
                        f"伺服器數量：**{total_guilds}**"
                    ),
                    accessory=Thumbnail(
                        self.bot.user.display_avatar.url,
                        description="機器人頭像",
                    ),
                )
            )

        container.add_item(Separator(visible=True, spacing=discord.SeparatorSpacing.small))

        if self.section == "overview":
            uptime_str = "未知"
            start_time: Optional[datetime] = getattr(self.bot, "_start_time", None)
            if start_time is not None:
                delta = datetime.now(timezone.utc) - start_time
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(rem, 60)
                uptime_str = f"{hours}h {minutes}m {seconds}s"

            latency_ms = round(self.bot.latency * 1000, 2)
            overview_lines = (
                f"伺服器數量：**{total_guilds}**",
                f"網路延遲：**{latency_ms} ms**",
                f"運行時間：**{uptime_str}**",
            )
            container.add_item(TextDisplay(_dev_markdown("基本統計", overview_lines)))

        elif self.section == "guilds":
            guild_lines = [
                f"`{g.name}` — ID: `{g.id}` — {g.member_count} 位成員"
                for g in sorted(
                    self.bot.guilds,
                    key=lambda x: x.member_count or 0,
                    reverse=True,
                )
            ]
            if not guild_lines:
                guild_lines = ["尚未加入任何伺服器"]

            container.add_item(
                TextDisplay(_dev_markdown(f"伺服器列表 ({total_guilds})", guild_lines[:20]))
            )
            if len(guild_lines) > 20:
                container.add_item(
                    TextDisplay(f"*...及其他 {len(guild_lines) - 20} 個伺服器*")
                )

        elif self.section == "system":
            bot_id = str(self.bot.user.id) if self.bot.user else "未知"
            bot_name = self.bot.user.name if self.bot.user else "未知"
            system_lines = (
                f"Python 版本：**{sys.version.split()[0]}**",
                f"discord.py 版本：**{discord.__version__}**",
                f"作業系統：**{platform.system()} {platform.release()}**",
                f"機器人 ID：**{bot_id}**",
                f"機器人名稱：**{bot_name}**",
            )
            container.add_item(TextDisplay(_dev_markdown("系統資訊", system_lines)))

        action_row = ActionRow()
        action_row.add_item(self._section_select)
        container.add_item(Separator(visible=True, spacing=discord.SeparatorSpacing.large))
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

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_developer_slash(self, interaction: discord.Interaction) -> bool:
        """斜杠指令的開發者檢查"""
        return interaction.user.id in DEVELOPER_IDS

    @commands.Cog.listener()
    async def on_ready(self):
        """記錄機器人啟動時間"""
        if not hasattr(self.bot, "_start_time"):
            self.bot._start_time = datetime.now(timezone.utc)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """處理 >>>info 開發者面板指令"""
        if message.author.bot:
            return
        if not message.content.strip().startswith(">>>info"):
            return
        if message.author.id not in DEVELOPER_IDS:
            await message.reply("[拒絕] 僅限開發者使用此指令", delete_after=5)
            return

        view = DevInfoLayoutView(bot=self.bot)
        msg = await message.reply(view=view)
        view.message = msg

    @app_commands.command(name="dev-status", description="查看開發者狀態")
    async def dev_status_slash(self, interaction: discord.Interaction):
        """開發者狀態檢查"""
        if not self.is_developer_slash(interaction):
            await interaction.response.send_message(
                "[拒絕] 你沒有權限使用此指令", ephemeral=True
            )
            return

        embed = discord.Embed(title="[開發者] 系統狀態", color=discord.Color.from_rgb(155, 89, 182))
        embed.add_field(name="開發者ID", value=f"`{', '.join(str(d) for d in DEVELOPER_IDS)}`", inline=True)
        embed.add_field(name="機器人狀態", value="運行中", inline=True)
        embed.set_footer(text=f"請求者: {interaction.user.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="dev-status", description="開發者狀態檢查")
    @commands.check(lambda ctx: ctx.author.id in DEVELOPER_IDS)
    async def dev_status_command(self, ctx):
        """開發者狀態檢查"""
        embed = discord.Embed(title="[開發者] 系統狀態", color=discord.Color.from_rgb(155, 89, 182))
        embed.add_field(name="開發者ID", value=f"`{', '.join(str(d) for d in DEVELOPER_IDS)}`", inline=True)
        embed.add_field(name="機器人狀態", value="運行中", inline=True)
        embed.set_footer(text=f"請求者: {ctx.author.name}")

        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Developer(bot))

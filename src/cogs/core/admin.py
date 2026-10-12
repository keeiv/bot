from datetime import timedelta
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

from src.locales.help import CATEGORIES as HELP_CATEGORIES
from src.locales.help import HelpCategory
from src.utils.i18n import Lang
from src.utils.i18n import t
from src.utils.i18n import text as tx
from src.utils.lang_context import context_lang
from src.utils.lang_context import interaction_lang
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage


def _categories(lang: Lang) -> tuple[HelpCategory, ...]:
    return HELP_CATEGORIES[lang]


def _category_map(lang: Lang) -> dict[str, HelpCategory]:
    return {category.key: category for category in HELP_CATEGORIES[lang]}


def _help_markdown(title: str, lines: Sequence[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {title}\n{body}"


class HelpCategorySelect(Select[Any]):
    def __init__(self, parent_view: "HelpLayoutView") -> None:
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=category.label,
                value=category.key,
                description=category.description,
                default=category.key == parent_view.category_key,
            )
            for category in _categories(parent_view.lang)
        ]
        super().__init__(
            placeholder=t(parent_view.lang, "help.placeholder"),
            min_values=1,
            max_values=1,
            options=options,
        )

    @localized("interaction")
    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.parent_view.author_id:
            await interaction.response.send_message(
                t(await interaction_lang(interaction), "help.denied"), ephemeral=True
            )
            return

        next_view = HelpLayoutView(
            bot=self.parent_view.bot,
            author_id=self.parent_view.author_id,
            category_key=self.values[0],
            lang=self.parent_view.lang,
        )
        next_view.message = interaction.message
        self.parent_view.stop()
        await interaction.response.edit_message(view=next_view)


class HelpLayoutView(LayoutView):
    def __init__(
        self,
        bot: commands.Bot,
        author_id: int,
        category_key: str,
        lang: Lang = "en",
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.author_id = author_id
        self.lang: Lang = lang
        self.category_key = (
            category_key if category_key in _category_map(lang) else "overview"
        )
        self.message: Optional[discord.Message] = None
        self.category_select = HelpCategorySelect(self)
        self._build()

    def _build(self) -> None:
        category = _category_map(self.lang)[self.category_key]
        container = Container[Any](accent_color=category.accent_color)

        header_lines = (
            t(self.lang, "help.current", label=category.label),
            category.summary,
        )

        if self.bot.user is not None:
            container.add_item(
                Section(
                    TextDisplay(f"## {t(self.lang, 'help.title')}"),
                    TextDisplay("\n".join(header_lines)),
                    accessory=Thumbnail(
                        self.bot.user.display_avatar.url,
                        description=t(self.lang, "help.avatar"),
                    ),
                )
            )
        else:
            container.add_item(
                TextDisplay(_help_markdown(t(self.lang, "help.title"), header_lines))
            )

        for block in category.blocks:
            container.add_item(
                Separator(visible=True, spacing=discord.SeparatorSpacing.small)
            )
            container.add_item(TextDisplay(_help_markdown(block.title, block.lines)))

        action_row = ActionRow[Any]()
        action_row.add_item(self.category_select)
        container.add_item(
            Separator(visible=True, spacing=discord.SeparatorSpacing.large)
        )
        container.add_item(action_row)

        self.add_item(container)

    async def on_timeout(self) -> None:
        self.category_select.disabled = True
        if self.message is None:
            return

        try:
            await self.message.edit(view=self)
        except (discord.HTTPException, discord.NotFound):
            pass


class Admin(commands.Cog):
    """管理員命令 Cog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def is_blacklisted_check(self) -> Any:
        """黑名單檢查裝飾器"""

        @localized("ctx")
        async def predicate(ctx: commands.Context[Any]) -> Any:
            blacklist_manager = getattr(self.bot, "blacklist_manager", None)
            if blacklist_manager is not None and (
                await run_storage(blacklist_manager.local_check, ctx.author.id)
            ):
                embed = discord.Embed(
                    title=tx("admin.denied_access_denied"),
                    description=tx("admin.bot_commands_are_unavailable_for_this"),
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await ctx.send(embed=embed)
                return False
            return True

        return commands.check(predicate)

    @commands.hybrid_command(
        name="clear", description="Delete a number of recent messages"
    )
    @app_commands.describe(amount="How many messages to delete (1-100, default 10)")
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @localized("ctx")
    async def clear(self, ctx: commands.Context[Any], amount: int = 10) -> None:
        """清除訊息"""
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(
                tx("admin.failed_the_manage_messages_permission_is"), ephemeral=True
            )
            return

        if amount < 1 or amount > 100:
            await ctx.send(tx("admin.failed_the_count_must_be_between"), ephemeral=True)
            return

        await ctx.defer()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.followup.send(
            tx("admin.success_deleted_messages", v0=(len(deleted))), ephemeral=True
        )

    @commands.hybrid_command(name="kick", description="Kick a member")
    @app_commands.describe(
        user="The member to kick", reason="Why they are being kicked"
    )
    @commands.has_permissions(kick_members=True)
    @localized("ctx")
    async def kick(
        self,
        ctx: commands.Context[Any],
        user: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        """踢出成員"""
        reason = reason or tx("admin.no_reason_given")
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send(
                tx("admin.failed_the_kick_members_permission_is"), ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send(
                tx("admin.failed_self_kicking_is_not_allowed"), ephemeral=True
            )
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                tx("admin.failed_insufficient_permission_to_kick_this"),
                ephemeral=True,
            )
            return

        try:
            await user.kick(reason=reason)
            embed = discord.Embed(
                title=tx("admin.success_member_kicked"),
                description=tx("admin.member_reason", v0=(user.mention), v1=(reason)),
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(
                tx("admin.failed_could_not_kick_member", v0=(str(e))), ephemeral=True
            )

    @commands.hybrid_command(name="ban", description="Ban a member")
    @app_commands.describe(user="The member to ban", reason="Why they are being banned")
    @commands.has_permissions(ban_members=True)
    @localized("ctx")
    async def ban(
        self,
        ctx: commands.Context[Any],
        user: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        """封禁成員"""
        reason = reason or tx("admin.no_reason_given")
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send(
                tx("admin.failed_the_ban_members_permission_is"), ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send(
                tx("admin.failed_self_banning_is_not_allowed"), ephemeral=True
            )
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                tx("admin.failed_insufficient_permission_to_ban_this"),
                ephemeral=True,
            )
            return

        try:
            await user.ban(reason=reason)
            embed = discord.Embed(
                title=tx("admin.success_member_banned"),
                description=tx("admin.member_reason", v0=(user.mention), v1=(reason)),
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(
                tx("admin.failed_could_not_ban_member", v0=(str(e))), ephemeral=True
            )

    @commands.hybrid_command(name="mute", description="Time out a member")
    @app_commands.describe(
        user="The member to time out",
        duration="Timeout length in minutes (default 60)",
        reason="Why they are being timed out",
    )
    @commands.has_permissions(moderate_members=True)
    @localized("ctx")
    async def mute(
        self,
        ctx: commands.Context[Any],
        user: discord.Member,
        duration: int = 60,
        reason: Optional[str] = None,
    ) -> None:
        """禁言成員"""
        reason = reason or tx("admin.no_reason_given")
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                tx("admin.failed_the_moderate_members_permission_is"), ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send(
                tx("admin.failed_self_muting_is_not_allowed"), ephemeral=True
            )
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                tx("admin.failed_insufficient_permission_to_mute_this"), ephemeral=True
            )
            return

        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title=tx("admin.success_member_muted"),
                description=tx(
                    "admin.member_duration_minutes_reason",
                    v0=(user.mention),
                    v1=(duration),
                    v2=(reason),
                ),
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(
                tx("admin.failed_could_not_mute_member", v0=(str(e))), ephemeral=True
            )

    @commands.hybrid_command(name="warn", description="Warn a member")
    @app_commands.describe(
        user="The member to warn", reason="Why they are being warned"
    )
    @commands.has_permissions(moderate_members=True)
    @localized("ctx")
    async def warn(
        self,
        ctx: commands.Context[Any],
        user: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        """警告成員"""
        reason = reason or tx("admin.no_reason_given")
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                tx("admin.failed_the_moderate_members_permission_is"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("admin.warning_member_warning"),
            description=tx(
                "admin.was_warned_for_the_following_reason",
                v0=(user.mention),
                v1=(reason),
            ),
            color=discord.Color.from_rgb(241, 196, 15),
        )

        try:
            await user.send(embed=embed)
            await ctx.send(
                tx("admin.success_warned", v0=(user.mention)), ephemeral=True
            )
        except Exception as e:
            await ctx.send(
                tx("admin.warning_member_warned_but_the_dm", v0=(str(e))),
                ephemeral=True,
            )

    @commands.hybrid_command(name="help", description="Show what the bot can do")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @localized("ctx")
    async def help_command(self, ctx: commands.Context[Any]) -> None:
        """幫助指令"""
        lang = await context_lang(ctx)
        view = HelpLayoutView(self.bot, ctx.author.id, "overview", lang)
        message = await ctx.send(view=view)
        if isinstance(message, discord.Message):
            view.message = message


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(Admin(bot))

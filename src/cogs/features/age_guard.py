"""年齡守門員 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.services.age_guard_service import AgeGuardService
from src.utils.config_manager import get_guild_log_channel
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage

TZ_OFFSET = timezone(timedelta(hours=8))


class AgeGuard(commands.Cog):
    """年齡守門員 — 偵測成員公開宣告未成年，移除成人身份組並附加懲罰身份組"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AgeGuardService()

    age_guard = app_commands.Group(
        name="age_guard",
        description="Age guard settings",
        default_permissions=discord.Permissions(administrator=True),
        guild_only=True,
    )

    @age_guard.command(
        name="set_adult_role",
        description="Set the adult (18+) role, removed when someone says they are under age",
    )
    @app_commands.describe(role="The adult (18+) role")
    @localized("interaction")
    async def set_adult_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await run_storage(self.service.set_adult_role, interaction.guild_id, role.id)
        embed = discord.Embed(
            title=tx("age_guard.success_adult_role_saved"),
            description=tx(
                "age_guard.adult_role_this_role_is_removed", v0=(role.mention)
            ),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @age_guard.command(
        name="set_punishment_role",
        description="Set the role added when someone says they are under age",
    )
    @app_commands.describe(role="The role to add")
    @localized("interaction")
    async def set_punishment_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await run_storage(
            self.service.set_punishment_role, interaction.guild_id, role.id
        )
        embed = discord.Embed(
            title=tx("age_guard.success_penalty_role_saved"),
            description=tx(
                "age_guard.penalty_role_this_role_is_added", v0=(role.mention)
            ),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @age_guard.command(name="toggle", description="Turn the age guard on or off")
    @localized("interaction")
    async def toggle(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        new_state = await run_storage(self.service.toggle_enabled, interaction.guild_id)
        state_str = (
            tx("settings.enabled_0ae5c7") if new_state else tx("settings.disabled")
        )
        color = (
            discord.Color.from_rgb(46, 204, 113)
            if new_state
            else discord.Color.from_rgb(231, 76, 60)
        )
        embed = discord.Embed(
            title=tx("age_guard.success_age_guard", v0=(state_str)),
            color=color,
            timestamp=datetime.now(TZ_OFFSET),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @age_guard.command(name="status", description="Show the age guard settings")
    @localized("interaction")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        cfg = await run_storage(self.service.get_config, interaction.guild_id)
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
            title=tx("settings.settings_age_guard"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("blacklist.status"),
            value=tx("settings.enabled") if enabled else tx("settings.disabled_891b9e"),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.adult_role"),
            value=adult_role.mention if adult_role else tx("settings.not_configured"),
            inline=True,
        )
        embed.add_field(
            name=tx("settings.penalty_role"),
            value=(
                punishment_role.mention
                if punishment_role
                else tx("settings.not_configured")
            ),
            inline=True,
        )
        embed.set_footer(text=tx("age_guard.server", v0=(interaction.guild.name)))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message: discord.Message) -> None:
        """監聽訊息，偵測未成年年齡宣告"""
        if message.author.bot or message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return

        cfg = await run_storage(self.service.get_config, message.guild.id)
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
                    adult_role,
                    reason=tx(
                        "age_guard.age_guard_member_declared_age_underage", v0=(age)
                    ),
                )
                actions_taken.append(
                    tx("age_guard.removed_adult_role", v0=(adult_role.mention))
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if punishment_role is not None and punishment_role not in member.roles:
            try:
                await member.add_roles(
                    punishment_role,
                    reason=tx(
                        "age_guard.age_guard_member_declared_age_underage", v0=(age)
                    ),
                )
                actions_taken.append(
                    tx("age_guard.added_penalty_role", v0=(punishment_role.mention))
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if not actions_taken:
            return

        log_channel_id = await run_storage(get_guild_log_channel, guild.id)
        if not log_channel_id:
            return
        log_channel = guild.get_channel(log_channel_id)
        if not isinstance(
            log_channel,
            (
                discord.TextChannel,
                discord.Thread,
                discord.VoiceChannel,
                discord.StageChannel,
            ),
        ):
            return

        content = message.content or ""
        excerpt = content if len(content) <= 200 else content[:197] + "..."
        embed = discord.Embed(
            title=tx("age_guard.age_guard_underage_declaration_detected"),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("age_guard.member"),
            value=f"{member.mention} (`{member.id}`)",
            inline=True,
        )
        embed.add_field(name=tx("age_guard.declared_age"), value=str(age), inline=True)
        embed.add_field(
            name=tx("audit_log.channel"), value=message.channel.mention, inline=True
        )
        embed.add_field(
            name=tx("age_guard.original_message"), value=excerpt, inline=False
        )
        embed.add_field(
            name=tx("age_guard.actions_taken"),
            value="\n".join(actions_taken),
            inline=False,
        )
        embed.set_footer(
            text=tx("age_guard.server_user_id", v0=(guild.name), v1=(member.id))
        )
        try:
            await log_channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AgeGuard(bot))

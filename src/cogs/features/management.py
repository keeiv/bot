import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.services.management_service import ManagementService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage


class Management(commands.Cog):
    """伺服器管理指令，包含倉庫追蹤、身份組分配、表情符號管理和歡迎訊息"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = ManagementService()

        self._repo_poll_task.start()

    async def cog_unload(self) -> None:
        self._repo_poll_task.cancel()

    # Repository tracking commands
    repo_track = app_commands.Group(
        name="repo_track", description="Follow repository updates and pull requests"
    )

    @repo_track.command(name="add", description="Follow keeiv/bot")
    @app_commands.describe(channel="The channel for notifications")
    @localized("interaction")
    async def repo_track_add(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=False)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("management.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"
        owner = "keeiv"
        repo = "bot"

        await run_storage(
            self.service.add_tracked_repo, guild_id, owner, repo, channel.id
        )
        await interaction.followup.send(
            tx(
                "management.success_tracking_updates_for_in",
                v0=(channel.mention),
                v1=(repo_key),
            )
        )

    @repo_track.command(name="remove", description="Stop following keeiv/bot")
    @localized("interaction")
    async def repo_track_remove(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=False)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("management.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"

        if await run_storage(self.service.remove_tracked_repo, guild_id, repo_key):
            await interaction.followup.send(
                tx("management.success_stopped_tracking", v0=(repo_key))
            )
        else:
            await interaction.followup.send(
                tx("management.info_is_not_being_tracked", v0=(repo_key)),
                ephemeral=True,
            )

    @repo_track.command(name="status", description="Show what is being followed")
    @localized("interaction")
    async def repo_track_status(self, interaction: discord.Interaction) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        guild_id = str(interaction.guild.id)

        repos = self.service.get_tracked_repos(guild_id)
        if not repos:
            await interaction.response.send_message(
                tx("management.info_no_repositories_are_being_tracked"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("management.keeiv_bot_tracking_status"),
            color=discord.Color.from_rgb(52, 152, 219),
        )

        repo_key = "keeiv/bot"
        if repo_key in repos:
            data = repos[repo_key]
            channel = self.bot.get_channel(data["channel_id"])
            channel_name = (
                channel.mention
                if channel
                else tx("management.unknown_channel", v0=(data["channel_id"]))
            )

            embed.add_field(
                name=repo_key,
                value=tx(
                    "management.channel_last_commit_last_pr",
                    v0=(channel_name),
                    v1=(data.get("last_commit", tx("management.none_yet"))),
                    v2=(data.get("last_pr", tx("management.none_yet"))),
                ),
                inline=False,
            )
        else:
            embed.description = tx("management.the_keeiv_bot_repository_is_not")

        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=5)
    async def _repo_poll_task(self) -> None:
        """每 5 分鐘檢查倉庫更新"""
        configs = self.service.get_all_configs()
        for guild_id, guild_config in configs.items():
            if "tracked_repos" not in guild_config or not guild_config["tracked_repos"]:
                continue

            for repo_key, repo_data in list(guild_config["tracked_repos"].items()):
                await self._poll_repository(guild_id, repo_key, repo_data)

    @localized("guild_id")
    async def _poll_repository(self, guild_id, repo_key, repo_data) -> None:
        try:
            events = await self.service.check_repo_updates(
                guild_id, repo_key, repo_data
            )
            for event in events:
                channel = self.bot.get_channel(event["channel_id"])
                if not isinstance(
                    channel,
                    (
                        discord.TextChannel,
                        discord.Thread,
                        discord.VoiceChannel,
                        discord.StageChannel,
                    ),
                ):
                    continue
                if event["type"] == "commit":
                    embed = discord.Embed(
                        title=event["title"],
                        description=event["description"],
                        url=event["url"],
                        color=discord.Color.from_rgb(46, 204, 113),
                    )
                    embed.set_author(
                        name=event["author_name"],
                        url=event["author_url"],
                        icon_url=event["author_avatar"],
                    )
                    embed.add_field(name="[SHA]", value=event["sha"], inline=True)
                    embed.add_field(
                        name=tx("management.date"), value=event["date"], inline=True
                    )
                    await channel.send(embed=embed)
                elif event["type"] == "pr":
                    embed = discord.Embed(
                        title=event["title"],
                        description=event["description"],
                        url=event["url"],
                        color=discord.Color.from_rgb(230, 126, 34),
                    )
                    embed.set_author(
                        name=event["author_name"],
                        url=event["author_url"],
                        icon_url=event["author_avatar"],
                    )
                    embed.add_field(
                        name=tx("management.pr_number"),
                        value=event["pr_number"],
                        inline=True,
                    )
                    embed.add_field(
                        name=tx("management.status"), value=event["state"], inline=True
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"Error checking {repo_key}: {e}")
            return

    # Role management commands
    role = app_commands.Group(name="role", description="Role commands")

    @role.command(name="assign", description="Give a member a role")
    @app_commands.describe(
        user="The member to give the role to", role="The role to give"
    )
    @localized("interaction")
    async def role_assign(
        self, interaction: discord.Interaction, user: discord.Member, role: discord.Role
    ) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                tx("management.failed_the_manage_roles_permission_is"),
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                tx("management.failed_the_everyone_role_cannot_be"),
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                tx("management.failed_roles_managed_by_bots_or"),
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                tx("management.failed_roles_at_or_above_the"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await user.add_roles(role)
            await interaction.followup.send(
                tx(
                    "management.success_assigned_to",
                    v0=(role.mention),
                    v1=(user.mention),
                ),
            )
        except discord.Forbidden:
            await interaction.followup.send(
                tx("management.failed_the_bot_cannot_assign_this"),
            )

    @role.command(name="remove", description="Take a role from a member")
    @app_commands.describe(
        user="The member to take the role from", role="The role to take away"
    )
    @localized("interaction")
    async def role_remove(
        self, interaction: discord.Interaction, user: discord.Member, role: discord.Role
    ) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                tx("management.failed_the_manage_roles_permission_is"),
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                tx("management.failed_the_everyone_role_cannot_be"),
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                tx("management.failed_roles_managed_by_bots_or"),
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                tx("management.failed_roles_at_or_above_the_5af74a"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await user.remove_roles(role)
            await interaction.followup.send(
                tx(
                    "management.success_removed_from",
                    v0=(user.mention),
                    v1=(role.mention),
                ),
            )
        except discord.Forbidden:
            await interaction.followup.send(
                tx("management.failed_the_bot_cannot_remove_this"),
            )

    # Emoji management commands
    emoji = app_commands.Group(name="emoji", description="Emoji commands")

    @emoji.command(name="get", description="Get an emoji at full size")
    @app_commands.describe(emoji="The emoji")
    @localized("interaction")
    async def emoji_get(self, interaction: discord.Interaction, emoji: str) -> None:
        try:
            # Parse emoji
            if emoji.startswith("<:") and emoji.endswith(">"):
                # Custom emoji
                parts = emoji.strip("<:>").split(":")
                if len(parts) == 2:
                    emoji_id = parts[1]
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
                else:
                    await interaction.response.send_message(
                        tx("management.failed_invalid_emoji_format"), ephemeral=True
                    )
                    return
            elif emoji.startswith("<a:") and emoji.endswith(">"):
                # Animated emoji
                parts = emoji.strip("<a:>").split(":")
                if len(parts) == 2:
                    emoji_id = parts[1]
                    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.gif"
                else:
                    await interaction.response.send_message(
                        tx("management.failed_invalid_emoji_format"), ephemeral=True
                    )
                    return
            else:
                await interaction.response.send_message(
                    tx("management.failed_a_custom_emoji_is_required"), ephemeral=True
                )
                return

            embed = discord.Embed(
                title=tx("management.emoji_full_size_image"),
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                tx("management.failed_could_not_retrieve_emoji", v0=(e)), ephemeral=True
            )

    @emoji.command(name="upload", description="Upload an emoji to this server")
    @app_commands.describe(name="Emoji name", image="The image to upload")
    @localized("interaction")
    async def emoji_upload(
        self, interaction: discord.Interaction, name: str, image: discord.Attachment
    ) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_emojis:
            await interaction.response.send_message(
                tx("management.failed_the_manage_expressions_permission_is"),
                ephemeral=True,
            )
            return

        if not (image.content_type or "").startswith("image/"):
            await interaction.response.send_message(
                tx("management.failed_upload_an_image_file"), ephemeral=True
            )
            return

        await interaction.response.defer()
        try:
            image_data = await image.read()
            emoji = await interaction.guild.create_custom_emoji(
                name=name,
                image=image_data,
                reason=tx("management.uploaded_by", v0=(interaction.user)),
            )
            await interaction.followup.send(
                tx("management.success_emoji_uploaded", v0=(emoji))
            )
        except discord.Forbidden:
            await interaction.followup.send(
                tx("management.failed_the_bot_cannot_upload_emoji"), ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                tx("management.failed_could_not_upload_emoji", v0=(e)), ephemeral=True
            )

    # Welcome message commands
    welcome = app_commands.Group(name="welcome", description="Welcome messages")

    @welcome.command(name="setup", description="Set up the welcome message")
    @app_commands.describe(
        channel="The channel for welcome messages",
        message="The welcome message",
        embed_title="Embed title",
        embed_color="Embed colour (hex)",
        auto_role="Role to give new members",
        send_dm="Also send it as a DM",
    )
    @localized("interaction")
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str | None = None,
        embed_title: str | None = None,
        embed_color: str | None = None,
        auto_role: discord.Role | None = None,
        send_dm: bool = False,
    ) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                tx("management.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)

        welcome_config = {
            "channel_id": channel.id,
            "message": message or tx("management.welcome_to"),
            "send_dm": send_dm,
        }

        if embed_title:
            welcome_config["embed_title"] = embed_title

        if embed_color:
            try:
                welcome_config["embed_color"] = int(embed_color.lstrip("#"), 16)
            except ValueError:
                await interaction.followup.send(
                    tx("management.failed_invalid_color_use_a_hexadecimal"),
                    ephemeral=True,
                )
                return

        if auto_role:
            if auto_role.is_default():
                await interaction.followup.send(
                    tx("management.failed_the_everyone_role_cannot_be_9e2c5a"),
                    ephemeral=True,
                )
                return
            welcome_config["auto_role_id"] = auto_role.id

        await run_storage(self.service.set_welcome_config, guild_id, welcome_config)

        response_msg = tx(
            "management.success_welcome_messages_will_be_sent", v0=(channel.mention)
        )
        if auto_role:
            response_msg += tx("management.automatic_role", v0=(auto_role.mention))
        if send_dm:
            response_msg += tx("management.dm_notifications_enabled")

        await interaction.followup.send(response_msg)

    @welcome.command(name="templates", description="Show welcome message templates")
    @localized("interaction")
    async def welcome_templates(self, interaction: discord.Interaction) -> None:
        templates = [
            {
                "name": tx("management.basic"),
                "message": tx("management.welcome_to_there_are_now_members"),
            },
            {
                "name": tx("management.friendly"),
                "message": tx("management.hello_welcome_to_introductions_are_welcome"),
            },
            {
                "name": tx("management.formal"),
                "message": tx("management.welcome_to_please_read_the_rules"),
            },
            {
                "name": tx("management.gaming"),
                "message": tx("management.joined_the_game_welcome_to_ready"),
            },
            {
                "name": tx("management.community"),
                "message": tx("management.welcome_to_the_community_member_number"),
            },
        ]

        embed = discord.Embed(
            title=tx("management.welcome_messages_default_templates"),
            description=tx("management.available_variables"),
            color=discord.Color.from_rgb(52, 152, 219),
        )

        for template in templates:
            embed.add_field(
                name=template["name"], value=template["message"], inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome.command(name="preview", description="Preview the welcome message")
    @app_commands.describe(
        test_user="Sample user name", test_server="Sample server name"
    )
    @localized("interaction")
    async def welcome_preview(
        self,
        interaction: discord.Interaction,
        test_user: str | None = None,
        test_server: str | None = None,
    ) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        guild_id = str(interaction.guild.id)

        welcome_config = self.service.get_welcome_config(guild_id)
        if not welcome_config:
            await interaction.response.send_message(
                tx("management.failed_welcome_messages_are_not_configured"),
                ephemeral=True,
            )
            return

        user_mention = test_user or interaction.user.mention
        server_name = test_server or interaction.guild.name

        message = welcome_config["message"].format(
            user=user_mention,
            username=interaction.user.display_name,
            server=server_name,
            count=interaction.guild.member_count,
            created_at=interaction.guild.created_at.strftime("%Y/%m/%d"),
        )

        if "embed_title" in welcome_config or "embed_color" in welcome_config:
            embed = discord.Embed(
                title=welcome_config.get("embed_title"),
                description=message,
                color=welcome_config.get(
                    "embed_color", discord.Color.from_rgb(52, 152, 219)
                ),
            )
            embed.set_thumbnail(
                url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            embed.set_footer(
                text=tx("management.member_number", v0=(interaction.guild.member_count))
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                tx("management.preview", v0=(message)), ephemeral=True
            )

    @welcome.command(name="disable", description="Turn off welcome messages")
    @localized("interaction")
    async def welcome_disable(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=False)
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.followup.send(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.followup.send(
                tx("management.failed_the_manage_channels_permission_is"),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        if await run_storage(self.service.clear_welcome_config, guild_id):
            await interaction.followup.send(
                tx("management.success_welcome_messages_disabled")
            )
        else:
            await interaction.followup.send(
                tx("management.failed_welcome_messages_are_not_enabled"), ephemeral=True
            )

    # Auto role commands
    auto_role = app_commands.Group(name="auto_role", description="Automatic roles")

    @auto_role.command(name="setup", description="Add an automatic role rule")
    @app_commands.describe(
        role="The role new members get",
        delay="Delay before giving it, in seconds",
        min_members="Minimum member count",
        require_verification="Require verification",
    )
    @localized("interaction")
    async def auto_role_setup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        delay: int = 0,
        min_members: int = 0,
        require_verification: bool = False,
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
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                tx("management.failed_the_manage_roles_permission_is"),
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.followup.send(
                tx("management.failed_the_everyone_role_cannot_be_9e2c5a"),
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.followup.send(
                tx("management.failed_managed_roles_cannot_be_used"),
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.followup.send(
                tx("management.failed_roles_at_or_above_the_7790b2"),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        role_config = {
            "role_id": role.id,
            "delay": delay,
            "min_members": min_members,
            "require_verification": require_verification,
        }

        await run_storage(self.service.add_auto_role, guild_id, role_config)

        embed = discord.Embed(
            title=tx("management.success_automatic_role_saved"),
            description=tx(
                "management.role_will_be_assigned_to_new", v0=(role.mention)
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=tx("management.delay"),
            value=tx("audit_log.seconds", v0=(delay)),
            inline=True,
        )
        embed.add_field(
            name=tx("management.minimum_members"), value=str(min_members), inline=True
        )
        embed.add_field(
            name=tx("management.verification_required"),
            value=tx("anti_spam.yes") if require_verification else tx("anti_spam.no"),
            inline=True,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @auto_role.command(name="list", description="List automatic role rules")
    @localized("interaction")
    async def auto_role_list(self, interaction: discord.Interaction) -> None:
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        guild_id = str(interaction.guild.id)

        auto_roles = self.service.get_auto_roles(guild_id)
        if not auto_roles:
            await interaction.response.send_message(
                tx("management.failed_no_automatic_role_rules_are"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=tx("management.automatic_roles_rules"),
            color=discord.Color.from_rgb(52, 152, 219),
        )

        for i, role_config in enumerate(auto_roles, 1):
            role = interaction.guild.get_role(role_config["role_id"])
            role_name = (
                role.name
                if role
                else tx("management.deleted_role", v0=(role_config["role_id"]))
            )

            rules = []
            if role_config.get("delay", 0) > 0:
                rules.append(tx("management.delay_seconds", v0=(role_config["delay"])))
            if role_config.get("min_members", 0) > 0:
                rules.append(
                    tx(
                        "management.minimum_members_1e794c",
                        v0=(role_config["min_members"]),
                    )
                )
            if role_config.get("require_verification", False):
                rules.append(tx("management.verification_required_686d9b"))

            rule_text = (
                " | ".join(rules) if rules else tx("management.assigned_immediately")
            )
            embed.add_field(
                name=tx("management.rule", v0=(i), v1=(role_name)),
                value=rule_text,
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @auto_role.command(name="remove", description="Remove an automatic role rule")
    @app_commands.describe(rule_index="Rule number")
    @localized("interaction")
    async def auto_role_remove(
        self, interaction: discord.Interaction, rule_index: int
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
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                tx("management.failed_the_manage_roles_permission_is"),
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        removed_role = await run_storage(
            self.service.remove_auto_role, guild_id, rule_index
        )
        if removed_role is None:
            await interaction.followup.send(
                tx("management.failed_invalid_rule_number"), ephemeral=True
            )
            return

        role = interaction.guild.get_role(removed_role["role_id"])
        role_name = (
            role.name
            if role
            else tx("management.deleted_role", v0=(removed_role["role_id"]))
        )

        await interaction.followup.send(
            tx("management.success_removed_automatic_role_rule", v0=(role_name)),
            ephemeral=True,
        )

    @commands.Cog.listener()
    @localized("member")
    async def on_member_join(self, member: discord.Member) -> None:
        guild_id = str(member.guild.id)

        # Handle welcome messages
        welcome_config = self.service.get_welcome_config(guild_id)
        if welcome_config:
            channel = member.guild.get_channel(welcome_config["channel_id"])

            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.Thread,
                    discord.VoiceChannel,
                    discord.StageChannel,
                ),
            ):
                message = welcome_config["message"].format(
                    user=member.mention,
                    username=member.display_name,
                    server=member.guild.name,
                    count=member.guild.member_count,
                    created_at=member.guild.created_at.strftime("%Y/%m/%d"),
                )

                if "embed_title" in welcome_config or "embed_color" in welcome_config:
                    embed = discord.Embed(
                        title=welcome_config.get("embed_title"),
                        description=message,
                        color=welcome_config.get(
                            "embed_color", discord.Color.from_rgb(52, 152, 219)
                        ),
                    )
                    embed.set_thumbnail(
                        url=member.guild.icon.url if member.guild.icon else None
                    )
                    embed.set_footer(
                        text=tx(
                            "management.member_number", v0=(member.guild.member_count)
                        )
                    )
                    embed.set_author(
                        name=member.name, icon_url=member.display_avatar.url
                    )
                    await channel.send(embed=embed)
                else:
                    await channel.send(message)

                # Send DM if enabled
                if welcome_config.get("send_dm", False):
                    try:
                        dm_message = welcome_config["message"].format(
                            user=member.mention,
                            username=member.display_name,
                            server=member.guild.name,
                            count=member.guild.member_count,
                            created_at=member.guild.created_at.strftime("%Y/%m/%d"),
                        )
                        await member.send(dm_message)
                    except discord.Forbidden:
                        pass

                # Apply welcome auto-role if configured
                try:
                    auto_role_id = welcome_config.get("auto_role_id")
                    if auto_role_id:
                        role = member.guild.get_role(auto_role_id)
                        if role and not role.is_default() and not role.managed:
                            await member.add_roles(
                                role, reason=tx("management.automatic_welcome_role")
                            )
                except (discord.Forbidden, discord.HTTPException):
                    # 忽略權限或 API 錯誤，避免中斷歡迎流程
                    pass

        await self._apply_auto_roles(member)

    @commands.Cog.listener()
    @localized("after")
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """成員完成 Discord 會員篩選後套用需要驗證的角色。"""
        if before.pending and not after.pending:
            await self._apply_auto_roles(after, verified_only=True)

    async def _apply_auto_roles(
        self, member: discord.Member, *, verified_only: bool = False
    ) -> None:
        guild_id = str(member.guild.id)
        auto_roles = self.service.get_auto_roles(guild_id)
        if auto_roles:
            for role_config in auto_roles:
                try:
                    requires_verification = role_config.get(
                        "require_verification", False
                    )
                    if verified_only and not requires_verification:
                        continue
                    # Check conditions
                    if role_config.get("min_members", 0) > member.guild.member_count:
                        continue

                    if requires_verification and member.pending:
                        continue

                    role = member.guild.get_role(role_config["role_id"])
                    if not role:
                        continue

                    # Apply delay if needed
                    if role_config.get("delay", 0) > 0:
                        await asyncio.sleep(role_config["delay"])

                    if requires_verification and member.pending:
                        continue
                    if role in member.roles:
                        continue

                    await member.add_roles(
                        role, reason=tx("management.automatic_role_assignment")
                    )

                except (discord.Forbidden, discord.HTTPException):
                    continue


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Management(bot))

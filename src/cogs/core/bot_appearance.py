import base64
from datetime import datetime
from typing import Any
import uuid

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.config.constants import DEVELOPER_IDS
from src.services.appearance_service import AppearanceService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView
from src.utils.time_utils import TZ_OFFSET

# 圖片大小限制 8MB
MAX_IMAGE_SIZE = 8 * 1024 * 1024


class AppearanceApprovalView(LocalizedView):
    """外觀變更審核視圖"""

    i18n = {
        "approve_button.label": "bot_appearance.approve",
        "reject_button.label": "bot_appearance.reject",
    }

    def __init__(self, request_id: str, cog: "BotAppearance") -> None:
        super().__init__(timeout=None)
        self.request_id = request_id
        self.cog = cog

    @ui.button(label="Approve", style=discord.ButtonStyle.success)
    @localized("interaction")
    async def approve_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """核准變更"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                tx("blacklist.denied_appeal_review_permission_is_required"),
                ephemeral=True,
            )
            return
        await self.cog.handle_approval(interaction, self.request_id, approved=True)

    @ui.button(label="Reject", style=discord.ButtonStyle.danger)
    @localized("interaction")
    async def reject_button(
        self, interaction: discord.Interaction, button: ui.Button[Any]
    ) -> None:
        """拒絕變更"""
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message(
                tx("blacklist.denied_appeal_review_permission_is_required"),
                ephemeral=True,
            )
            return
        await self.cog.handle_approval(interaction, self.request_id, approved=False)


class BotAppearance(commands.Cog):
    """機器人外觀設定 Cog (伺服器級)"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AppearanceService()

    appearance_group = app_commands.Group(
        name="bot_appearance",
        description="The bot's appearance in this server",
        default_permissions=discord.Permissions(administrator=True),
    )

    @localized("interaction")
    async def send_approval_request(
        self,
        interaction: discord.Interaction,
        change_type: str,
        image_bytes: bytes,
        content_type: str,
        image_url: str,
    ) -> None:
        """發送審核請求給開發者"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        request_id = str(uuid.uuid4())[:8]

        self.service.add_request(
            request_id,
            {
                "guild_id": interaction.guild_id,
                "guild_name": interaction.guild.name,
                "type": change_type,
                "image_bytes": image_bytes,
                "content_type": content_type,
                "requester_id": interaction.user.id,
                "channel_id": interaction.channel_id,
                "created_at": datetime.now(TZ_OFFSET).isoformat(),
            },
        )

        type_name = (
            tx("bot_appearance.avatar")
            if change_type == "avatar"
            else tx("bot_appearance.banner")
        )
        embed = discord.Embed(
            title=tx("bot_appearance.review_bot_change_request", v0=(type_name)),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("bot_appearance.server"),
            value=f"{interaction.guild.name} ({interaction.guild_id})",
            inline=False,
        )
        embed.add_field(
            name=tx("bot_appearance.requester"),
            value=f"<@{interaction.user.id}> ({interaction.user.id})",
            inline=False,
        )
        embed.add_field(
            name=tx("bot_appearance.change_type"), value=type_name, inline=True
        )
        embed.add_field(
            name=tx("bot_appearance.request_id"), value=request_id, inline=True
        )
        embed.set_image(url=image_url)
        embed.set_footer(
            text=tx("bot_appearance.this_change_request_is_awaiting_review")
        )

        try:
            for dev_id in DEVELOPER_IDS:
                developer = await self.bot.fetch_user(dev_id)
                view = AppearanceApprovalView(request_id, self)
                await developer.send(embed=embed, view=view)
        except Exception as e:
            self.service.remove_request(request_id)
            raise RuntimeError(tx("bot_appearance.could_not_notify_developers", v0=(e)))

    @localized("interaction")
    async def handle_approval(
        self,
        interaction: discord.Interaction,
        request_id: str,
        approved: bool,
    ) -> None:
        """處理審核結果"""
        request = self.service.remove_request(request_id)
        if not request:
            await interaction.response.send_message(
                tx("bot_appearance.failed_this_request_has_expired_or"), ephemeral=True
            )
            return

        change_type = request["type"]
        type_name = (
            tx("bot_appearance.avatar")
            if change_type == "avatar"
            else tx("bot_appearance.banner")
        )

        if approved:
            guild = self.bot.get_guild(request["guild_id"])
            if not guild:
                await interaction.response.send_message(
                    tx("bot_appearance.failed_server_not_found"), ephemeral=True
                )
                return

            await interaction.response.defer()
            try:
                b64 = base64.b64encode(request["image_bytes"]).decode("ascii")
                data_uri = f"data:{request['content_type']};base64,{b64}"
                route = discord.http.Route(
                    "PATCH",
                    "/guilds/{guild_id}/members/@me",
                    guild_id=guild.id,
                )
                payload_key = "avatar" if change_type == "avatar" else "banner"
                await self.bot.http.request(route, json={payload_key: data_uri})

                # 更新審核訊息
                embed = discord.Embed(
                    title=tx("bot_appearance.approved_change", v0=(type_name)),
                    description=tx(
                        "bot_appearance.applied_to", v0=(request["guild_name"])
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                )
                await interaction.edit_original_response(embed=embed, view=None)

                # 通知申請者
                try:
                    channel = self.bot.get_channel(request["channel_id"])
                    if isinstance(
                        channel,
                        (
                            discord.TextChannel,
                            discord.Thread,
                            discord.VoiceChannel,
                            discord.StageChannel,
                        ),
                    ):
                        notify_embed = discord.Embed(
                            title=tx("bot_appearance.success_updated", v0=(type_name)),
                            description=(
                                tx(
                                    "bot_appearance.the_change_requested_by_was_approved",
                                    v0=(request["requester_id"]),
                                    v1=(type_name),
                                )
                            ),
                            color=discord.Color.from_rgb(46, 204, 113),
                        )
                        await channel.send(embed=notify_embed)
                except Exception:
                    pass

            except Exception as e:
                await interaction.followup.send(
                    tx("bot_appearance.failed_could_not_apply_change", v0=(e)),
                    ephemeral=True,
                )
        else:
            # 拒絕
            embed = discord.Embed(
                title=tx("bot_appearance.rejected_change", v0=(type_name)),
                description=tx(
                    "bot_appearance.the_request_from_was_rejected",
                    v0=(request["guild_name"]),
                ),
                color=discord.Color.from_rgb(231, 76, 60),
            )
            await interaction.response.edit_message(embed=embed, view=None)

            # 通知申請者
            try:
                channel = self.bot.get_channel(request["channel_id"])
                if isinstance(
                    channel,
                    (
                        discord.TextChannel,
                        discord.Thread,
                        discord.VoiceChannel,
                        discord.StageChannel,
                    ),
                ):
                    notify_embed = discord.Embed(
                        title=tx(
                            "bot_appearance.rejected_change_not_approved",
                            v0=(type_name),
                        ),
                        description=(
                            tx(
                                "bot_appearance.the_change_requested_by_was_rejected",
                                v0=(request["requester_id"]),
                                v1=(type_name),
                            )
                        ),
                        color=discord.Color.from_rgb(231, 76, 60),
                    )
                    await channel.send(embed=notify_embed)
            except Exception:
                pass

    @appearance_group.command(
        name="name", description="Change the bot's nickname in this server"
    )
    @app_commands.describe(name="New nickname (leave empty to reset)")
    @localized("interaction")
    async def change_name(
        self, interaction: discord.Interaction, name: str | None = None
    ) -> None:
        """更改機器人在伺服器中的暱稱"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                tx("bot_appearance.failed_administrator_permission_is_required"),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            bot_member = interaction.guild.me
            await bot_member.edit(nick=name)

            if name:
                embed = discord.Embed(
                    title=tx("bot_appearance.success_name_changed"),
                    description=tx("bot_appearance.the_bot_s_name_in_this", v0=(name)),
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            else:
                embed = discord.Embed(
                    title=tx("bot_appearance.success_name_reset"),
                    description=tx("bot_appearance.the_bot_s_name_has_been"),
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                tx("bot_appearance.failed_the_bot_lacks_permission_to"), ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                tx("bot_appearance.failed_could_not_change_name", v0=(e)),
                ephemeral=True,
            )

    @appearance_group.command(
        name="avatar", description="Change the bot's avatar in this server (reviewed)"
    )
    @app_commands.describe(image="New avatar image (sent to the developers for review)")
    @localized("interaction")
    async def change_avatar(
        self, interaction: discord.Interaction, image: discord.Attachment
    ) -> None:
        """更改機器人在此伺服器的頭像 (需審核)"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                tx("bot_appearance.failed_administrator_permission_is_required"),
                ephemeral=True,
            )
            return

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                tx("bot_appearance.failed_upload_a_valid_image_file"), ephemeral=True
            )
            return

        if image.size > MAX_IMAGE_SIZE:
            await interaction.response.send_message(
                tx("bot_appearance.failed_the_image_must_not_exceed"), ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            image_bytes = await image.read()
            await self.send_approval_request(
                interaction,
                change_type="avatar",
                image_bytes=image_bytes,
                content_type=image.content_type,
                image_url=image.url,
            )

            embed = discord.Embed(
                title=tx("bot_appearance.pending_avatar_change_submitted"),
                description=tx("bot_appearance.the_avatar_change_request_has_been"),
                color=discord.Color.from_rgb(241, 196, 15),
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                tx("bot_appearance.failed_could_not_submit_for_review", v0=(e)),
                ephemeral=True,
            )

    @appearance_group.command(
        name="banner", description="Change the bot's banner in this server (reviewed)"
    )
    @app_commands.describe(image="New banner image (sent to the developers for review)")
    @localized("interaction")
    async def change_banner(
        self, interaction: discord.Interaction, image: discord.Attachment
    ) -> None:
        """更改機器人在此伺服器的橫幅 (需審核)"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                tx("bot_appearance.failed_administrator_permission_is_required"),
                ephemeral=True,
            )
            return

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                tx("bot_appearance.failed_upload_a_valid_image_file"), ephemeral=True
            )
            return

        if image.size > MAX_IMAGE_SIZE:
            await interaction.response.send_message(
                tx("bot_appearance.failed_the_image_must_not_exceed"), ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            image_bytes = await image.read()
            await self.send_approval_request(
                interaction,
                change_type="banner",
                image_bytes=image_bytes,
                content_type=image.content_type,
                image_url=image.url,
            )

            embed = discord.Embed(
                title=tx("bot_appearance.pending_banner_change_submitted"),
                description=tx("bot_appearance.the_banner_change_request_has_been"),
                color=discord.Color.from_rgb(241, 196, 15),
            )
            embed.set_image(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                tx("bot_appearance.failed_could_not_submit_for_review", v0=(e)),
                ephemeral=True,
            )

    @appearance_group.command(
        name="reset", description="Reset the bot's avatar or banner in this server"
    )
    @app_commands.describe(target="What to reset")
    @app_commands.choices(
        target=[
            app_commands.Choice(name="Avatar", value="avatar"),
            app_commands.Choice(name="Banner", value="banner"),
            app_commands.Choice(name="Avatar and banner", value="both"),
        ]
    )
    @localized("interaction")
    async def reset_appearance(
        self,
        interaction: discord.Interaction,
        target: app_commands.Choice[str],
    ) -> None:
        """將機器人伺服器級頭像/橫幅還原為全域預設"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                tx("bot_appearance.failed_administrator_permission_is_required"),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        target_name_map = {
            "avatar": tx("bot_appearance.avatar"),
            "banner": tx("bot_appearance.banner"),
            "both": tx("bot_appearance.avatar_and_banner"),
        }
        target_name = target_name_map[target.value]

        try:
            route = discord.http.Route(
                "PATCH",
                "/guilds/{guild_id}/members/@me",
                guild_id=interaction.guild_id,
            )

            payload = {}
            if target.value in ("avatar", "both"):
                payload["avatar"] = None
            if target.value in ("banner", "both"):
                payload["banner"] = None

            await self.bot.http.request(route, json=payload)

            embed = discord.Embed(
                title=tx("bot_appearance.success_appearance_reset"),
                description=tx(
                    "bot_appearance.the_bot_s_in_this_server", v0=(target_name)
                ),
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )
            embed.add_field(
                name=tx("bot_appearance.performed_by"),
                value=f"{interaction.user.mention} ({interaction.user.id})",
                inline=False,
            )
            await interaction.followup.send(embed=embed)

        except discord.Forbidden:
            await interaction.followup.send(
                tx("bot_appearance.failed_the_bot_lacks_the_required"), ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                tx("bot_appearance.failed_api_request_failed", v0=(e)), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(BotAppearance(bot))

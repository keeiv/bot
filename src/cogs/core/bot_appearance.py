import base64
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import uuid

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# 開發者 ID
DEVELOPER_ID = 241619561760292866

# 圖片大小限制 8MB
MAX_IMAGE_SIZE = 8 * 1024 * 1024


class AppearanceApprovalView(ui.View):
    """外觀變更審核視圖"""

    def __init__(self, request_id: str, cog: "BotAppearance"):
        super().__init__(timeout=None)
        self.request_id = request_id
        self.cog = cog

    @ui.button(label="核准", style=discord.ButtonStyle.success)
    async def approve_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """核准變更"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 你沒有權限審核", ephemeral=True
            )
            return
        await self.cog.handle_approval(interaction, self.request_id, approved=True)

    @ui.button(label="拒絕", style=discord.ButtonStyle.danger)
    async def reject_button(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        """拒絕變更"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 你沒有權限審核", ephemeral=True
            )
            return
        await self.cog.handle_approval(interaction, self.request_id, approved=False)


class BotAppearance(commands.Cog):
    """機器人外觀設定 Cog (伺服器級)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending_requests = {}

    appearance_group = app_commands.Group(
        name="bot_appearance",
        description="機器人在此伺服器的外觀設定",
        default_permissions=discord.Permissions(administrator=True),
    )

    async def send_approval_request(
        self,
        interaction: discord.Interaction,
        change_type: str,
        image_bytes: bytes,
        content_type: str,
        image_url: str,
    ):
        """發送審核請求給開發者"""
        request_id = str(uuid.uuid4())[:8]

        self.pending_requests[request_id] = {
            "guild_id": interaction.guild_id,
            "guild_name": interaction.guild.name,
            "type": change_type,
            "image_bytes": image_bytes,
            "content_type": content_type,
            "requester_id": interaction.user.id,
            "channel_id": interaction.channel_id,
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
        }

        type_name = "頭像" if change_type == "avatar" else "橫幅"
        embed = discord.Embed(
            title=f"[審核] 機器人{type_name}變更請求",
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="伺服器",
            value=f"{interaction.guild.name} ({interaction.guild_id})",
            inline=False,
        )
        embed.add_field(
            name="申請者",
            value=f"<@{interaction.user.id}> ({interaction.user.id})",
            inline=False,
        )
        embed.add_field(name="變更類型", value=type_name, inline=True)
        embed.add_field(name="請求 ID", value=request_id, inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text="請審核此變更請求")

        try:
            developer = await self.bot.fetch_user(DEVELOPER_ID)
            view = AppearanceApprovalView(request_id, self)
            await developer.send(embed=embed, view=view)
        except Exception as e:
            del self.pending_requests[request_id]
            raise RuntimeError(f"無法通知開發者: {e}")

    async def handle_approval(
        self,
        interaction: discord.Interaction,
        request_id: str,
        approved: bool,
    ):
        """處理審核結果"""
        request = self.pending_requests.pop(request_id, None)
        if not request:
            await interaction.response.send_message(
                "[失敗] 此請求已過期或不存在", ephemeral=True
            )
            return

        change_type = request["type"]
        type_name = "頭像" if change_type == "avatar" else "橫幅"

        if approved:
            guild = self.bot.get_guild(request["guild_id"])
            if not guild:
                await interaction.response.send_message(
                    "[失敗] 找不到伺服器", ephemeral=True
                )
                return

            try:
                b64 = base64.b64encode(request["image_bytes"]).decode("ascii")
                data_uri = (
                    f"data:{request['content_type']};base64,{b64}"
                )
                route = discord.http.Route(
                    "PATCH",
                    "/guilds/{guild_id}/members/@me",
                    guild_id=guild.id,
                )
                payload_key = "avatar" if change_type == "avatar" else "banner"
                await self.bot.http.request(
                    route, json={payload_key: data_uri}
                )

                # 更新審核訊息
                embed = discord.Embed(
                    title=f"[已核准] {type_name}變更",
                    description=f"已套用至 {request['guild_name']}",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
                await interaction.response.edit_message(embed=embed, view=None)

                # 通知申請者
                try:
                    channel = self.bot.get_channel(request["channel_id"])
                    if channel:
                        notify_embed = discord.Embed(
                            title=f"[成功] {type_name}已更新",
                            description=(
                                f"<@{request['requester_id']}> 申請的"
                                f"{type_name}變更已通過審核並套用"
                            ),
                            color=discord.Color.from_rgb(46, 204, 113),
                        )
                        await channel.send(embed=notify_embed)
                except Exception:
                    pass

            except Exception as e:
                await interaction.response.send_message(
                    f"[失敗] 套用失敗: {e}", ephemeral=True
                )
        else:
            # 拒絕
            embed = discord.Embed(
                title=f"[已拒絕] {type_name}變更",
                description=f"來自 {request['guild_name']} 的請求已拒絕",
                color=discord.Color.from_rgb(231, 76, 60),
            )
            await interaction.response.edit_message(embed=embed, view=None)

            # 通知申請者
            try:
                channel = self.bot.get_channel(request["channel_id"])
                if channel:
                    notify_embed = discord.Embed(
                        title=f"[拒絕] {type_name}變更未通過",
                        description=(
                            f"<@{request['requester_id']}> 申請的"
                            f"{type_name}變更已被開發者拒絕"
                        ),
                        color=discord.Color.from_rgb(231, 76, 60),
                    )
                    await channel.send(embed=notify_embed)
            except Exception:
                pass

    @appearance_group.command(
        name="name", description="更改機器人在此伺服器的名稱"
    )
    @app_commands.describe(name="新的暱稱 (留空則還原預設)")
    async def change_name(
        self, interaction: discord.Interaction, name: str = None
    ):
        """更改機器人在伺服器中的暱稱"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "[失敗] 你需要管理員權限", ephemeral=True
            )
            return

        try:
            bot_member = interaction.guild.me
            await bot_member.edit(nick=name)

            if name:
                embed = discord.Embed(
                    title="[成功] 名稱已更改",
                    description=f"機器人在此伺服器的名稱已更改為: **{name}**",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            else:
                embed = discord.Embed(
                    title="[成功] 名稱已還原",
                    description="機器人名稱已還原為預設",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
            await interaction.response.send_message(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "[失敗] 機器人缺少更改暱稱的權限", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"[失敗] 無法更改名稱: {e}", ephemeral=True
            )

    @appearance_group.command(
        name="avatar", description="更改機器人在此伺服器的頭像 (需審核)"
    )
    @app_commands.describe(image="新的頭像圖片 (將送交開發者審核)")
    async def change_avatar(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        """更改機器人在此伺服器的頭像 (需審核)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "[失敗] 你需要管理員權限", ephemeral=True
            )
            return

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "[失敗] 請上傳有效的圖片檔案", ephemeral=True
            )
            return

        if image.size > MAX_IMAGE_SIZE:
            await interaction.response.send_message(
                "[失敗] 圖片大小不能超過 8MB", ephemeral=True
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
                title="[待審核] 頭像變更已提交",
                description="你的頭像變更請求已發送給開發者審核，請耐心等待",
                color=discord.Color.from_rgb(241, 196, 15),
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"[失敗] 提交審核失敗: {e}", ephemeral=True
            )

    @appearance_group.command(
        name="banner", description="更改機器人在此伺服器的橫幅 (需審核)"
    )
    @app_commands.describe(image="新的橫幅圖片 (將送交開發者審核)")
    async def change_banner(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        """更改機器人在此伺服器的橫幅 (需審核)"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "[失敗] 你需要管理員權限", ephemeral=True
            )
            return

        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "[失敗] 請上傳有效的圖片檔案", ephemeral=True
            )
            return

        if image.size > MAX_IMAGE_SIZE:
            await interaction.response.send_message(
                "[失敗] 圖片大小不能超過 8MB", ephemeral=True
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
                title="[待審核] 橫幅變更已提交",
                description="你的橫幅變更請求已發送給開發者審核，請耐心等待",
                color=discord.Color.from_rgb(241, 196, 15),
            )
            embed.set_image(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"[失敗] 提交審核失敗: {e}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(BotAppearance(bot))

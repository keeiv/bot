import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

# 開發者 ID
DEVELOPER_ID = 241619561760292866


class ImageReviewView(ui.View):
    """圖片審核按鈕視圖"""

    def __init__(
        self,
        guild_id: int,
        change_type: str,
        image_url: str,
        requester_id: int,
    ):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.change_type = change_type
        self.image_url = image_url
        self.requester_id = requester_id

    @ui.button(label="核准", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        """核准圖片變更"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 只有開發者可以審核", ephemeral=True
            )
            return

        await interaction.response.defer()

        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            await interaction.followup.send("[失敗] 找不到該伺服器")
            return

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(self.image_url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("[失敗] 無法下載圖片，連結可能已過期")
                        return
                    image_bytes = await resp.read()

            if self.change_type == "icon":
                await guild.edit(icon=image_bytes)
                type_text = "頭像"
            else:
                await guild.edit(banner=image_bytes)
                type_text = "橫幅"

            # 更新審核訊息
            embed = discord.Embed(
                title=f"[已核准] 伺服器{type_text}變更",
                description=f"**伺服器:** {guild.name}\n**申請者:** <@{self.requester_id}>\n**狀態:** 已核准",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            embed.set_image(url=self.image_url)
            await interaction.edit_original_response(embed=embed, view=None)

            # 通知申請者
            try:
                requester = await interaction.client.fetch_user(self.requester_id)
                notify_embed = discord.Embed(
                    title=f"[通知] 伺服器{type_text}變更已核准",
                    description=f"您在 **{guild.name}** 提交的{type_text}變更已通過審核並套用。",
                    color=discord.Color.from_rgb(46, 204, 113),
                )
                await requester.send(embed=notify_embed)
            except Exception:
                pass

        except discord.Forbidden:
            await interaction.followup.send(
                f"[失敗] 機器人缺少管理伺服器的權限"
            )
        except Exception as e:
            await interaction.followup.send(f"[失敗] 套用變更失敗: {e}")

    @ui.button(label="駁回", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        """駁回圖片變更"""
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 只有開發者可以審核", ephemeral=True
            )
            return

        guild = interaction.client.get_guild(self.guild_id)
        guild_name = guild.name if guild else f"ID: {self.guild_id}"
        type_text = "頭像" if self.change_type == "icon" else "橫幅"

        embed = discord.Embed(
            title=f"[已駁回] 伺服器{type_text}變更",
            description=f"**伺服器:** {guild_name}\n**申請者:** <@{self.requester_id}>\n**狀態:** 已駁回",
            color=discord.Color.from_rgb(231, 76, 60),
        )
        embed.set_image(url=self.image_url)
        await interaction.response.edit_message(embed=embed, view=None)

        # 通知申請者
        try:
            requester = await interaction.client.fetch_user(self.requester_id)
            notify_embed = discord.Embed(
                title=f"[通知] 伺服器{type_text}變更已駁回",
                description=f"您在 **{guild_name}** 提交的{type_text}變更未通過審核。",
                color=discord.Color.from_rgb(231, 76, 60),
            )
            await requester.send(embed=notify_embed)
        except Exception:
            pass


class ServerAppearance(commands.Cog):
    """伺服器外觀設定 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    appearance_group = app_commands.Group(
        name="server_appearance",
        description="伺服器外觀設定",
        default_permissions=discord.Permissions(administrator=True),
    )

    @appearance_group.command(name="name", description="更改機器人在此伺服器的暱稱")
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

    @appearance_group.command(name="icon", description="申請更改伺服器頭像 (需審核)")
    @app_commands.describe(image="新的伺服器頭像圖片")
    async def change_icon(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        """申請更改伺服器頭像"""
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

        await interaction.response.defer()

        try:
            # 傳送審核請求給開發者
            developer = await self.bot.fetch_user(DEVELOPER_ID)

            review_embed = discord.Embed(
                title="[審核] 伺服器頭像變更申請",
                description=(
                    f"**伺服器:** {interaction.guild.name} ({interaction.guild.id})\n"
                    f"**申請者:** {interaction.user.mention} ({interaction.user.id})\n"
                    f"**檔案:** {image.filename} ({image.size // 1024} KB)"
                ),
                color=discord.Color.from_rgb(241, 196, 15),
            )
            review_embed.set_image(url=image.url)

            view = ImageReviewView(
                guild_id=interaction.guild.id,
                change_type="icon",
                image_url=image.url,
                requester_id=interaction.user.id,
            )
            await developer.send(embed=review_embed, view=view)

            embed = discord.Embed(
                title="[已提交] 伺服器頭像變更申請",
                description="您的申請已提交審核，審核通過後將自動套用。",
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"[失敗] 無法提交審核: {e}", ephemeral=True
            )

    @appearance_group.command(name="banner", description="申請更改伺服器橫幅 (需審核)")
    @app_commands.describe(image="新的伺服器橫幅圖片")
    async def change_banner(
        self, interaction: discord.Interaction, image: discord.Attachment
    ):
        """申請更改伺服器橫幅"""
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

        # 檢查伺服器 Boost 等級
        if interaction.guild.premium_tier < 2:
            await interaction.response.send_message(
                "[失敗] 伺服器需要 Boost 等級 2 以上才能設定橫幅",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            # 傳送審核請求給開發者
            developer = await self.bot.fetch_user(DEVELOPER_ID)

            review_embed = discord.Embed(
                title="[審核] 伺服器橫幅變更申請",
                description=(
                    f"**伺服器:** {interaction.guild.name} ({interaction.guild.id})\n"
                    f"**申請者:** {interaction.user.mention} ({interaction.user.id})\n"
                    f"**檔案:** {image.filename} ({image.size // 1024} KB)\n"
                    f"**Boost 等級:** {interaction.guild.premium_tier}"
                ),
                color=discord.Color.from_rgb(241, 196, 15),
            )
            review_embed.set_image(url=image.url)

            view = ImageReviewView(
                guild_id=interaction.guild.id,
                change_type="banner",
                image_url=image.url,
                requester_id=interaction.user.id,
            )
            await developer.send(embed=review_embed, view=view)

            embed = discord.Embed(
                title="[已提交] 伺服器橫幅變更申請",
                description="您的申請已提交審核，審核通過後將自動套用。",
                color=discord.Color.from_rgb(52, 152, 219),
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"[失敗] 無法提交審核: {e}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(ServerAppearance(bot))

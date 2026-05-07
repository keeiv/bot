import asyncio
from datetime import datetime
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks

from src.services.management_service import ManagementService
from src.services.management_service import _format_time


class Management(commands.Cog):
    """伺服器管理指令，包含倉庫追蹤、身份組分配、表情符號管理和歡迎訊息"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = ManagementService()

        self._repo_poll_task.start()

    def cog_unload(self):
        self._repo_poll_task.cancel()

    # Repository tracking commands
    repo_track = app_commands.Group(
        name="repo_track", description="追蹤倉庫更新與拉取請求"
    )

    @repo_track.command(name="add", description="新增 keeiv/bot 倉庫追蹤")
    @app_commands.describe(channel="發送通知的頻道")
    async def repo_track_add(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"
        owner = "keeiv"
        repo = "bot"

        if guild_id not in self.service.config:
            self.service.config[guild_id] = {}
        if "tracked_repos" not in self.service.config[guild_id]:
            self.service.config[guild_id]["tracked_repos"] = {}

        self.service.config[guild_id]["tracked_repos"][repo_key] = {
            "owner": owner,
            "repo": repo,
            "channel_id": channel.id,
            "last_commit": None,
            "last_pr": None,
        }

        self.service.save()
        await interaction.response.send_message(
            f"[成功] 已開始在 {channel.mention} 追蹤 {repo_key} 的更新"
        )

    @repo_track.command(name="remove", description="移除 keeiv/bot 倉庫追蹤")
    async def repo_track_remove(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)
        repo_key = "keeiv/bot"

        if (
            guild_id in self.service.config
            and "tracked_repos" in self.service.config[guild_id]
            and repo_key in self.service.config[guild_id]["tracked_repos"]
        ):

            del self.service.config[guild_id]["tracked_repos"][repo_key]
            self.service.save()
            await interaction.response.send_message(f"[成功] 已停止追蹤 {repo_key}")
        else:
            await interaction.response.send_message(
                f"[提示] {repo_key} 目前未被追蹤", ephemeral=True
            )

    @repo_track.command(name="status", description="顯示追蹤狀態")
    async def repo_track_status(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if (
            guild_id not in self.service.config
            or "tracked_repos" not in self.service.config[guild_id]
            or not self.service.config[guild_id]["tracked_repos"]
        ):

            await interaction.response.send_message(
                "[提示] 目前沒有追蹤任何倉庫", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="keeiv/bot 倉庫追蹤狀態", color=discord.Color.from_rgb(52, 152, 219)
        )

        repo_key = "keeiv/bot"
        if (
            guild_id in self.service.config
            and "tracked_repos" in self.service.config[guild_id]
            and repo_key in self.service.config[guild_id]["tracked_repos"]
        ):

            data = self.service.config[guild_id]["tracked_repos"][repo_key]
            channel = self.bot.get_channel(data["channel_id"])
            channel_name = (
                channel.mention
                if channel
                else f"未知頻道 ({data['channel_id']})"
            )

            embed.add_field(
                name=repo_key,
                value=f"頻道: {channel_name}\n最後 Commit: {data.get('last_commit', '尚無')}\n最後 PR: {data.get('last_pr', '尚無')}",
                inline=False,
            )
        else:
            embed.description = "keeiv/bot 倉庫目前未被追蹤"

        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=5)
    async def _repo_poll_task(self):
        """每 5 分鐘檢查倉庫更新"""
        if not self.service.config:
            return

        for guild_id, guild_config in list(self.service.config.items()):
            if "tracked_repos" not in guild_config or not guild_config["tracked_repos"]:
                continue

            for repo_key, repo_data in list(guild_config["tracked_repos"].items()):
                try:
                    events = await self.service.check_repo_updates(guild_id, repo_key, repo_data)
                    for event in events:
                        channel = self.bot.get_channel(event["channel_id"])
                        if not channel:
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
                            embed.add_field(name="[日期]", value=event["date"], inline=True)
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
                            embed.add_field(name="[PR 編號]", value=event["pr_number"], inline=True)
                            embed.add_field(name="[狀態]", value=event["state"], inline=True)
                            await channel.send(embed=embed)
                except Exception as e:
                    print(f"Error checking {repo_key}: {e}")
                    continue

    # Role management commands
    role = app_commands.Group(name="role", description="身份組管理指令")

    @role.command(name="assign", description="為用戶分配身份組")
    @app_commands.describe(user="要分配身份組的用戶", role="要分配的身份組")
    async def role_assign(
        self, interaction: discord.Interaction, user: discord.Member, role: discord.Role
    ):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "[失敗] 你需要「管理身份組」權限",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                "[失敗] 無法操作 @everyone 身份組",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "[失敗] 無法操作由機器人/整合管理的身份組",
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                "[失敗] 你無法分配高於或等於你最高身份組的角色",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await user.add_roles(role)
            await interaction.followup.send(
                f"[成功] 已將 {role.mention} 分配給 {user.mention}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "[失敗] 機器人沒有權限分配該身份組",
            )

    @role.command(name="remove", description="從用戶移除身份組")
    @app_commands.describe(user="要移除身份組的用戶", role="要移除的身份組")
    async def role_remove(
        self, interaction: discord.Interaction, user: discord.Member, role: discord.Role
    ):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "[失敗] 你需要「管理身份組」權限",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                "[失敗] 無法操作 @everyone 身份組",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "[失敗] 無法操作由機器人/整合管理的身份組",
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                "[失敗] 你無法移除高於或等於你最高身份組的角色",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await user.remove_roles(role)
            await interaction.followup.send(
                f"[成功] 已從 {user.mention} 移除 {role.mention}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "[失敗] 機器人沒有權限移除該身份組",
            )

    # Emoji management commands
    emoji = app_commands.Group(name="emoji", description="表情符號管理指令")

    @emoji.command(name="get", description="獲取表情符號大圖")
    @app_commands.describe(emoji="要獲取的表情符號")
    async def emoji_get(self, interaction: discord.Interaction, emoji: str):
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
                        "[失敗] 無效的表情符號格式", ephemeral=True
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
                        "[失敗] 無效的表情符號格式", ephemeral=True
                    )
                    return
            else:
                await interaction.response.send_message(
                    "[失敗] 請使用自訂表情符號", ephemeral=True
                )
                return

            embed = discord.Embed(title="[表情符號] 大圖", color=discord.Color.from_rgb(52, 152, 219))
            embed.set_image(url=url)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"[失敗] 取得表情符號失敗: {e}", ephemeral=True
            )

    @emoji.command(name="upload", description="上傳表情符號到伺服器")
    @app_commands.describe(name="表情符號名稱", image="要上傳為表情符號的圖片檔案")
    async def emoji_upload(
        self, interaction: discord.Interaction, name: str, image: discord.Attachment
    ):
        if not interaction.user.guild_permissions.manage_emojis:
            await interaction.response.send_message(
                "[失敗] 你需要「管理表情符號」權限",
                ephemeral=True,
            )
            return

        if not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                "[失敗] 請上傳圖片檔案", ephemeral=True
            )
            return

        try:
            image_data = await image.read()
            emoji = await interaction.guild.create_custom_emoji(
                name=name, image=image_data, reason=f"由 {interaction.user} 上傳"
            )
            await interaction.response.send_message(
                f"[成功] 已上傳表情符號: {emoji}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "[失敗] 機器人沒有權限上傳表情符號", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"[失敗] 上傳表情符號失敗: {e}", ephemeral=True
            )

    # Welcome message commands
    welcome = app_commands.Group(name="welcome", description="歡迎訊息管理")

    @welcome.command(name="setup", description="設定新成員歡迎訊息")
    @app_commands.describe(
        channel="發送歡迎訊息的頻道",
        message="歡迎訊息範本",
        embed_title="嵌入訊息標題",
        embed_color="嵌入訊息顏色 (hex 格式)",
        auto_role="自動分配的角色",
        send_dm="同時發送私訊",
    )
    async def welcome_setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = "歡迎 {user} 來到 {server}！",
        embed_title: str = None,
        embed_color: str = None,
        auto_role: discord.Role = None,
        send_dm: bool = False,
    ):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        guild_id = str(interaction.guild.id)

        if guild_id not in self.service.config:
            self.service.config[guild_id] = {}

        welcome_config = {
            "channel_id": channel.id,
            "message": message,
            "send_dm": send_dm,
        }

        if embed_title:
            welcome_config["embed_title"] = embed_title

        if embed_color:
            try:
                welcome_config["embed_color"] = int(embed_color.lstrip("#"), 16)
            except ValueError:
                await interaction.followup.send(
                    "[失敗] 無效的顏色格式，請使用十六進位格式，例如 #FF5733", ephemeral=True
                )
                return

        if auto_role:
            if auto_role.is_default():
                await interaction.followup.send(
                    "[失敗] 無法將 @everyone 設為自動角色",
                    ephemeral=True,
                )
                return
            welcome_config["auto_role_id"] = auto_role.id

        self.service.config[guild_id]["welcome"] = welcome_config
        self.service.save()

        response_msg = f"[成功] 歡迎訊息將發送至 {channel.mention}"
        if auto_role:
            response_msg += f"\n自動角色: {auto_role.mention}"
        if send_dm:
            response_msg += "\n已啟用私訊通知"

        await interaction.followup.send(response_msg)

    @welcome.command(name="templates", description="預設歡迎訊息模板")
    async def welcome_templates(self, interaction: discord.Interaction):
        templates = [
            {
                "name": "基本",
                "message": "歡迎 {user} 來到 {server}！我們現在有 {count} 位成員！",
            },
            {
                "name": "友善",
                "message": "你好 {user}！歡迎來到 {server}！請隨意介紹你自己。",
            },
            {
                "name": "正式",
                "message": "{user} 您好，歡迎來到 {server}。請先閱讀規則，祝您在此愚快。",
            },
            {
                "name": "遊戲",
                "message": "{user} 加入了遊戲！歡迎來到 {server}！準備好了嗎？",
            },
            {
                "name": "社群",
                "message": "歡迎 {user} 加入我們的社群 {server}！你是第 {count} 位成員！",
            },
        ]

        embed = discord.Embed(
            title="[歡迎訊息] 預設模板",
            description="可使用變數: {user}, {server}, {count}, {created_at}",
            color=discord.Color.from_rgb(52, 152, 219),
        )

        for template in templates:
            embed.add_field(
                name=template["name"], value=template["message"], inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome.command(name="preview", description="預覽歡迎訊息")
    @app_commands.describe(test_user="測試用戶名稱", test_server="測試伺服器名稱")
    async def welcome_preview(
        self,
        interaction: discord.Interaction,
        test_user: str = None,
        test_server: str = None,
    ):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.service.config or "welcome" not in self.service.config[guild_id]:
            await interaction.response.send_message(
                "[失敗] 尚未設定歡迎訊息", ephemeral=True
            )
            return

        welcome_config = self.service.config[guild_id]["welcome"]

        user_mention = test_user or interaction.user.mention
        server_name = test_server or interaction.guild.name

        message = welcome_config["message"].format(
            user=user_mention,
            server=server_name,
            count=interaction.guild.member_count,
            created_at=interaction.guild.created_at.strftime("%Y/%m/%d"),
        )

        if "embed_title" in welcome_config or "embed_color" in welcome_config:
            embed = discord.Embed(
                title=welcome_config.get("embed_title"),
                description=message,
                color=welcome_config.get("embed_color", discord.Color.from_rgb(52, 152, 219)),
            )
            embed.set_thumbnail(
                url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            embed.set_footer(text=f"第 {interaction.guild.member_count} 位成員")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"[預覽] {message}", ephemeral=True
            )

    @welcome.command(name="disable", description="停用歡迎訊息")
    async def welcome_disable(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        if guild_id in self.service.config and "welcome" in self.service.config[guild_id]:
            del self.service.config[guild_id]["welcome"]
            self.service.save()
            await interaction.response.send_message("[成功] 已停用歡迎訊息")
        else:
            await interaction.response.send_message(
                "[失敗] 歡迎訊息尚未啟用", ephemeral=True
            )

    # Auto role commands
    auto_role = app_commands.Group(name="auto_role", description="自動角色分配管理")

    @auto_role.command(name="setup", description="設定自動角色分配規則")
    @app_commands.describe(
        role="要分配的角色",
        delay="延遲分配時間（秒）",
        min_members="最小成員數要求",
        require_verification="需要通過驗證",
    )
    async def auto_role_setup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        delay: int = 0,
        min_members: int = 0,
        require_verification: bool = False,
    ):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "[失敗] 你需要「管理身份組」權限",
                ephemeral=True,
            )
            return

        if role.is_default():
            await interaction.response.send_message(
                "[失敗] 無法將 @everyone 設為自動角色",
                ephemeral=True,
            )
            return

        if role.managed:
            await interaction.response.send_message(
                "[失敗] 無法設定由機器人/整合管理的身份組為自動角色",
                ephemeral=True,
            )
            return

        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message(
                "[失敗] 你無法設定高於或等於你最高身份組的角色",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        if guild_id not in self.service.config:
            self.service.config[guild_id] = {}
        if "auto_roles" not in self.service.config[guild_id]:
            self.service.config[guild_id]["auto_roles"] = []

        role_config = {
            "role_id": role.id,
            "delay": delay,
            "min_members": min_members,
            "require_verification": require_verification,
        }

        self.service.config[guild_id]["auto_roles"].append(role_config)
        self.service.save()

        embed = discord.Embed(
            title="[成功] 自動角色已設定",
            description=f"角色 {role.mention} 將自動分配給新成員",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="[延遲]", value=f"{delay} 秒", inline=True)
        embed.add_field(name="[最少成員數]", value=str(min_members), inline=True)
        embed.add_field(
            name="[需要驗證]",
            value="是" if require_verification else "否",
            inline=True,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @auto_role.command(name="list", description="列出自動角色分配規則")
    async def auto_role_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.service.config or "auto_roles" not in self.service.config[guild_id]:
            await interaction.response.send_message(
                "[失敗] 尚未設定自動角色規則", ephemeral=True
            )
            return

        auto_roles = self.service.config[guild_id]["auto_roles"]

        embed = discord.Embed(title="[自動角色] 規則列表", color=discord.Color.from_rgb(52, 152, 219))

        for i, role_config in enumerate(auto_roles, 1):
            role = interaction.guild.get_role(role_config["role_id"])
            role_name = (
                role.name if role else f"已刪除的角色 ({role_config['role_id']})"
            )

            rules = []
            if role_config.get("delay", 0) > 0:
                rules.append(f"延遲: {role_config['delay']} 秒")
            if role_config.get("min_members", 0) > 0:
                rules.append(f"最少成員: {role_config['min_members']}")
            if role_config.get("require_verification", False):
                rules.append("需要驗證")

            rule_text = " | ".join(rules) if rules else "立即分配"
            embed.add_field(
                name=f"規則 {i}: {role_name}", value=rule_text, inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @auto_role.command(name="remove", description="移除自動角色分配規則")
    @app_commands.describe(rule_index="規則編號")
    async def auto_role_remove(self, interaction: discord.Interaction, rule_index: int):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "[失敗] 你需要「管理身份組」權限",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild.id)

        if (
            guild_id not in self.service.config
            or "auto_roles" not in self.service.config[guild_id]
            or rule_index < 1
            or rule_index > len(self.service.config[guild_id]["auto_roles"])
        ):
            await interaction.response.send_message(
                "[失敗] 無效的規則編號", ephemeral=True
            )
            return

        removed_role = self.service.config[guild_id]["auto_roles"].pop(rule_index - 1)
        self.service.save()

        role = interaction.guild.get_role(removed_role["role_id"])
        role_name = role.name if role else f"已刪除的角色 ({removed_role['role_id']})"

        await interaction.response.send_message(
            f"[成功] 已移除自動角色規則: {role_name}", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)

        # Handle welcome messages
        if guild_id in self.service.config and "welcome" in self.service.config[guild_id]:
            welcome_config = self.service.config[guild_id]["welcome"]
            channel = member.guild.get_channel(welcome_config["channel_id"])

            if channel:
                message = welcome_config["message"].format(
                    user=member.mention,
                    server=member.guild.name,
                    count=member.guild.member_count,
                    created_at=member.guild.created_at.strftime("%Y/%m/%d"),
                )

                if "embed_title" in welcome_config or "embed_color" in welcome_config:
                    embed = discord.Embed(
                        title=welcome_config.get("embed_title"),
                        description=message,
                        color=welcome_config.get("embed_color", discord.Color.from_rgb(52, 152, 219)),
                    )
                    embed.set_thumbnail(
                        url=member.guild.icon.url if member.guild.icon else None
                    )
                    embed.set_footer(text=f"第 {member.guild.member_count} 位成員")
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
                            await member.add_roles(role, reason="歡迎自動分配")
                except (discord.Forbidden, discord.HTTPException):
                    # 忽略權限或 API 錯誤，避免中斷歡迎流程
                    pass

        # Handle auto roles
        if guild_id in self.service.config and "auto_roles" in self.service.config[guild_id]:
            auto_roles = self.service.config[guild_id]["auto_roles"]

            for role_config in auto_roles:
                try:
                    # Check conditions
                    if role_config.get("min_members", 0) > member.guild.member_count:
                        continue

                    if role_config.get("require_verification", False):
                        if not member.verified:
                            continue

                    role = member.guild.get_role(role_config["role_id"])
                    if not role:
                        continue

                    # Apply delay if needed
                    if role_config.get("delay", 0) > 0:
                        await asyncio.sleep(role_config["delay"])

                    await member.add_roles(role, reason="自動角色分配")

                except (discord.Forbidden, discord.HTTPException):
                    continue


async def setup(bot: commands.Bot):
    await bot.add_cog(Management(bot))

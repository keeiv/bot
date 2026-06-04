from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.services.temp_voice_service import TempVoiceService

TZ_OFFSET = timezone(timedelta(hours=8))
ENVC_PREFIX = "envc*"

_service = TempVoiceService()


class TempVoice(commands.Cog):
    """暫時語音頻道系統"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = _service

    # ─────────────────── 管理員斜線指令 ───────────────────

    temp_voice = app_commands.Group(
        name="temp_voice",
        description="暫時語音頻道系統管理（管理員專用）",
    )

    @temp_voice.command(name="setup", description="設定暫時語音頻道觸發房間")
    @app_commands.describe(
        trigger="使用者加入此頻道後自動建立暫時語音頻道",
        category="新建立的暫時語音頻道所在類別（預設與觸發頻道相同類別）",
        name_template="頻道名稱範本，使用 {username} 作為玩家名稱佔位符（預設：{username}的家）",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        trigger: discord.VoiceChannel,
        category: Optional[discord.CategoryChannel] = None,
        name_template: str = "{username}的家",
    ):
        """設定暫時語音頻道觸發房間"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限才能使用此指令", ephemeral=True
            )
            return

        if len(name_template) > 100:
            await interaction.response.send_message(
                "[失敗] 名稱範本不能超過 100 字元", ephemeral=True
            )
            return

        resolved_category_id = (
            category.id if category else trigger.category_id
        )

        self.service.save_guild_config(
            guild_id=interaction.guild.id,
            trigger_channel_id=trigger.id,
            category_id=resolved_category_id,
            name_template=name_template,
        )

        category_display = (
            category.name
            if category
            else (trigger.category.name if trigger.category else "無類別（根目錄）")
        )

        embed = discord.Embed(
            title="[成功] 暫時語音頻道系統已設定",
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="觸發頻道", value=trigger.mention, inline=True)
        embed.add_field(name="建立類別", value=category_display, inline=True)
        embed.add_field(
            name="名稱範本",
            value=f"`{name_template}`\n範例：`{name_template.replace('{username}', interaction.user.display_name)}`",
            inline=False,
        )
        embed.add_field(
            name="用戶指令前綴",
            value=f"`{ENVC_PREFIX}` — 輸入 `{ENVC_PREFIX}help` 查看完整說明",
            inline=False,
        )
        embed.set_footer(
            text=f"由 {interaction.user} 設定 | 伺服器：{interaction.guild.name}"
        )
        await interaction.response.send_message(embed=embed)

    @temp_voice.command(name="status", description="查看此伺服器的暫時語音頻道系統狀態")
    async def status(self, interaction: discord.Interaction):
        """顯示暫時語音頻道系統設定狀態"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限才能使用此指令", ephemeral=True
            )
            return

        config = self.service.get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "[提示] 此伺服器尚未設定暫時語音頻道系統，請使用 `/temp_voice setup` 設定",
                ephemeral=True,
            )
            return

        trigger_ch = interaction.guild.get_channel(config["trigger_channel_id"])
        category_id = config.get("category_id")
        category = interaction.guild.get_channel(category_id) if category_id else None
        active_channels = self.service.get_guild_channels(interaction.guild.id)

        embed = discord.Embed(
            title="[資訊] 暫時語音頻道系統狀態",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="觸發頻道",
            value=(
                trigger_ch.mention
                if trigger_ch
                else f"[已刪除] ID: {config['trigger_channel_id']}"
            ),
            inline=True,
        )
        embed.add_field(
            name="建立類別",
            value=category.name if category else "無類別（根目錄）",
            inline=True,
        )
        embed.add_field(
            name="名稱範本",
            value=f"`{config.get('name_template', '{username}的家')}`",
            inline=True,
        )
        embed.add_field(
            name="目前活躍暫時頻道數",
            value=str(len(active_channels)),
            inline=True,
        )
        embed.set_footer(text=f"伺服器：{interaction.guild.name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @temp_voice.command(name="disable", description="停用此伺服器的暫時語音頻道系統")
    async def disable(self, interaction: discord.Interaction):
        """停用暫時語音頻道系統"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "[失敗] 你需要「管理頻道」權限才能使用此指令", ephemeral=True
            )
            return

        config = self.service.get_guild_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(
                "[提示] 此伺服器尚未啟用暫時語音頻道系統", ephemeral=True
            )
            return

        self.service.remove_guild_config(interaction.guild.id)
        await interaction.response.send_message(
            "[成功] 已停用此伺服器的暫時語音頻道系統\n（現有暫時頻道不受影響，將在清空後自動刪除）"
        )

    # ─────────────────── 事件監聽 ───────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        """啟動時清理殘留的暫時頻道記錄"""
        all_ids = self.service.get_all_channel_ids()
        if not all_ids:
            return

        valid_ids: set[int] = set()
        for channel_id in all_ids:
            ch = self.bot.get_channel(channel_id)
            if ch is not None:
                valid_ids.add(channel_id)

        removed = self.service.remove_stale_channels(valid_ids)
        if removed:
            print(f"[TempVoice] 啟動清理：已移除 {removed} 筆殘留頻道記錄")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """監聽語音狀態：觸發建立、偵測空頻道刪除"""
        guild = member.guild
        config = self.service.get_guild_config(guild.id)

        # ── 使用者加入觸發頻道 → 建立暫時頻道 ──
        if (
            config
            and after.channel
            and after.channel.id == config["trigger_channel_id"]
        ):
            await self._create_temp_channel(member, guild, config)

        # ── 使用者離開頻道 → 若頻道為空則刪除 ──
        if before.channel and before.channel.id != (
            config["trigger_channel_id"] if config else None
        ):
            ch_data = self.service.get_channel(before.channel.id)
            if ch_data and len(before.channel.members) == 0:
                self.service.remove_channel(before.channel.id)
                try:
                    await before.channel.delete(reason="暫時語音頻道已清空，自動刪除")
                except discord.HTTPException:
                    pass

    async def _create_temp_channel(
        self,
        member: discord.Member,
        guild: discord.Guild,
        config: dict,
    ):
        """建立暫時語音頻道並將成員移入"""
        template = config.get("name_template", "{username}的家")
        channel_name = template.replace("{username}", member.display_name)

        category_id = config.get("category_id")
        category = guild.get_channel(category_id) if category_id else None

        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason=f"暫時語音頻道建立：{member} ({member.id})",
            )
            # 給創立者頻道管理權限
            await new_channel.set_permissions(
                member,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            self.service.save_channel(
                channel_id=new_channel.id,
                guild_id=guild.id,
                owner_id=member.id,
            )
            await member.move_to(new_channel, reason="移入暫時語音頻道")
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    # ─────────────────── envc* 前綴指令處理 ───────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """處理 envc* 前綴指令"""
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content.startswith(ENVC_PREFIX):
            return

        content = message.content[len(ENVC_PREFIX):].strip()
        parts = content.split(maxsplit=1)
        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        handlers = {
            "help": self._cmd_help,
            "name": self._cmd_name,
            "limit": self._cmd_limit,
            "bitrate": self._cmd_bitrate,
            "hide": self._cmd_hide,
            "unhide": self._cmd_unhide,
            "lock": self._cmd_lock,
            "unlock": self._cmd_unlock,
            "kick": self._cmd_kick,
            "ban": self._cmd_ban,
            "unban": self._cmd_unban,
            "transfer": self._cmd_transfer,
            "claim": self._cmd_claim,
        }

        handler = handlers.get(cmd)
        if handler:
            await handler(message, args)
        else:
            await message.reply(
                f"[失敗] 未知指令 `{ENVC_PREFIX}{cmd}`，輸入 `{ENVC_PREFIX}help` 查看所有可用指令",
                mention_author=False,
            )

    # ─────────────── 輔助函式 ───────────────

    def _get_user_owned_channel(
        self, member: discord.Member
    ) -> Optional[tuple[discord.VoiceChannel, dict]]:
        """取得使用者目前所在且擁有的暫時語音頻道"""
        voice = member.voice
        if not voice or not voice.channel:
            return None
        ch_data = self.service.get_channel(voice.channel.id)
        if not ch_data:
            return None
        if ch_data["owner_id"] != member.id:
            return None
        return voice.channel, ch_data  # type: ignore[return-value]

    def _get_user_in_temp_channel(
        self, member: discord.Member
    ) -> Optional[tuple[discord.VoiceChannel, dict]]:
        """取得使用者目前所在的暫時語音頻道（不限擁有者）"""
        voice = member.voice
        if not voice or not voice.channel:
            return None
        ch_data = self.service.get_channel(voice.channel.id)
        if not ch_data:
            return None
        return voice.channel, ch_data  # type: ignore[return-value]

    # ─────────────── 指令實作 ───────────────

    async def _cmd_help(self, message: discord.Message, args: str):
        embed = discord.Embed(
            title="[說明] 暫時語音頻道指令",
            description=(
                "以下指令僅限你自己建立（或已接管）的暫時語音頻道使用。\n"
                f"**指令前綴：`{ENVC_PREFIX}`**"
            ),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="基礎設定",
            value=(
                f"`{ENVC_PREFIX}name <名稱>` — 更改頻道名稱\n"
                f"`{ENVC_PREFIX}limit <人數>` — 設定人數上限（0 = 無限制，最大 99）\n"
                f"`{ENVC_PREFIX}bitrate <位元率>` — 設定位元率（8～96，單位 kbps）"
            ),
            inline=False,
        )
        embed.add_field(
            name="隱私設定",
            value=(
                f"`{ENVC_PREFIX}hide` — 隱藏頻道，其他玩家無法看見\n"
                f"`{ENVC_PREFIX}unhide` — 取消隱藏，頻道恢復可見\n"
                f"`{ENVC_PREFIX}lock` — 鎖定頻道，其他人無法加入（除非受邀）\n"
                f"`{ENVC_PREFIX}unlock` — 解除鎖定，所有人可自由加入"
            ),
            inline=False,
        )
        embed.add_field(
            name="管理頻道參與者",
            value=(
                f"`{ENVC_PREFIX}kick <@成員>` — 將成員踢出頻道\n"
                f"`{ENVC_PREFIX}ban <@成員>` — 永久封鎖成員加入此頻道\n"
                f"`{ENVC_PREFIX}unban <@成員>` — 解除某成員的封鎖"
            ),
            inline=False,
        )
        embed.add_field(
            name="擁有者管理",
            value=(
                f"`{ENVC_PREFIX}transfer <@成員>` — 將管理權轉移給頻道內其他成員\n"
                f"`{ENVC_PREFIX}claim` — 當原創建者已離開時，接管此頻道的管理權"
            ),
            inline=False,
        )
        embed.set_footer(
            text=f"伺服器：{message.guild.name} | 頻道 ID 僅限於你所在的暫時語音頻道有效"
        )
        await message.reply(embed=embed, mention_author=False)

    async def _cmd_name(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not args:
            await message.reply(
                f"[失敗] 請提供新頻道名稱，例如：`{ENVC_PREFIX}name 我的頻道`",
                mention_author=False,
            )
            return
        if len(args) > 100:
            await message.reply(
                "[失敗] 頻道名稱不能超過 100 字元", mention_author=False
            )
            return

        try:
            await channel.edit(name=args)
            await message.reply(f"[成功] 頻道名稱已更改為：**{args}**", mention_author=False)
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少修改此頻道的權限", mention_author=False)
        except discord.HTTPException as e:
            await message.reply(f"[失敗] 修改失敗（Discord 錯誤）：{e}", mention_author=False)

    async def _cmd_limit(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not args.isdigit():
            await message.reply(
                f"[失敗] 請輸入有效數字，例如：`{ENVC_PREFIX}limit 5`（0 表示無限制）",
                mention_author=False,
            )
            return
        limit = int(args)
        if limit < 0 or limit > 99:
            await message.reply(
                "[失敗] 人數限制必須在 0～99 之間（0 表示無限制）", mention_author=False
            )
            return

        try:
            await channel.edit(user_limit=limit)
            limit_text = f"{limit} 人" if limit > 0 else "無限制"
            await message.reply(
                f"[成功] 頻道人數上限已設定為：**{limit_text}**", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少修改此頻道的權限", mention_author=False)
        except discord.HTTPException as e:
            await message.reply(f"[失敗] 修改失敗（Discord 錯誤）：{e}", mention_author=False)

    async def _cmd_bitrate(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not args.isdigit():
            await message.reply(
                f"[失敗] 請輸入有效數字，例如：`{ENVC_PREFIX}bitrate 64`",
                mention_author=False,
            )
            return
        bitrate = int(args)

        # 依伺服器加成等級決定上限
        max_bitrate = message.guild.bitrate_limit // 1000
        if bitrate < 8 or bitrate > max_bitrate:
            await message.reply(
                f"[失敗] 位元率必須在 8～{max_bitrate} kbps 之間（此伺服器加成等級上限）",
                mention_author=False,
            )
            return

        try:
            await channel.edit(bitrate=bitrate * 1000)
            await message.reply(
                f"[成功] 頻道位元率已設定為：**{bitrate} kbps**", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少修改此頻道的權限", mention_author=False)
        except discord.HTTPException as e:
            await message.reply(f"[失敗] 修改失敗（Discord 錯誤）：{e}", mention_author=False)

    async def _cmd_hide(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(
                message.guild.default_role, view_channel=False
            )
            await message.reply(
                "[成功] 頻道已隱藏，其他人無法看見此頻道", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_unhide(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(
                message.guild.default_role, view_channel=True
            )
            await message.reply("[成功] 頻道已設為可見", mention_author=False)
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_lock(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(
                message.guild.default_role, connect=False
            )
            await message.reply(
                "[成功] 頻道已鎖定，其他人無法加入（除非受邀或管理員強制移動）",
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_unlock(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        try:
            await channel.set_permissions(
                message.guild.default_role, connect=True
            )
            await message.reply("[成功] 頻道已解除鎖定，所有人可自由加入", mention_author=False)
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_kick(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                f"[失敗] 請 @ 提及要踢出的成員，例如：`{ENVC_PREFIX}kick @成員`",
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if target.id == message.author.id:
            await message.reply("[失敗] 你無法踢出自己", mention_author=False)
            return

        if (
            target.voice
            and target.voice.channel
            and target.voice.channel.id == channel.id
        ):
            try:
                await target.move_to(
                    None, reason=f"暫時語音頻道踢出：由 {message.author} ({message.author.id})"
                )
                await message.reply(
                    f"[成功] 已將 {target.mention} 踢出頻道", mention_author=False
                )
            except discord.Forbidden:
                await message.reply("[失敗] 機器人缺少移動成員的權限", mention_author=False)
        else:
            await message.reply(
                f"[失敗] {target.mention} 目前不在此頻道內", mention_author=False
            )

    async def _cmd_ban(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                f"[失敗] 請 @ 提及要封鎖的成員，例如：`{ENVC_PREFIX}ban @成員`",
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if target.id == message.author.id:
            await message.reply("[失敗] 你無法封鎖自己", mention_author=False)
            return

        self.service.add_ban(channel.id, target.id)
        try:
            await channel.set_permissions(
                target, connect=False, view_channel=False
            )
            # 若目標在頻道內，一併踢出
            if (
                target.voice
                and target.voice.channel
                and target.voice.channel.id == channel.id
            ):
                await target.move_to(
                    None,
                    reason=f"暫時語音頻道封鎖：由 {message.author} ({message.author.id})",
                )
            await message.reply(
                f"[成功] 已永久封鎖 {target.mention} 加入此頻道", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_unban(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                f"[失敗] 請 @ 提及要解除封鎖的成員，例如：`{ENVC_PREFIX}unban @成員`",
                mention_author=False,
            )
            return

        target = message.mentions[0]
        self.service.remove_ban(channel.id, target.id)
        try:
            await channel.set_permissions(target, overwrite=None)
            await message.reply(
                f"[成功] 已解除 {target.mention} 的封鎖，對方可再次加入此頻道",
                mention_author=False,
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_transfer(self, message: discord.Message, args: str):
        result = self._get_user_owned_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在自己建立（或已接管）的暫時語音頻道中才能使用此指令",
                mention_author=False,
            )
            return
        channel, _ = result

        if not message.mentions:
            await message.reply(
                f"[失敗] 請 @ 提及要轉移給的成員，例如：`{ENVC_PREFIX}transfer @成員`",
                mention_author=False,
            )
            return

        target = message.mentions[0]
        if target.id == message.author.id:
            await message.reply("[失敗] 你已經是此頻道的擁有者", mention_author=False)
            return

        if not (
            target.voice
            and target.voice.channel
            and target.voice.channel.id == channel.id
        ):
            await message.reply(
                f"[失敗] {target.mention} 需要在此頻道內才能轉移管理權",
                mention_author=False,
            )
            return

        self.service.set_owner(channel.id, target.id)
        try:
            # 移除舊擁有者的額外權限
            await channel.set_permissions(message.author, overwrite=None)
            # 給新擁有者管理員權限
            await channel.set_permissions(
                target,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            await message.reply(
                f"[成功] 已將頻道管理權轉移給 {target.mention}", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)

    async def _cmd_claim(self, message: discord.Message, args: str):
        result = self._get_user_in_temp_channel(message.author)
        if not result:
            await message.reply(
                "[失敗] 你需要在暫時語音頻道中才能使用此指令", mention_author=False
            )
            return
        channel, ch_data = result

        current_owner_id = ch_data["owner_id"]
        if current_owner_id == message.author.id:
            await message.reply("[提示] 你已經是此頻道的擁有者", mention_author=False)
            return

        # 確認原擁有者已不在頻道內
        owner_in_channel = any(m.id == current_owner_id for m in channel.members)
        if owner_in_channel:
            await message.reply(
                "[失敗] 頻道的原擁有者仍在頻道內，無法接管", mention_author=False
            )
            return

        self.service.set_owner(channel.id, message.author.id)
        try:
            await channel.set_permissions(
                message.author,
                manage_channels=True,
                move_members=True,
                connect=True,
                view_channel=True,
            )
            await message.reply(
                "[成功] 你已成功接管此暫時語音頻道的管理權", mention_author=False
            )
        except discord.Forbidden:
            await message.reply("[失敗] 機器人缺少設定頻道權限的能力", mention_author=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoice(bot))

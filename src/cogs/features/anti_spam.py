from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.anti_spam import ACTION_BAN
from src.utils.anti_spam import ACTION_DELETE
from src.utils.anti_spam import ACTION_KICK
from src.utils.anti_spam import ACTION_LOCKDOWN
from src.utils.anti_spam import ACTION_MUTE
from src.utils.anti_spam import ACTION_NAMES
from src.utils.anti_spam import ACTION_WARN
from src.utils.anti_spam import ALL_DETECTIONS
from src.utils.anti_spam import AntiSpamManager
from src.utils.anti_spam import DETECT_NAMES
from src.utils.anti_spam import VALID_ACTIONS
from src.utils.anti_spam import create_anti_spam_log_embed
from src.utils.anti_spam import create_raid_alert_embed
from src.utils.blacklist_manager import blacklist_manager
from src.utils.config_manager import get_guild_log_channel


class AntiSpam(commands.Cog):
    """頂級防炸群系統 Cog — 多層偵測、自動升級、突襲防護"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = AntiSpamManager()

    # ───────────── 輔助方法 ─────────────

    async def _send_log(self, guild_id: int, embed: discord.Embed):
        """發送日誌到設定的頻道"""
        log_channel_id = get_guild_log_channel(guild_id)
        if not log_channel_id:
            return
        try:
            ch = self.bot.get_channel(log_channel_id)
            if not ch:
                ch = await self.bot.fetch_channel(log_channel_id)
            await ch.send(embed=embed)
        except Exception:
            pass

    async def _execute_action(
        self,
        action: str,
        message: discord.Message,
        detail: str,
        detection_type: str,
    ):
        """執行懲罰動作"""
        member = message.author
        guild = message.guild
        s = self.manager.get_settings(guild.id)
        reason = f"防炸群: {DETECT_NAMES.get(detection_type, detection_type)} — {detail}"

        try:
            if action == ACTION_WARN:
                try:
                    warn_embed = discord.Embed(
                        title="[警告] 防炸群系統",
                        description=f"你的行為觸發了 **{DETECT_NAMES.get(detection_type)}** 偵測\n請停止此行為，否則將自動升級懲罰",
                        color=discord.Color.from_rgb(255, 200, 0),
                    )
                    await member.send(embed=warn_embed)
                except discord.Forbidden:
                    pass

            elif action == ACTION_DELETE:
                try:
                    await message.channel.purge(
                        limit=15,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    try:
                        await message.delete()
                    except discord.HTTPException:
                        pass

            elif action == ACTION_MUTE:
                duration = s.get("mute_duration", 3600)
                await member.timeout(
                    timedelta(seconds=duration), reason=reason
                )
                try:
                    await message.channel.purge(
                        limit=10,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    pass

            elif action == ACTION_KICK:
                try:
                    await message.channel.purge(
                        limit=15,
                        check=lambda m: m.author.id == member.id,
                    )
                except discord.HTTPException:
                    pass
                await guild.kick(member, reason=reason)

            elif action == ACTION_BAN:
                delete_days = s.get("ban_delete_days", 1)
                await guild.ban(
                    member,
                    reason=reason,
                    delete_message_days=delete_days,
                )

            elif action == ACTION_LOCKDOWN:
                await self._activate_lockdown(guild)

        except discord.Forbidden:
            pass
        except Exception:
            pass

    async def _activate_lockdown(self, guild: discord.Guild):
        """啟用封鎖模式 — 鎖定所有文字頻道"""
        if self.manager.is_lockdown(guild.id):
            return
        self.manager.set_lockdown(guild.id, True)

        default_role = guild.default_role
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(default_role)
                overwrite.send_messages = False
                await channel.set_permissions(
                    default_role, overwrite=overwrite,
                    reason="防炸群: 突襲封鎖模式啟動",
                )
            except discord.Forbidden:
                continue

    async def _deactivate_lockdown(self, guild: discord.Guild):
        """解除封鎖模式"""
        self.manager.set_lockdown(guild.id, False)

        default_role = guild.default_role
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(default_role)
                overwrite.send_messages = None
                await channel.set_permissions(
                    default_role, overwrite=overwrite,
                    reason="防炸群: 封鎖模式解除",
                )
            except discord.Forbidden:
                continue

    # ───────────── 事件監聽 ─────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽訊息 — 多層偵測"""
        if message.author.bot or message.guild is None:
            return
        if blacklist_manager.is_blacklisted(message.author.id):
            return

        # 權限跳過: 管理員與機器人無法懲罰的成員
        member = message.author
        if isinstance(member, discord.Member):
            if member.guild_permissions.administrator:
                return
            if message.guild.me.top_role <= member.top_role:
                return

        # 邀請連結快速攔截
        if self.manager.is_invite_link(message.content or "", message.guild.id):
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        triggers = self.manager.check_message(
            guild_id=message.guild.id,
            user_id=message.author.id,
            content=message.content or "",
            channel_id=message.channel.id,
            member=message.author,
        )

        if not triggers:
            return

        # 取最嚴重的動作執行
        from src.utils.anti_spam import ACTION_SEVERITY
        triggers.sort(key=lambda t: ACTION_SEVERITY.get(t[1], 0), reverse=True)
        worst_det, worst_action, worst_detail = triggers[0]
        strike_count = self.manager.get_user_strikes(
            message.guild.id, message.author.id
        )

        # 執行動作
        await self._execute_action(
            worst_action, message, worst_detail, worst_det
        )

        # 發送日誌
        embed = create_anti_spam_log_embed(
            user_id=message.author.id,
            user_name=str(message.author),
            guild_id=message.guild.id,
            guild_name=message.guild.name,
            channel_id=message.channel.id,
            detection_type=worst_det,
            action=worst_action,
            detail=worst_detail,
            strike_count=strike_count,
        )

        # 如果有多個觸發，列出所有
        if len(triggers) > 1:
            others = "\n".join(
                f"- {DETECT_NAMES.get(d, d)}: {det}"
                for d, _, det in triggers[1:]
            )
            embed.add_field(name="其他觸發", value=others, inline=False)

        await self._send_log(message.guild.id, embed)

        # 重設紀錄
        self.manager.reset_user(message.guild.id, message.author.id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """監聽成員加入 — 突襲偵測"""
        if member.bot:
            return

        result = self.manager.check_member_join(member.guild.id)
        if not result:
            return

        det_type, action, detail = result
        s = self.manager.get_settings(member.guild.id)

        embed = create_raid_alert_embed(
            guild_name=member.guild.name,
            guild_id=member.guild.id,
            join_count=s["raid_joins"],
            window=s["raid_window"],
            action=action,
        )

        await self._send_log(member.guild.id, embed)

        if action == ACTION_LOCKDOWN:
            await self._activate_lockdown(member.guild)

    # ───────────── 指令群組 ─────────────

    anti_spam_group = app_commands.Group(
        name="anti_spam",
        description="防炸群系統設定",
        default_permissions=discord.Permissions(administrator=True),
    )

    @anti_spam_group.command(name="setup", description="快速設定防炸群 (啟用/禁用)")
    @app_commands.describe(enabled="是否啟用防炸群系統")
    async def setup_cmd(self, interaction: discord.Interaction, enabled: bool = True):
        """快速啟用/禁用"""
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {"enabled": enabled})
        status = "已啟用" if enabled else "已禁用"
        embed = discord.Embed(
            title=f"[設定] 防炸群 {status}",
            color=discord.Color.from_rgb(46, 204, 113) if enabled else discord.Color.from_rgb(231, 76, 60),
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="flood", description="設定訊息洪水偵測")
    @app_commands.describe(
        messages="時間視窗內最大訊息數",
        window="時間視窗 (秒)",
        action="觸發動作 (warn/delete/mute/kick/ban)",
    )
    async def flood_cmd(
        self,
        interaction: discord.Interaction,
        messages: int = 10,
        window: int = 10,
        action: str = "mute",
    ):
        """設定洪水偵測"""
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "flood_messages": max(1, messages),
            "flood_window": max(1, window),
            "flood_action": action,
        })
        embed = discord.Embed(
            title="[設定] 洪水偵測已更新",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="訊息上限", value=f"{messages} 條", inline=True)
        embed.add_field(name="時間視窗", value=f"{window} 秒", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="duplicate", description="設定重複內容偵測")
    @app_commands.describe(
        enabled="是否啟用",
        count="觸發次數",
        window="時間視窗 (秒)",
        action="觸發動作",
    )
    async def duplicate_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        count: int = 4,
        window: int = 30,
        action: str = "delete",
    ):
        """設定重複偵測"""
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "duplicate_enabled": enabled,
            "duplicate_count": max(2, count),
            "duplicate_window": max(5, window),
            "duplicate_action": action,
        })
        status = "啟用" if enabled else "禁用"
        embed = discord.Embed(
            title=f"[設定] 重複偵測 — {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="觸發次數", value=f"{count} 次", inline=True)
        embed.add_field(name="時間視窗", value=f"{window} 秒", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="mention", description="設定提及轟炸偵測")
    @app_commands.describe(
        enabled="是否啟用",
        limit="單條訊息最大提及數",
        action="觸發動作",
    )
    async def mention_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 8,
        action: str = "mute",
    ):
        """設定提及偵測"""
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "mention_enabled": enabled,
            "mention_limit": max(1, limit),
            "mention_action": action,
        })
        status = "啟用" if enabled else "禁用"
        embed = discord.Embed(
            title=f"[設定] 提及偵測 — {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="提及上限", value=f"{limit} 個", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="link", description="設定連結/邀請偵測")
    @app_commands.describe(
        enabled="是否啟用",
        limit="時間視窗內最大連結數",
        window="時間視窗 (秒)",
        action="觸發動作",
        invite_auto_delete="自動刪除邀請連結",
    )
    async def link_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        limit: int = 5,
        window: int = 15,
        action: str = "delete",
        invite_auto_delete: bool = True,
    ):
        """設定連結偵測"""
        if action not in VALID_ACTIONS:
            await interaction.response.send_message(
                f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "link_enabled": enabled,
            "link_limit": max(1, limit),
            "link_window": max(5, window),
            "link_action": action,
            "invite_auto_delete": invite_auto_delete,
        })
        status = "啟用" if enabled else "禁用"
        embed = discord.Embed(
            title=f"[設定] 連結偵測 — {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="連結上限", value=f"{limit} 個", inline=True)
        embed.add_field(name="時間視窗", value=f"{window} 秒", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        embed.add_field(name="自動刪除邀請", value="是" if invite_auto_delete else "否", inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="raid", description="設定突襲偵測")
    @app_commands.describe(
        enabled="是否啟用",
        joins="觸發人數",
        window="時間視窗 (秒)",
        action="觸發動作 (建議 lockdown)",
    )
    async def raid_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        joins: int = 10,
        window: int = 30,
        action: str = "lockdown",
    ):
        """設定突襲偵測"""
        if action not in VALID_ACTIONS and action != "lockdown":
            await interaction.response.send_message(
                f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "raid_enabled": enabled,
            "raid_joins": max(3, joins),
            "raid_window": max(10, window),
            "raid_action": action,
        })
        status = "啟用" if enabled else "禁用"
        embed = discord.Embed(
            title=f"[設定] 突襲偵測 — {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="觸發人數", value=f"{joins} 人", inline=True)
        embed.add_field(name="時間視窗", value=f"{window} 秒", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="escalation", description="設定自動升級懲罰")
    @app_commands.describe(
        enabled="是否啟用自動升級",
        strikes="升級門檻 (違規次數)",
        window="違規記錄視窗 (秒)",
    )
    async def escalation_cmd(
        self,
        interaction: discord.Interaction,
        enabled: bool = True,
        strikes: int = 3,
        window: int = 600,
    ):
        """設定自動升級"""
        await interaction.response.defer()
        self.manager.update_settings(interaction.guild_id, {
            "auto_escalate": enabled,
            "escalate_strikes": max(2, strikes),
            "escalate_window": max(60, window),
        })
        status = "啟用" if enabled else "禁用"
        embed = discord.Embed(
            title=f"[設定] 自動升級 — {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="升級門檻", value=f"{strikes} 次違規", inline=True)
        embed.add_field(name="記錄視窗", value=f"{window} 秒", inline=True)
        embed.add_field(
            name="機制說明",
            value="用戶在視窗內累積違規達門檻後，懲罰自動升一級\n(警告→刪除→禁言→踢出→封禁)",
            inline=False,
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="whitelist", description="管理白名單")
    @app_commands.describe(
        action="add 或 remove",
        role="要加入/移除的角色",
        channel="要加入/移除的頻道",
    )
    async def whitelist_cmd(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role = None,
        channel: discord.TextChannel = None,
    ):
        """管理白名單"""
        if action not in ("add", "remove"):
            await interaction.response.send_message(
                "[失敗] action 必須為 add 或 remove", ephemeral=True
            )
            return
        if not role and not channel:
            await interaction.response.send_message(
                "[失敗] 請指定角色或頻道", ephemeral=True
            )
            return

        await interaction.response.defer()
        s = self.manager.get_settings(interaction.guild_id)
        changes = []

        if role:
            if action == "add" and role.id not in s["whitelisted_roles"]:
                s["whitelisted_roles"].append(role.id)
                changes.append(f"新增角色白名單: {role.mention}")
            elif action == "remove" and role.id in s["whitelisted_roles"]:
                s["whitelisted_roles"].remove(role.id)
                changes.append(f"移除角色白名單: {role.mention}")

        if channel:
            if action == "add" and channel.id not in s["whitelisted_channels"]:
                s["whitelisted_channels"].append(channel.id)
                changes.append(f"新增頻道白名單: {channel.mention}")
            elif action == "remove" and channel.id in s["whitelisted_channels"]:
                s["whitelisted_channels"].remove(channel.id)
                changes.append(f"移除頻道白名單: {channel.mention}")

        if not changes:
            await interaction.followup.send("[提示] 無變更", ephemeral=True)
            return

        embed = discord.Embed(
            title="[設定] 白名單已更新",
            description="\n".join(changes),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="lockdown_off", description="解除封鎖模式")
    async def lockdown_off_cmd(self, interaction: discord.Interaction):
        """手動解除封鎖模式"""
        if not self.manager.is_lockdown(interaction.guild_id):
            await interaction.response.send_message(
                "[提示] 目前未處於封鎖模式", ephemeral=True
            )
            return

        await interaction.response.defer()
        await self._deactivate_lockdown(interaction.guild)

        embed = discord.Embed(
            title="[成功] 封鎖模式已解除",
            description="所有頻道的發言權限已恢復",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

        await self._send_log(interaction.guild_id, discord.Embed(
            title="[防炸群] 封鎖模式已手動解除",
            description=f"由 {interaction.user.mention} 解除",
            color=discord.Color.from_rgb(46, 204, 113),
        ))

    @anti_spam_group.command(name="status", description="查看防炸群系統完整狀態")
    async def status_cmd(self, interaction: discord.Interaction):
        """顯示完整防炸群設定狀態"""
        await interaction.response.defer()
        s = self.manager.get_settings(interaction.guild_id)

        main_status = "已啟用" if s["enabled"] else "已禁用"
        lockdown = "啟動中" if self.manager.is_lockdown(interaction.guild_id) else "正常"

        embed = discord.Embed(
            title="[狀態] 防炸群系統",
            description=f"系統狀態: **{main_status}** | 封鎖模式: **{lockdown}**",
            color=discord.Color.from_rgb(52, 152, 219),
        )

        # 洪水
        embed.add_field(
            name="訊息洪水",
            value=f"{s['flood_messages']} 條 / {s['flood_window']}s → {ACTION_NAMES.get(s['flood_action'])}",
            inline=True,
        )

        # 重複
        dup_st = "開" if s["duplicate_enabled"] else "關"
        embed.add_field(
            name=f"重複內容 [{dup_st}]",
            value=f"{s['duplicate_count']} 次 / {s['duplicate_window']}s → {ACTION_NAMES.get(s['duplicate_action'])}",
            inline=True,
        )

        # 提及
        men_st = "開" if s["mention_enabled"] else "關"
        embed.add_field(
            name=f"提及轟炸 [{men_st}]",
            value=f"{s['mention_limit']} 個/條 → {ACTION_NAMES.get(s['mention_action'])}",
            inline=True,
        )

        # 連結
        link_st = "開" if s["link_enabled"] else "關"
        inv = "是" if s["invite_auto_delete"] else "否"
        embed.add_field(
            name=f"連結轟炸 [{link_st}]",
            value=f"{s['link_limit']} 個 / {s['link_window']}s → {ACTION_NAMES.get(s['link_action'])}\n自動刪除邀請: {inv}",
            inline=True,
        )

        # 表情
        emo_st = "開" if s["emoji_enabled"] else "關"
        embed.add_field(
            name=f"表情轟炸 [{emo_st}]",
            value=f"{s['emoji_limit']} 個/條 → {ACTION_NAMES.get(s['emoji_action'])}",
            inline=True,
        )

        # 換行
        nl_st = "開" if s["newline_enabled"] else "關"
        embed.add_field(
            name=f"換行轟炸 [{nl_st}]",
            value=f"{s['newline_limit']} 行/條 → {ACTION_NAMES.get(s['newline_action'])}",
            inline=True,
        )

        # 突襲
        raid_st = "開" if s["raid_enabled"] else "關"
        embed.add_field(
            name=f"突襲偵測 [{raid_st}]",
            value=f"{s['raid_joins']} 人 / {s['raid_window']}s → {ACTION_NAMES.get(s['raid_action'])}",
            inline=True,
        )

        # 自動升級
        esc_st = "開" if s["auto_escalate"] else "關"
        embed.add_field(
            name=f"自動升級 [{esc_st}]",
            value=f"{s['escalate_strikes']} 次 / {s['escalate_window']}s",
            inline=True,
        )

        # 白名單
        roles = [f"<@&{r}>" for r in s["whitelisted_roles"]] or ["無"]
        channels = [f"<#{c}>" for c in s["whitelisted_channels"]] or ["無"]
        embed.add_field(
            name="白名單",
            value=f"角色: {', '.join(roles)}\n頻道: {', '.join(channels)}",
            inline=False,
        )

        embed.set_footer(text=f"禁言時長: {s['mute_duration']}s | 封禁刪除天數: {s['ban_delete_days']}d")

        await interaction.followup.send(embed=embed)

    @anti_spam_group.command(name="mute_duration", description="設定禁言時長")
    @app_commands.describe(seconds="禁言秒數 (預設 3600 = 1 小時)")
    async def mute_duration_cmd(
        self, interaction: discord.Interaction, seconds: int = 3600
    ):
        """設定禁言時長"""
        await interaction.response.defer()
        sec = max(60, min(seconds, 2419200))  # 60s ~ 28d
        self.manager.update_settings(interaction.guild_id, {"mute_duration": sec})
        embed = discord.Embed(
            title="[設定] 禁言時長已更新",
            description=f"禁言時長: **{sec}** 秒 ({sec // 3600}h {(sec % 3600) // 60}m)",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)

    # ───────────── 向下相容舊指令 ─────────────

    @commands.hybrid_command(name="anti_spam_set", description="快速設定防炸群功能 (舊版相容)")
    @commands.has_permissions(administrator=True)
    async def anti_spam_set_legacy(
        self,
        ctx,
        enabled: bool = True,
        messages_per_window: int = 10,
        window_seconds: int = 10,
        action: str = "mute",
    ):
        """向下相容的舊版設定指令"""
        if action not in VALID_ACTIONS:
            await ctx.send(f"[失敗] 無效動作，可選: {', '.join(VALID_ACTIONS)}", ephemeral=True)
            return

        self.manager.update_settings(ctx.guild.id, {
            "enabled": enabled,
            "flood_messages": max(1, messages_per_window),
            "flood_window": max(1, window_seconds),
            "flood_action": action,
        })

        status = "已啟用" if enabled else "已禁用"
        embed = discord.Embed(
            title=f"[設定] 防炸群 {status}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(name="時間視窗", value=f"{window_seconds} 秒", inline=True)
        embed.add_field(name="訊息限制", value=f"{messages_per_window} 條", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(action, action), inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="anti_spam_status", description="查看防炸群狀態 (舊版相容)")
    @commands.has_permissions(administrator=True)
    async def anti_spam_status_legacy(self, ctx):
        """向下相容的舊版狀態指令"""
        s = self.manager.get_settings(ctx.guild.id)
        status = "已啟用" if s["enabled"] else "已禁用"

        embed = discord.Embed(
            title="[查詢] 防炸群狀態",
            description=f"使用 `/anti_spam status` 查看完整設定",
            color=discord.Color.from_rgb(52, 152, 219),
        )
        embed.add_field(name="狀態", value=status, inline=True)
        embed.add_field(name="洪水偵測", value=f"{s['flood_messages']} 條 / {s['flood_window']}s", inline=True)
        embed.add_field(name="動作", value=ACTION_NAMES.get(s["flood_action"], s["flood_action"]), inline=True)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(AntiSpam(bot))

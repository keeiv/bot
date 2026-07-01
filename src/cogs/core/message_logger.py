"""訊息編輯/刪除日誌 Cog"""

from datetime import timedelta
from datetime import timezone

import discord
from discord.ext import commands
from discord.ext import tasks

from src.services.message_log_service import MessageLogService
from src.utils.config_manager import ensure_data_dir

TZ_OFFSET = timezone(timedelta(hours=8))


class MessageLogger(commands.Cog):
    """訊息編輯和刪除日誌 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = MessageLogService()
        ensure_data_dir()
        self._cleanup_task.start()

    def cog_unload(self):
        self._cleanup_task.cancel()

    @tasks.loop(hours=24)
    async def _cleanup_task(self):
        """定期清理超過保留天數的舊訊息日誌"""
        await self.bot.wait_until_ready()
        try:
            removed = self.service.cleanup_old_logs()
            if removed:
                print(f"[清理] 已移除 {removed} 筆舊訊息日誌")
        except Exception as e:
            print(f"[清理] 日誌清理失敗: {e}")

    # ─────────────── 事件監聽 ───────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽所有訊息，記錄內容以備後用"""
        if message.author.bot or message.guild is None:
            return
        if not self.service.get_record(message.guild.id, message.id):
            self.service.add_record(
                message.guild.id,
                message.id,
                message.content,
                message.author.id,
                message.channel.id,
                message.attachments or None,
            )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """監聽訊息編輯"""
        if before.author.bot or before.content == after.content:
            return
        try:
            guild_id = before.guild.id
            channel_id = before.channel.id
            message_id = before.id
            user_id = before.author.id
            user_name = str(before.author)

            record = self.service.get_record(guild_id, message_id)
            if not record:
                self.service.add_record(
                    guild_id,
                    message_id,
                    before.content,
                    user_id,
                    channel_id,
                    before.attachments or None,
                )
                before_content = before.content
                before_attachment_urls: list[str] = []
                edit_count = 1
            else:
                before_content = record.get("original_content", before.content)
                before_attachment_urls = record.get("attachments", [])
                edit_count = 1 + len(record.get("edit_history", []))

            self.service.record_edit(guild_id, message_id, after.content)

            log_channel_id = self.service.get_log_channel_id(guild_id)
            if not log_channel_id:
                return

            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel is None:
                log_channel = await self.bot.fetch_channel(log_channel_id)
            if not isinstance(log_channel, discord.TextChannel):
                return

            after_attachment_urls = [a.url for a in after.attachments]
            embed = self.service.build_edit_embed(
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
                user_id=user_id,
                user_name=user_name,
                guild_name=before.guild.name,
                before_content=before_content,
                after_content=after.content,
                edit_count=edit_count,
                before_attachments=before_attachment_urls,
                after_attachments=after_attachment_urls,
            )
            await log_channel.send(embed=embed)

            try:
                achievements_cog = self.bot.get_cog("Achievements")
                if achievements_cog:
                    achievements_cog.trigger_edit_achievement(user_id, guild_id)
            except Exception as e:
                print(f"[成就] 編輯成就觸發失敗: {e}")

        except Exception as e:
            print(f"[失敗] 編輯監聽出錯: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """監聽訊息刪除"""
        if message.author.bot:
            return
        try:
            guild_id = message.guild.id
            channel_id = message.channel.id
            message_id = message.id
            user_id = message.author.id
            user_name = str(message.author)

            record = self.service.get_record(guild_id, message_id)
            if record:
                original_content = record.get("original_content", message.content)
                attachment_urls: list[str] = record.get("attachments", [])
            else:
                original_content = message.content
                attachment_urls = [a.url for a in message.attachments]
                self.service.add_record(
                    guild_id,
                    message_id,
                    original_content,
                    user_id,
                    channel_id,
                    message.attachments or None,
                )

            self.service.mark_deleted(guild_id, message_id)

            log_channel_id = self.service.get_log_channel_id(guild_id)
            if not log_channel_id:
                return

            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel is None:
                log_channel = await self.bot.fetch_channel(log_channel_id)
            if not isinstance(log_channel, discord.TextChannel):
                return

            embed = self.service.build_delete_embed(
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
                user_id=user_id,
                user_name=user_name,
                guild_name=message.guild.name,
                content=original_content,
                attachments=attachment_urls,
            )
            await log_channel.send(embed=embed)

            try:
                achievements_cog = self.bot.get_cog("Achievements")
                if achievements_cog:
                    achievements_cog.trigger_delete_achievement(user_id, guild_id)
            except Exception as e:
                print(f"[成就] 刪除成就觸發失敗: {e}")

        except Exception as e:
            print(f"[失敗] 刪除監聽出錯: {e}")

    # ─────────────── 指令 ───────────────

    @discord.app_commands.command(
        name="編刪紀錄設定", description="設置訊息編輯/刪除的日誌頻道"
    )
    @discord.app_commands.describe(channel="要發送日誌的頻道")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """設置日誌頻道"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "[失敗] 你需要管理員權限才能使用此指令", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.service.set_log_channel_id(interaction.guild_id, channel.id)
        embed = discord.Embed(
            title="[成功] 設置成功",
            description=f"訊息編輯/刪除的日誌將發送到 {channel.mention}",
            color=discord.Color.from_rgb(46, 204, 113),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(MessageLogger(bot))

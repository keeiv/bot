from datetime import timedelta

import discord
from discord.ext import commands

from src.utils.anti_spam import AntiSpamManager
from src.utils.anti_spam import create_anti_spam_log_embed
from src.utils.blacklist_manager import blacklist_manager
from src.utils.config_manager import get_guild_log_channel


class AntiSpam(commands.Cog):
    """防炸群功能 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.anti_spam_manager = AntiSpamManager()

    def is_blacklisted_check(self):
        """黑名單檢查裝飾器"""

        async def predicate(ctx):
            if blacklist_manager.is_blacklisted(ctx.author.id):
                embed = discord.Embed(
                    title="[拒絕] 你已被禁止",
                    description="你已被禁止使用機器人指令，請聯繫管理員",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return False
            return True

        return commands.check(predicate)

    @commands.hybrid_command(name="anti_spam_set", description="設置防炸群功能")
    @commands.has_permissions(administrator=True)
    async def anti_spam_set(
        self,
        ctx,
        enabled: bool = True,
        messages_per_window: int = 10,
        window_seconds: int = 10,
        action: str = "mute",
    ):
        """設置防炸群功能"""
        try:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("[失敗] 你需要管理員權限", ephemeral=True)
                return

            if action not in ["mute", "delete"]:
                await ctx.send("[失敗] 可選的動作: mute 或 delete", ephemeral=True)
                return

            if messages_per_window < 1 or window_seconds < 1:
                await ctx.send("[失敗] 數量必須大於 0", ephemeral=True)
                return

            settings = {
                "enabled": enabled,
                "messages_per_window": messages_per_window,
                "window_seconds": window_seconds,
                "action": action,
            }

            self.anti_spam_manager.update_settings(ctx.guild.id, settings)

            status = "[已啟用]" if enabled else "[已禁用]"
            embed = discord.Embed(
                title="[設置] 防炸群設置完成",
                description=f"{status} 防炸群功能",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            embed.add_field(
                name="[時間視窗]", value=f"{window_seconds} 秒", inline=True
            )
            embed.add_field(
                name="[訊息限制]", value=f"{messages_per_window} 條", inline=True
            )
            embed.add_field(name="[動作]", value=action, inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            print(f"[防炸群設置] 錯誤: {type(e).__name__}: {e}")
            if hasattr(ctx, "interaction") and ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(
                        f"[失敗] 錯誤: {str(e)}", ephemeral=True
                    )
            else:
                await ctx.send(f"[失敗] 錯誤: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="anti_spam_status", description="查看防炸群狀態")
    @commands.has_permissions(administrator=True)
    async def anti_spam_status(self, ctx):
        """查看防炸群狀態"""
        try:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("[失敗] 你需要管理員權限", ephemeral=True)
                return

            settings = self.anti_spam_manager.get_settings(ctx.guild.id)

            status = "[已啟用]" if settings["enabled"] else "[已禁用]"

            embed = discord.Embed(
                title="[查詢] 防炸群設置狀態", color=discord.Color.blue()
            )
            embed.add_field(name="[是否啟用]", value=status, inline=False)
            embed.add_field(
                name="[時間視窗]", value=f"{settings['window_seconds']} 秒", inline=True
            )
            embed.add_field(
                name="[訊息限制]",
                value=f"{settings['messages_per_window']} 條",
                inline=True,
            )
            embed.add_field(name="[動作]", value=settings["action"], inline=True)

            await ctx.send(embed=embed)
        except Exception as e:
            print(f"[查詢防炸群設置] 錯誤: {type(e).__name__}: {e}")
            if hasattr(ctx, "interaction") and ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(
                        f"[失敗] 錯誤: {str(e)}", ephemeral=True
                    )
            else:
                await ctx.send(f"[失敗] 錯誤: {str(e)}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """監聽訊息進行防炸群檢查"""
        # 忽略bot訊息
        if message.author.bot:
            return

        # 忽略私人訊息
        if message.guild is None:
            return

        # 檢查黑名單
        if blacklist_manager.is_blacklisted(message.author.id):
            return

        # 檢查是否為垃圾訊息
        is_spam, message_count = self.anti_spam_manager.check_spam(
            message.guild.id, message.author.id
        )

        if is_spam:
            settings = self.anti_spam_manager.get_settings(message.guild.id)

            # 發送日誌
            log_channel_id = get_guild_log_channel(message.guild.id)
            if log_channel_id:
                try:
                    log_channel = await self.bot.fetch_channel(log_channel_id)
                    embed = create_anti_spam_log_embed(
                        user_id=message.author.id,
                        user_name=str(message.author),
                        guild_id=message.guild.id,
                        guild_name=message.guild.name,
                        channel_id=message.channel.id,
                        message_count=message_count,
                        threshold=settings["messages_per_window"],
                        action=settings["action"],
                    )
                    await log_channel.send(embed=embed)
                except Exception as e:
                    print(f"無法發送防炸群日誌: {e}")

            # 執行設定的動作
            try:
                if settings["action"] == "mute":
                    # 禁言 1 小時
                    await message.author.timeout(
                        timedelta(hours=1), reason="防炸群: 訊息流量被警告"
                    )
                elif settings["action"] == "delete":
                    # 刪除最近 10 條訊息
                    try:
                        await message.channel.purge(
                            limit=10, check=lambda m: m.author == message.author
                        )
                    except discord.HTTPException:
                        # 如果不能刪除所有，就算了
                        pass
            except Exception as e:
                print(f"無法執行防炸群動作: {e}")

            # 重置使用者訊息記錄
            self.anti_spam_manager.reset_user(message.guild.id, message.author.id)
            return


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(AntiSpam(bot))

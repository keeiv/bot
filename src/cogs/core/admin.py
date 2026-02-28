from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.blacklist_manager import blacklist_manager


class Admin(commands.Cog):
    """管理員命令 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_blacklisted_check(self):
        """黑名單檢查裝飾器"""

        async def predicate(ctx):
            if blacklist_manager.is_blacklisted(ctx.author.id):
                embed = discord.Embed(
                    title="[Denied] Access Denied",
                    description="You have been banned from using bot commands. Please contact an administrator.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return False
            return True

        return commands.check(predicate)

    @commands.hybrid_command(name="clear", description="清除指定數量的訊息")
    @app_commands.describe(amount="要刪除的訊息數量 (1-100，預設 10)")
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clear(self, ctx, amount: int = 10):
        """清除訊息"""
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(
                "[Failed] You need manage messages permission", ephemeral=True
            )
            return

        if amount < 1 or amount > 100:
            await ctx.send("[Failed] Amount must be between 1-100", ephemeral=True)
            return

        await ctx.defer()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.followup.send(
            f"[Success] Cleared {len(deleted)} messages", ephemeral=True
        )

    @commands.hybrid_command(name="kick", description="踢出成員")
    @app_commands.describe(user="要踢出的成員", reason="踢出原因")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """踢出成員"""
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("[Failed] You need kick members permission", ephemeral=True)
            return

        if user == ctx.author:
            await ctx.send("[Failed] You cannot kick yourself", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[Failed] Your permissions are insufficient to kick this member",
                ephemeral=True,
            )
            return

        try:
            await user.kick(reason=reason)
            embed = discord.Embed(
                title="[Success] Member Kicked",
                description=f"Member: {user.mention}\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to kick member: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="ban", description="封禁成員")
    @app_commands.describe(user="要封禁的成員", reason="封禁原因")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """封禁成員"""
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("[Failed] You need ban members permission", ephemeral=True)
            return

        if user == ctx.author:
            await ctx.send("[Failed] You cannot ban yourself", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[Failed] Your permissions are insufficient to ban this member",
                ephemeral=True,
            )
            return

        try:
            await user.ban(reason=reason)
            embed = discord.Embed(
                title="[Success] Member Banned",
                description=f"Member: {user.mention}\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to ban member: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="mute", description="禁言成員")
    @app_commands.describe(user="要禁言的成員", duration="禁言時長 (分鐘，預設 60)", reason="禁言原因")
    @commands.has_permissions(moderate_members=True)
    async def mute(
        self,
        ctx,
        user: discord.Member,
        duration: int = 60,
        reason: str = "沒有提供原因",
    ):
        """禁言成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[失敗] 你需要有管理成員的權限", ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send("[失敗] 你不能禁言自己", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[失敗] 你的權限不足以禁言此成員", ephemeral=True
            )
            return

        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title="[成功] 成員已被禁言",
                description=f"成員: {user.mention}\n持續時間: {duration} 分鐘\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法禁言成員: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="警告成員")
    @app_commands.describe(user="要警告的成員", reason="警告原因")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """警告成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[失敗] 你需要有管理成員的權限", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="[警告] 警告成員",
            description=f"{user.mention} 已被警告，原因如下:\n{reason}",
            color=discord.Color.from_rgb(241, 196, 15),
        )

        try:
            await user.send(embed=embed)
            await ctx.send(f"[成功] 已警告 {user.mention}", ephemeral=True)
        except Exception as e:
            await ctx.send(
                f"[警告] 成員已被警告，但無法發送私訊: {str(e)}",
                ephemeral=True,
            )

    @commands.hybrid_command(name="help", description="顯示機器人幫助資訊")
    async def help_command(self, ctx):
        """幫助指令"""
        # --- 第一頁：機器人介紹與指令清單 ---
        embed_main = discord.Embed(
            title="[幫助] 機器人資訊",
            description=(
                "一個功能完整的 Discord 機器人，包含訊息管理、遊戲、osu! 整合與 GitHub 監控。\n"
                "由社群共同維護，歡迎任何人貢獻。"
            ),
            color=discord.Color.blue(),
        )

        embed_main.add_field(
            name="[管理指令]",
            value=(
                "`/編刪紀錄設定` - 設置訊息日誌頻道\n"
                "`/clear` - 清除指定數量的訊息\n"
                "`/kick` - 踢出成員\n"
                "`/ban` - 封禁成員\n"
                "`/mute` - 禁言成員\n"
                "`/warn` - 警告成員"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[審計日誌]",
            value=(
                "自動記錄以下伺服器事件到日誌頻道:\n"
                "成員加入/離開、語音頻道異動、角色變更、暱稱變更、頻道建立/刪除/修改"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[機器人外觀 (此伺服器)]",
            value=(
                "`/bot_appearance name` - 更改機器人暱稱\n"
                "`/bot_appearance avatar` - 更改機器人頭像 (需審核)\n"
                "`/bot_appearance banner` - 更改機器人橫幅 (需審核)"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[舉報系統]",
            value=(
                "右鍵訊息 > 應用程式 > `舉報訊息` - 舉報可疑訊息\n"
                "`/report_channel set` - 設定舉報接收頻道\n"
                "`/report_channel status` - 查看舉報頻道設定"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[翻譯]",
            value=(
                "右鍵訊息 > 應用程式 > `翻譯訊息` - 翻譯任意訊息\n"
                "支援 14 種語言，自動偵測來源語言"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[防炸群系統]",
            value=(
                "`/anti_spam setup` - 啟用/禁用防炸群\n"
                "`/anti_spam flood` - 訊息洪水偵測設定\n"
                "`/anti_spam duplicate` - 重複內容偵測\n"
                "`/anti_spam mention` - 提及轟炸偵測\n"
                "`/anti_spam link` - 連結/邀請偵測\n"
                "`/anti_spam raid` - 突襲偵測\n"
                "`/anti_spam escalation` - 自動升級懲罰\n"
                "`/anti_spam whitelist` - 白名單管理\n"
                "`/anti_spam lockdown_off` - 解除封鎖\n"
                "`/anti_spam status` - 查看完整狀態"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[抽獎]",
            value=(
                "`/giveaway start` - 建立抽獎活動\n"
                "`/giveaway end` - 提前結束抽獎\n"
                "`/giveaway reroll` - 重新抽取得獎者\n"
                "`/giveaway list` - 查看進行中抽獎"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[遊戲]",
            value=(
                "`/deep_sea_oxygen` - 深海氧氣瓶遊戲\n"
                "`/russian_roulette` - 俄羅斯輪盤"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[osu! 整合]",
            value=(
                "`/user_info_osu` - 查詢 osu! 玩家資料\n"
                "`/osu bind` - 綁定 osu! 帳號\n"
                "`/osu best` - 查詢 BP\n"
                "`/osu recent` - 查詢最近遊玩"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[GitHub 監控]",
            value=(
                "`/repo_watch set` - 設定倉庫監控\n"
                "`/repo_track add` - 追蹤 keeiv/bot 更新\n"
                "`/repo_watch status` - 查看監控狀態"
            ),
            inline=False,
        )

        embed_main.add_field(
            name="[其他]",
            value=(
                "`/achievements` - 查看成就\n"
                "`/user_info` - 查看用戶資訊\n"
                "`/server_info` - 查看伺服器資訊"
            ),
            inline=False,
        )

        # --- 第二頁：貢獻指南 ---
        embed_contrib = discord.Embed(
            title="[貢獻] 如何參與開發",
            description=(
                "這個專案歡迎任何人貢獻。如果你想要某個功能，歡迎直接提交 PR！"
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )

        embed_contrib.add_field(
            name="[小型/中型更新]",
            value=(
                "不需要事先討論，直接提交 PR 即可。\n"
                "例如：新增獨立指令、修復 Bug、更新文件、程式碼重構。"
            ),
            inline=False,
        )

        embed_contrib.add_field(
            name="[大型更新]",
            value=(
                "必須先開 Issue 討論後再開發。\n"
                "例如：新增依賴、架構變動、資料結構變更、破壞性變更。"
            ),
            inline=False,
        )

        embed_contrib.add_field(
            name="[PR 提交流程]",
            value=(
                "1. Fork 倉庫並建立分支\n"
                "2. 完成開發並確保通過 CI 檢查\n"
                "3. 使用 Conventional Commits 格式\n"
                "   `feat:` 新功能 / `fix:` 修復 / `docs:` 文件\n"
                "4. 提交 PR 並清楚描述變更內容"
            ),
            inline=False,
        )

        embed_contrib.add_field(
            name="[程式碼規範]",
            value=(
                "- 遵循 PEP 8 規範\n"
                "- 使用 Black + isort 格式化\n"
                "- 通過 flake8 檢查\n"
                "- 鼓勵為新功能編寫測試"
            ),
            inline=False,
        )

        embed_contrib.set_footer(
            text="倉庫: github.com/keeiv/bot"
        )

        await ctx.send(embeds=[embed_main, embed_contrib])


async def setup(bot: commands.Bot):
    """Load Cog"""
    await bot.add_cog(Admin(bot))

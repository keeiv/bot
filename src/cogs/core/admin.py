from datetime import timedelta

import discord
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

    @commands.hybrid_command(name="kick", description="踢出成员")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """踢出成员"""
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

    @commands.hybrid_command(name="ban", description="封禁成员")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """封禁成员"""
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

    @commands.hybrid_command(name="mute", description="Mute member")
    @commands.has_permissions(moderate_members=True)
    async def mute(
        self,
        ctx,
        user: discord.Member,
        duration: int = 60,
        reason: str = "No reason provided",
    ):
        """Mute member"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[Failed] You need moderate members permission", ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send("[Failed] You cannot mute yourself", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[Failed] Your permissions are insufficient to mute this member",
                ephemeral=True,
            )
            return

        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title="[Success] Member Muted",
                description=f"Member: {user.mention}\nDuration: {duration} minutes\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to mute member: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="Warn member")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        """Warn member"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[Failed] You need moderate members permission", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="[Warning] Warning",
            description=f"{user.mention} has been warned for the following reason:\n{reason}",
            color=discord.Color.from_rgb(241, 196, 15),
        )

        try:
            await user.send(embed=embed)
            await ctx.send(f"[Success] Warned {user.mention}", ephemeral=True)
        except Exception as e:
            await ctx.send(
                f"[Warning] Member warned but unable to send DM: {str(e)}",
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
            name="[防刷屏]",
            value=(
                "`/anti_spam_set` - 設置防刷屏功能\n"
                "`/anti_spam_status` - 查看防刷屏狀態"
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

        # --- 第二頁：開發者資訊 ---
        embed_dev = discord.Embed(
            title="[關於] 開發者資訊",
            description="本機器人由 **凱伊 (keeiv)** 開發與維護。",
            color=discord.Color.from_rgb(88, 101, 242),
        )

        embed_dev.add_field(
            name="[自我介紹]",
            value=(
                "- Discord Bot 開發者 / 小型遊戲開發者\n"
                "- 追求低延遲設計 / 專業開發\n"
                "- 喜歡把簡單的事情變複雜\n"
                "- 具有代碼強迫症"
            ),
            inline=False,
        )

        embed_dev.add_field(
            name="[關於我]",
            value=(
                "- 熟悉多種語言開發\n"
                "- 注重團隊紀律 (Team Discipline)\n"
                "- 學習程式語言已有 8 年以上\n"
                "- UI/UX 具有深度理解\n"
                "- 希望做出與 osu! 一樣厲害的低延遲音樂遊戲"
            ),
            inline=False,
        )

        embed_dev.add_field(
            name="[技術棧]",
            value=(
                "**主要語言**: C++, C#, Java, Python\n"
                "**Web / Script**: JS, Lua, PHP, HTML5\n"
                "**框架與工具**: .NET, Discord, Linux, Git"
            ),
            inline=False,
        )

        embed_dev.add_field(
            name="[專案]",
            value=(
                "**BOT** - 開放大家踴躍提交 PR 的 Discord Bot\n"
                "**RhythmClicker** - 音樂節奏遊戲 (開發中)"
            ),
            inline=False,
        )

        embed_dev.set_footer(text="GitHub Developer Program Member | PRO")

        # --- 第三頁：貢獻指南 ---
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

        await ctx.send(embeds=[embed_main, embed_dev, embed_contrib])


async def setup(bot: commands.Bot):
    """Load Cog"""
    await bot.add_cog(Admin(bot))

import discord
from discord.ext import commands
from datetime import timedelta
from utils.blacklist_manager import blacklist_manager

class Admin(commands.Cog):
    """管理員指令 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def is_blacklisted_check(self):
        """黑名單檢查裝飾器"""
        async def predicate(ctx):
            if blacklist_manager.is_blacklisted(ctx.author.id):
                embed = discord.Embed(
                    title="[拒絕] 你已被禁止",
                    description="你已被禁止使用機器人指令，請聯繫管理員",
                    color=discord.Color.red()
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
            await ctx.send("[失敗] 你需要管理訊息權限", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await ctx.send("[失敗] 數量必須在 1-100 之間", ephemeral=True)
            return
        
        await ctx.defer()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.followup.send(f"[成功] 已清除 {len(deleted)} 條訊息", ephemeral=True)
    
    @commands.hybrid_command(name="kick", description="踢出成員")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "無"):
        """踢出成員"""
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("[失敗] 你需要踢出成員權限", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[失敗] 你不能踢出你自己", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[失敗] 你的權限不足以踢出此成員", ephemeral=True)
            return
        
        try:
            await user.kick(reason=reason)
            embed = discord.Embed(
                title="[成功] 已踢出成員",
                description=f"成員: {user.mention}\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法踢出成員: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="ban", description="封禁成員")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "無"):
        """封禁成員"""
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("[失敗] 你需要封禁成員權限", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[失敗] 你不能封禁你自己", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[失敗] 你的權限不足以封禁此成員", ephemeral=True)
            return
        
        try:
            await user.ban(reason=reason)
            embed = discord.Embed(
                title="[成功] 已封禁成員",
                description=f"成員: {user.mention}\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法封禁成員: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="mute", description="禁言成員")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, duration: int = 60, reason: str = "無"):
        """禁言成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("[失敗] 你需要管理成員權限", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[失敗] 你不能禁言你自己", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[失敗] 你的權限不足以禁言此成員", ephemeral=True)
            return
        
        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title="[成功] 已禁言成員",
                description=f"成員: {user.mention}\n時長: {duration} 分鐘\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法禁言成員: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="warn", description="警告成員")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, reason: str = "無"):
        """警告成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("[失敗] 你需要管理成員權限", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="[警告] 警告",
            description=f"{user.mention} 因為以下原因被警告:\n{reason}",
            color=discord.Color.from_rgb(241, 196, 15)
        )
        
        try:
            await user.send(embed=embed)
            await ctx.send(f"[成功] 已警告 {user.mention}", ephemeral=True)
        except Exception as e:
            await ctx.send(f"[警告] 已警告成員，但無法發送私訊: {str(e)}", ephemeral=True)
    
    @commands.command(name="幫助", description="顯示幫助訊息")
    async def help_command(self, ctx):
        """幫助命令"""
        embed = discord.Embed(
            title="[Help] 指令列表",
            color=discord.Color.blue(),
            description="所有可用的管理命令"
        )
        
        # 管理員指令
        embed.add_field(
            name="🛠️ 管理員指令",
            value="`/編刪紀錄設定` `!clear` `!kick` `!ban` `!mute` `!warn`",
            inline=False
        )
        
        # 開發者指令（不顯示用法）
        embed.add_field(
            name="🔐 開發者指令",
            value="僅限開發者使用",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ 其他",
            value="使用 `!幫助` 查看更多資訊",
            inline=False
        )
        
        embed.set_footer(text="使用 '/' 或 '!' 前綴來使用指令")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Admin(bot))

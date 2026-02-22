import discord
from discord.ext import commands
from datetime import timedelta
from src.utils.blacklist_manager import blacklist_manager

class Admin(commands.Cog):
    """Admin commands Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def is_blacklisted_check(self):
        """Blacklist check decorator"""
        async def predicate(ctx):
            if blacklist_manager.is_blacklisted(ctx.author.id):
                embed = discord.Embed(
                    title="[Denied] Access Denied",
                    description="You have been banned from using bot commands. Please contact an administrator.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return False
            return True
        return commands.check(predicate)
    
    @commands.hybrid_command(name="clear", description="Clear specified number of messages")
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clear(self, ctx, amount: int = 10):
        """Clear messages"""
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send("[Failed] You need manage messages permission", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await ctx.send("[Failed] Amount must be between 1-100", ephemeral=True)
            return
        
        await ctx.defer()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.followup.send(f"[Success] Cleared {len(deleted)} messages", ephemeral=True)
    
    @commands.hybrid_command(name="kick", description="Kick member")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        """Kick member"""
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("[Failed] You need kick members permission", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[Failed] You cannot kick yourself", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[Failed] Your permissions are insufficient to kick this member", ephemeral=True)
            return
        
        try:
            await user.kick(reason=reason)
            embed = discord.Embed(
                title="[Success] Member Kicked",
                description=f"Member: {user.mention}\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to kick member: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="ban", description="Ban member")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        """Ban member"""
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("[Failed] You need ban members permission", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[Failed] You cannot ban yourself", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[Failed] Your permissions are insufficient to ban this member", ephemeral=True)
            return
        
        try:
            await user.ban(reason=reason)
            embed = discord.Embed(
                title="[Success] Member Banned",
                description=f"Member: {user.mention}\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to ban member: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="mute", description="Mute member")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, duration: int = 60, reason: str = "No reason provided"):
        """Mute member"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("[Failed] You need moderate members permission", ephemeral=True)
            return
        
        if user == ctx.author:
            await ctx.send("[Failed] You cannot mute yourself", ephemeral=True)
            return
        
        if user.top_role >= ctx.author.top_role:
            await ctx.send("[Failed] Your permissions are insufficient to mute this member", ephemeral=True)
            return
        
        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title="[Success] Member Muted",
                description=f"Member: {user.mention}\nDuration: {duration} minutes\nReason: {reason}",
                color=discord.Color.from_rgb(46, 204, 113)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[Failed] Unable to mute member: {str(e)}", ephemeral=True)
    
    @commands.hybrid_command(name="warn", description="Warn member")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        """Warn member"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("[Failed] You need moderate members permission", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="[Warning] Warning",
            description=f"{user.mention} has been warned for the following reason:\n{reason}",
            color=discord.Color.from_rgb(241, 196, 15)
        )
        
        try:
            await user.send(embed=embed)
            await ctx.send(f"[Success] Warned {user.mention}", ephemeral=True)
        except Exception as e:
            await ctx.send(f"[Warning] Member warned but unable to send DM: {str(e)}", ephemeral=True)
    
    @commands.command(name="help", description="Display help message")
    async def help_command(self, ctx):
        """Help command"""
        embed = discord.Embed(
            title="[Help] Command List",
            color=discord.Color.blue(),
            description="All available admin commands"
        )
        
        # Admin commands
        embed.add_field(
            name="🛠️ Admin Commands",
            value="`/編刪紀錄設定` `!clear` `!kick` `!ban` `!mute` `!warn`",
            inline=False
        )
        
        # Developer commands (usage not shown)
        embed.add_field(
            name="🔐 Developer Commands",
            value="For developers only",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Other",
            value="Use `!help` for more information",
            inline=False
        )
        
        embed.set_footer(text="Use '/' or '!' prefix to use commands")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Load Cog"""
    await bot.add_cog(Admin(bot))

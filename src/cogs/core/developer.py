import discord
from discord.ext import commands
from discord import app_commands
from src.utils.blacklist_manager import blacklist_manager

class Developer(commands.Cog):
    """開發者專用指令 Cog - 只有開發者可見和使用"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.developer_id = 241619561760292866  # 開發者ID

    def is_developer_slash(self, interaction: discord.Interaction) -> bool:
        """斜杠指令的開發者檢查"""
        return interaction.user.id == self.developer_id

    @commands.command(name="#-bt", description="開發者專用黑名單管理指令")
    @commands.check(lambda ctx: ctx.author.id == 241619561760292866)
    async def blacklist_command(self, ctx, action: str = None, user_id: str = None):
        """黑名單管理指令 - 只有開發者可使用

        用法: #-bt <add|remove|list> [用戶ID]
        """
        if not action:
            embed = discord.Embed(
                title="[開發者] 黑名單管理",
                description="用法: `#-bt <add|remove|list> [用戶ID]`",
                color=discord.Color.purple()
            )
            embed.add_field(name="操作", value="• `add` - 添加用戶到黑名單\n• `remove` - 從黑名單移除用戶\n• `list` - 查看黑名單", inline=False)
            await ctx.send(embed=embed, ephemeral=True)
            return

        action = action.lower()

        if action == "list":
            blacklist = blacklist_manager.load_blacklist()
            if blacklist:
                embed = discord.Embed(
                    title="[開發者] 黑名單列表",
                    description=f"共 {len(blacklist)} 名用戶被禁止",
                    color=discord.Color.red()
                )
                for i, user_id in enumerate(blacklist, 1):
                    embed.add_field(name=f"用戶 {i}", value=f"`{user_id}`", inline=True)
            else:
                embed = discord.Embed(
                    title="[開發者] 黑名單列表",
                    description="黑名單為空",
                    color=discord.Color.green()
                )
            await ctx.send(embed=embed, ephemeral=True)

        elif action in ["add", "remove"]:
            if not user_id:
                await ctx.send("[錯誤] 請提供用戶ID", ephemeral=True)
                return

            try:
                user_id = int(user_id)
            except ValueError:
                await ctx.send("[錯誤] 無效的用戶ID", ephemeral=True)
                return

            if action == "add":
                blacklist_manager.add_to_blacklist(user_id)
                embed = discord.Embed(
                    title="[開發者] 已添加到黑名單",
                    description=f"用戶ID: `{user_id}`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed, ephemeral=True)

            elif action == "remove":
                blacklist_manager.remove_from_blacklist(user_id)
                embed = discord.Embed(
                    title="[開發者] 已從黑名單移除",
                    description=f"用戶ID: `{user_id}`",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send("[錯誤] 無效的操作，請使用 `add`, `remove` 或 `list`", ephemeral=True)

    @app_commands.command(name="dev-blacklist", description="開發者黑名單管理")
    @app_commands.describe(action="操作類型", user_id="用戶ID")
    @app_commands.choices(action=[
        app_commands.Choice(name="添加到黑名單", value="add"),
        app_commands.Choice(name="從黑名單移除", value="remove"),
        app_commands.Choice(name="查看黑名單", value="list")
    ])
    async def dev_blacklist_slash(self, interaction: discord.Interaction, action: str, user_id: str = None):
        """開發者專用斜杠指令 - 黑名單管理"""
        if not self.is_developer_slash(interaction):
            await interaction.response.send_message("[拒絕] 你沒有權限使用此指令", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if action == "list":
            blacklist = blacklist_manager.load_blacklist()
            if blacklist:
                embed = discord.Embed(
                    title="[開發者] 黑名單列表",
                    description=f"共 {len(blacklist)} 名用戶被禁止",
                    color=discord.Color.red()
                )
                for i, user_id in enumerate(blacklist, 1):
                    embed.add_field(name=f"用戶 {i}", value=f"`{user_id}`", inline=True)
            else:
                embed = discord.Embed(
                    title="[開發者] 黑名單列表",
                    description="黑名單為空",
                    color=discord.Color.green()
                )
            await interaction.followup.send(embed=embed)

        elif action in ["add", "remove"]:
            if not user_id:
                await interaction.followup.send("[錯誤] 請提供用戶ID")
                return

            try:
                user_id = int(user_id)
            except ValueError:
                await interaction.followup.send("[錯誤] 無效的用戶ID")
                return

            if action == "add":
                blacklist_manager.add_to_blacklist(user_id)
                embed = discord.Embed(
                    title="[開發者] 已添加到黑名單",
                    description=f"用戶ID: `{user_id}`",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)

            elif action == "remove":
                blacklist_manager.remove_from_blacklist(user_id)
                embed = discord.Embed(
                    title="[開發者] 已從黑名單移除",
                    description=f"用戶ID: `{user_id}`",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)

    @app_commands.command(name="dev-status", description="查看開發者狀態")
    async def dev_status_slash(self, interaction: discord.Interaction):
        """開發者狀態檢查"""
        if not self.is_developer_slash(interaction):
            await interaction.response.send_message("[拒絕] 你沒有權限使用此指令", ephemeral=True)
            return

        blacklist = blacklist_manager.load_blacklist()

        embed = discord.Embed(
            title="[開發者] 系統狀態",
            color=discord.Color.purple()
        )
        embed.add_field(name="開發者ID", value=f"`{self.developer_id}`", inline=True)
        embed.add_field(name="黑名單人數", value=f"{len(blacklist)} 人", inline=True)
        embed.add_field(name="機器人狀態", value="✅ 運行中", inline=True)
        embed.set_footer(text=f"請求者: {interaction.user.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="#-achievement", description="開發者成就解鎖命令")
    @commands.check(lambda ctx: ctx.author.id == 241619561760292866)
    async def unlock_achievement(self, ctx, user_id_str: str = None):
        """解鎖森之宿茶室成就 - 只有開發者可使用

        用法: #-achievement <用戶ID>
        """
        if not user_id_str:
            embed = discord.Embed(
                title="[開發者] 成就解鎖",
                description="用法: `#-achievement <用戶ID>`",
                color=discord.Color.purple()
            )
            embed.add_field(name="功能", value="手動為指定用戶解鎖 **森之宿茶室** 成就", inline=False)
            await ctx.send(embed=embed, ephemeral=True)
            return

        try:
            user_id = int(user_id_str)
        except ValueError:
            embed = discord.Embed(
                title="[開發者] 錯誤",
                description="用戶ID 必須是數字",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        achievements_cog = self.bot.get_cog("Achievements")
        if not achievements_cog:
            embed = discord.Embed(
                title="[開發者] 錯誤",
                description="成就系統未載入",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        try:
            is_new = achievements_cog.unlock_achievement(user_id, ctx.guild.id, "morinoyado_tearoom")
            if is_new:
                embed = discord.Embed(
                    title="[開發者] 成就已解鎖",
                    description=f"✅ 用戶 `{user_id}` 剛剛解鎖 **森之宿茶室** 成就",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="[開發者] 成就已擁有",
                    description=f"ℹ️ 用戶 `{user_id}` 已經擁有 **森之宿茶室** 成就",
                    color=discord.Color.blue()
                )
            embed.add_field(name="成就名稱", value="森之宿茶室", inline=True)
            embed.add_field(name="描述", value="從虛無中破殼而出", inline=True)
            embed.add_field(name="稀有度", value="[傳奇]", inline=True)
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="[開發者] 錯誤",
                description=f"解鎖失敗: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
    @commands.command(name="dev-status", description="開發者狀態檢查")
    @commands.check(lambda ctx: ctx.author.id == 241619561760292866)
    async def dev_status_command(self, ctx):
        """開發者狀態檢查"""
        blacklist = blacklist_manager.load_blacklist()

        embed = discord.Embed(
            title="[開發者] 系統狀態",
            color=discord.Color.purple()
        )
        embed.add_field(name="開發者ID", value=f"`{self.developer_id}`", inline=True)
        embed.add_field(name="黑名單人數", value=f"{len(blacklist)} 人", inline=True)
        embed.add_field(name="機器人狀態", value="✅ 運行中", inline=True)
        embed.set_footer(text=f"請求者: {ctx.author.name}")

        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Developer(bot))

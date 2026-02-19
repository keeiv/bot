import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

class UserServerInfo(commands.Cog):
    """用戶和伺服器信息 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def format_time(self, dt: datetime) -> str:
        """格式化時間為 年/月/日 時:分:秒"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(TZ_OFFSET)
        return local_dt.strftime("%Y/%m/%d %H:%M:%S")
    
    @app_commands.command(name="user_info", description="顯示用戶信息")
    @app_commands.describe(user="要查詢的用戶 (不填默認為自己)")
    async def user_info(self, interaction: discord.Interaction, user: discord.User = None):
        """顯示用戶信息"""
        try:
            # 如果未指定用戶，默認為當前用戶
            if user is None:
                user = interaction.user
            
            # 獲取伺服器成員信息（用於獲取加入時間）
            member = None
            if interaction.guild:
                try:
                    member = await interaction.guild.fetch_member(user.id)
                except discord.NotFound:
                    member = None
            
            # 創建 Embed
            embed = discord.Embed(
                title="用戶信息",
                color=discord.Color.from_rgb(52, 152, 219),
                timestamp=datetime.now(TZ_OFFSET)
            )
            
            # 設置用戶頭像
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            else:
                embed.set_thumbnail(url=user.default_avatar.url)
            
            # 設置 Banner
            if user.banner:
                embed.set_image(url=user.banner.url)
            
            # 添加用戶信息字段
            embed.add_field(name="用戶ID", value=str(user.id), inline=False)
            
            # 唯一用戶名 (username)
            embed.add_field(name="用戶名 (唯一)", value=f"@{user.name}", inline=False)
            
            # 顯示用戶名 (display name)
            display_name = user.display_name
            if member and member.nick:
                display_name = f"{member.nick} ({user.display_name})"
            embed.add_field(name="用戶名 (顯示名稱)", value=display_name, inline=False)
            
            # 帳號創立時間
            created_time = self.format_time(user.created_at)
            embed.add_field(name="帳號創立時間", value=created_time, inline=False)
            
            # 加入伺服器時間（如果在伺服器內）
            if member and member.joined_at:
                joined_time = self.format_time(member.joined_at)
                embed.add_field(name="加入伺服器時間", value=joined_time, inline=False)
            else:
                embed.add_field(name="加入伺服器時間", value="無法獲取或不在伺服器內", inline=False)
            
            # 帳號狀態
            status = "機器人" if user.bot else "普通用戶"
            embed.add_field(name="帳號狀態", value=status, inline=False)
            
            # 角色信息（如果在伺服器內）
            if member:
                roles = [role.mention for role in member.roles if role.name != "@everyone"]
                if roles:
                    embed.add_field(name="角色", value=" ".join(roles), inline=False)
                else:
                    embed.add_field(name="角色", value="無", inline=False)
            
            # 成就進度（如果在伺服器內）
            if interaction.guild and not user.bot:
                try:
                    achievements_cog = self.bot.get_cog("Achievements")
                    if achievements_cog:
                        progress = achievements_cog.get_progress(user.id, interaction.guild_id)
                        progress_bar = achievements_cog.get_progress_bar(progress["percentage"], 15)
                        embed.add_field(
                            name="成就進度",
                            value=f"{progress_bar}\n{progress['unlocked']}/{progress['total']} ({progress['percentage']}%)",
                            inline=False
                        )
                        
                        # 觸發查詢成就
                        achievements_cog.unlock_achievement(user.id, interaction.guild_id, "info_explorer")
                except Exception as e:
                    print(f"[成就] 顯示進度失敗: {e}")

            # osu 綁定信息
            if not user.bot:
                try:
                    osu_cog = self.bot.get_cog("OsuInfo")
                    if osu_cog:
                        if getattr(osu_cog, "api", None) is None:
                            raise RuntimeError("osu 功能尚未啟用")
                        bound_username = osu_cog.get_bound_osu_username(user.id)
                        if bound_username:
                            osu_user = osu_cog.api.user(bound_username)
                            stats = osu_user.statistics

                            global_rank = getattr(stats, "global_rank", None)
                            country_rank = getattr(stats, "country_rank", None)
                            pp = getattr(stats, "pp", None)
                            acc = getattr(stats, "hit_accuracy", None)

                            lines = []
                            lines.append(f"用戶名: {osu_user.username}")
                            lines.append(f"全球排名: {f'#{global_rank:,}' if isinstance(global_rank, int) else '未排名'}")
                            lines.append(f"國家排名: {f'#{country_rank:,}' if isinstance(country_rank, int) else '未排名'}")
                            lines.append(f"PP: {f'{pp:,.2f}' if isinstance(pp, (int, float)) else '未知'}")
                            lines.append(f"準確度: {f'{acc:.2f}%' if isinstance(acc, (int, float)) else '未知'}")
                            lines.append(f"連結: https://osu.ppy.sh/users/{osu_user.id}")

                            embed.add_field(name="osu 信息", value="\n".join(lines), inline=False)
                except Exception as e:
                    print(f"[osu] 顯示綁定信息失敗: {e}")
            
            embed.set_footer(text=f"查詢時間: {self.format_time(datetime.now(TZ_OFFSET))}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"[user_info] 錯誤: {e}")
            await interaction.response.send_message(f"[錯誤] 無法獲取用戶信息: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="server_info", description="顯示伺服器信息")
    async def server_info(self, interaction: discord.Interaction):
        """顯示伺服器信息"""
        try:
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message("[失敗] 此命令只能在伺服器中使用", ephemeral=True)
                return
            
            # 創建 Embed
            embed = discord.Embed(
                title="伺服器信息",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET)
            )
            
            # 設置伺服器圖標
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # 基本信息
            embed.add_field(name="伺服器名稱", value=guild.name, inline=False)
            embed.add_field(name="伺服器ID", value=str(guild.id), inline=False)
            
            # 創建時間
            created_time = self.format_time(guild.created_at)
            embed.add_field(name="創建時間", value=created_time, inline=False)
            
            # 擁有者信息
            owner = guild.owner
            if owner:
                embed.add_field(name="擁有者", value=f"{owner.mention} ({owner.name})", inline=False)
            else:
                embed.add_field(name="擁有者", value="無法獲取", inline=False)
            
            # 成員統計
            total_members = guild.member_count or 0
            bot_count = sum(1 for member in guild.members if member.bot)
            human_count = total_members - bot_count
            
            embed.add_field(name="成員統計", value=f"總計: {total_members}\n人類: {human_count}\nBot: {bot_count}", inline=False)
            
            # 頻道統計
            text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
            voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
            categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
            
            embed.add_field(
                name="頻道統計",
                value=f"文字: {text_channels}\n語音: {voice_channels}\n分類: {categories}",
                inline=False
            )
            
            # 角色數量
            role_count = len(guild.roles)
            embed.add_field(name="角色數量", value=str(role_count), inline=False)
            
            # 驗證等級
            verification_level = str(guild.verification_level).capitalize()
            embed.add_field(name="驗證等級", value=verification_level, inline=False)
            
            # 伺服器等級 (Boosts)
            embed.add_field(
                name="Boost 信息",
                value=f"等級: {guild.premium_tier}\nBoosts: {guild.premium_subscription_count}",
                inline=False
            )
            
            # 伺服器描述
            if guild.description:
                embed.add_field(name="描述", value=guild.description, inline=False)
            
            # 伺服器 Banner
            if guild.banner:
                embed.set_image(url=guild.banner.url)
            
            embed.set_footer(text=f"查詢時間: {self.format_time(datetime.now(TZ_OFFSET))}")
            
            await interaction.response.send_message(embed=embed)
            
            # 觸發成就
            try:
                achievements_cog = self.bot.get_cog("Achievements")
                if achievements_cog:
                    achievements_cog.unlock_achievement(interaction.user.id, guild.id, "server_analyst")
            except Exception as e:
                print(f"[成就] 伺服器分析成就觸發失敗: {e}")
            
        except Exception as e:
            print(f"[server_info] 錯誤: {e}")
            await interaction.response.send_message(f"[錯誤] 無法獲取伺服器信息: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(UserServerInfo(bot))

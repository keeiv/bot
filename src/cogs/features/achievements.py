"""成就系統 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.services.achievement_service import ACHIEVEMENTS
from src.services.achievement_service import AchievementService

TZ_OFFSET = timezone(timedelta(hours=8))


class Achievements(commands.Cog):
    """成就系統 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = AchievementService()

    # ─────────────── 顯示工具 (UI 專屬) ───────────────

    @staticmethod
    def get_rarity_emoji(rarity: str) -> str:
        """取得稀有度標籤"""
        return {
            "common": "[通常]",
            "uncommon": "[罕見]",
            "rare": "[稀有]",
            "epic": "[史詩]",
            "legendary": "[傳說]",
        }.get(rarity, "[不知]")

    @staticmethod
    def get_rarity_display(rarity: str) -> str:
        """取得稀有度顯示名稱"""
        return {
            "common": "通常",
            "uncommon": "罕見",
            "rare": "稀有",
            "epic": "史詩",
            "legendary": "傳說",
        }.get(rarity, "未知")

    @staticmethod
    def get_rarity_color(rarity: str) -> discord.Color:
        """取得稀有度顏色"""
        return {
            "common": discord.Color.from_rgb(128, 128, 128),
            "uncommon": discord.Color.from_rgb(46, 204, 113),
            "rare": discord.Color.from_rgb(52, 152, 219),
            "epic": discord.Color.from_rgb(155, 89, 182),
            "legendary": discord.Color.from_rgb(241, 196, 15),
        }.get(rarity, discord.Color.from_rgb(128, 128, 128))

    # ─────────────── 指令 ───────────────

    @app_commands.command(name="achievements", description="查看成就")
    @app_commands.describe(user="要查詢的用戶 (不填默認為自己)")
    async def achievements_command(
        self, interaction: discord.Interaction, user: discord.User = None
    ):
        """查看成就"""
        await interaction.response.defer()
        if user is None:
            user = interaction.user

        unlocked = self.service.get_user_achievements(user.id, interaction.guild_id)
        progress = self.service.get_progress(user.id, interaction.guild_id)

        embed = discord.Embed(
            title="成就收集",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.set_thumbnail(
            url=user.avatar.url if user.avatar else user.default_avatar.url
        )
        embed.add_field(
            name="用戶", value=f"{user.mention} ({user.name})", inline=False
        )

        progress_bar = self.service.get_progress_bar(progress["percentage"])
        embed.add_field(
            name="成就進度",
            value=f"{progress_bar}\n{progress['unlocked']}/{progress['total']} ({progress['percentage']}%)",
            inline=False,
        )

        if unlocked:
            achievement_list = [
                f"{self.get_rarity_emoji(ACHIEVEMENTS[aid]['rarity'])} {ACHIEVEMENTS[aid]['name']}"
                for aid in unlocked
                if aid in ACHIEVEMENTS
            ]
            for i in range(0, len(achievement_list), 10):
                embed.add_field(
                    name=f"已解鎖成就 (第 {i//10 + 1} 頁)",
                    value="\n".join(achievement_list[i : i + 10]),
                    inline=False,
                )
        else:
            embed.add_field(name="已解鎖成就", value="尚未解鎖任何成就", inline=False)

        embed.set_footer(
            text=f"更新於 {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="achievement_codex", description="查看成就圖鑑")
    async def achievement_codex(self, interaction: discord.Interaction):
        """查看所有可用成就的圖鑑"""
        await interaction.response.defer()
        self.service.unlock(
            interaction.user.id, interaction.guild.id, "achievement_explorer"
        )

        rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
        by_rarity = {r: [] for r in rarity_order}
        for aid, adata in ACHIEVEMENTS.items():
            if adata.get("developer_only"):
                continue
            by_rarity[adata.get("rarity", "common")].append((aid, adata))

        embeds = []
        title_embed = discord.Embed(
            title="成就圖鑑",
            description="查看所有可解鎖的成就\n\n使用 `/achievement_info <成就ID>` 查看詳細資訊",
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        title_embed.add_field(
            name="統計",
            value=f"總成就數: {len([a for a in ACHIEVEMENTS.values() if not a.get('developer_only')])}\n稀有度: 通常 > 罕見 > 稀有 > 史詩 > 傳說",
            inline=False,
        )
        embeds.append(title_embed)

        for rarity in rarity_order:
            if not by_rarity[rarity]:
                continue
            embed = discord.Embed(
                title=f"{self.get_rarity_emoji(rarity)} 成就圖鑑",
                color=self.get_rarity_color(rarity),
                timestamp=datetime.now(TZ_OFFSET),
            )
            for aid, adata in by_rarity[rarity]:
                embed.add_field(
                    name=f"**{adata['name']}**\n{adata['description']}",
                    value=f"`{aid}`",
                    inline=False,
                )
            embeds.append(embed)

        await interaction.followup.send(embeds=embeds)

    @app_commands.command(name="achievement_info", description="查看成就詳細資訊")
    @app_commands.describe(achievement="成就名稱或 ID")
    async def achievement_info(
        self, interaction: discord.Interaction, achievement: str
    ):
        """查看成就詳細資訊"""
        achievement_id = None
        achievement_data = None

        if achievement in ACHIEVEMENTS:
            achievement_id = achievement
            achievement_data = ACHIEVEMENTS[achievement]
        else:
            for aid, adata in ACHIEVEMENTS.items():
                if achievement.lower() in adata["name"].lower():
                    achievement_id = aid
                    achievement_data = adata
                    break

        if not achievement_data:
            await interaction.response.send_message(
                "[失敗] 找不到該成就", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=achievement_data["name"],
            description=achievement_data["description"],
            color=self.get_rarity_color(achievement_data["rarity"]),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name="稀有度",
            value=self.get_rarity_display(achievement_data["rarity"]),
            inline=False,
        )
        embed.add_field(name="成就 ID", value=f"`{achievement_id}`", inline=False)
        await interaction.response.send_message(embed=embed)

    # ─────────────── 成就觸發 (供其他 Cog 呼叫) ───────────────

    def trigger_edit_achievement(self, user_id: int, guild_id: int):
        """觸發編輯成就"""
        self.service.unlock(user_id, guild_id, "first_edit")

    def trigger_delete_achievement(self, user_id: int, guild_id: int):
        """觸發刪除成就"""
        self.service.unlock(user_id, guild_id, "first_delete")

    def trigger_interaction_achievement(self, user_id: int, guild_id: int):
        """觸發互動成就"""
        self.service.unlock(user_id, guild_id, "first_interaction")

    def trigger_game_loss(self, user_id: int, guild_id: int, game_type: str):
        """觸發遊戲失敗成就"""
        if game_type == "russian_roulette":
            self.service.unlock(user_id, guild_id, "halo_broken")
        elif game_type == "submarine":
            self.service.unlock(user_id, guild_id, "kursk_sinking")

    def trigger_codex_achievement(self, user_id: int, guild_id: int):
        """觸發圖鑑成就"""
        self.service.unlock(user_id, guild_id, "achievement_explorer")

    def unlock_achievement(
        self, user_id: int, guild_id: int, achievement_id: str
    ) -> bool:
        """解鎖成就 (向後相容接口)"""
        return self.service.unlock(user_id, guild_id, achievement_id)


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Achievements(bot))

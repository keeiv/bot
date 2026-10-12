"""成就系統 Cog"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import discord
from discord import app_commands
from discord.ext import commands

from src.services.achievement_service import ACHIEVEMENTS
from src.services.achievement_service import AchievementService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage

TZ_OFFSET = timezone(timedelta(hours=8))


class Achievements(commands.Cog):
    """成就系統 Cog"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AchievementService()

    # ─────────────── 顯示工具 (UI 專屬) ───────────────

    @staticmethod
    def get_rarity_emoji(rarity: str) -> str:
        """取得稀有度標籤"""
        return {
            "common": tx("achievements.common"),
            "uncommon": tx("achievements.uncommon"),
            "rare": tx("achievements.rare"),
            "epic": tx("achievements.epic"),
            "legendary": tx("achievements.legendary"),
        }.get(rarity, tx("achievements.unknown"))

    @staticmethod
    def get_rarity_display(rarity: str) -> str:
        """取得稀有度顯示名稱"""
        return {
            "common": tx("achievements.common_bd3455"),
            "uncommon": tx("achievements.uncommon_7fcf13"),
            "rare": tx("achievements.rare_543cfd"),
            "epic": tx("achievements.epic_e7b2e9"),
            "legendary": tx("achievements.legendary_2b29b5"),
        }.get(rarity, tx("audit_log.unknown"))

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

    @app_commands.command(name="achievements", description="Show achievements")
    @app_commands.describe(user="The user to look up (defaults to you)")
    @localized("interaction")
    async def achievements_command(
        self,
        interaction: discord.Interaction,
        user: discord.User | discord.Member | None = None,
    ) -> None:
        """查看成就"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        if user is None:
            user = interaction.user

        unlocked = await run_storage(
            self.service.get_user_achievements, user.id, interaction.guild_id
        )
        progress = await run_storage(
            self.service.get_progress, user.id, interaction.guild_id
        )

        embed = discord.Embed(
            title=tx("achievements.achievement_collection"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.set_thumbnail(
            url=user.avatar.url if user.avatar else user.default_avatar.url
        )
        embed.add_field(
            name=tx("audit_log.user"),
            value=f"{user.mention} ({user.name})",
            inline=False,
        )

        progress_bar = self.service.get_progress_bar(progress["percentage"])
        embed.add_field(
            name=tx("achievements.achievement_progress"),
            value=f"{progress_bar}\n{progress['unlocked']}/{progress['total']} ({progress['percentage']}%)",
            inline=False,
        )

        if unlocked:
            achievement_list = [
                f"{self.get_rarity_emoji(ACHIEVEMENTS[aid]['rarity'])} {self.service.describe(aid)['name']}"
                for aid in unlocked
                if aid in ACHIEVEMENTS
            ]
            for i in range(0, len(achievement_list), 10):
                embed.add_field(
                    name=tx(
                        "achievements.unlocked_achievements_page", v0=(i // 10 + 1)
                    ),
                    value="\n".join(achievement_list[i : i + 10]),
                    inline=False,
                )
        else:
            embed.add_field(
                name=tx("achievements.unlocked_achievements"),
                value=tx("achievements.no_achievements_unlocked_yet"),
                inline=False,
            )

        embed.set_footer(
            text=tx(
                "achievements.updated_at",
                v0=(datetime.now(TZ_OFFSET).strftime("%Y/%m/%d %H:%M:%S")),
            )
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="achievement_codex", description="Browse every achievement"
    )
    @localized("interaction")
    async def achievement_codex(self, interaction: discord.Interaction) -> None:
        """查看所有可用成就的圖鑑"""
        if (
            interaction.guild is None
            or interaction.guild_id is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                tx("bot_appearance.this_feature_is_only_available_in"), ephemeral=True
            )
            return
        await interaction.response.defer()
        await run_storage(
            self.service.unlock,
            interaction.user.id,
            interaction.guild.id,
            "achievement_explorer",
        )

        rarity_order = ["legendary", "epic", "rare", "uncommon", "common"]
        by_rarity = {r: [] for r in rarity_order}
        for aid, adata in ACHIEVEMENTS.items():
            if adata.get("developer_only"):
                continue
            by_rarity[adata.get("rarity", "common")].append((aid, adata))

        embeds = []
        title_embed = discord.Embed(
            title=tx("achievements.achievement_catalogue"),
            description=tx(
                "achievements.browse_all_unlockable_achievements_use_achievement"
            ),
            color=discord.Color.from_rgb(241, 196, 15),
            timestamp=datetime.now(TZ_OFFSET),
        )
        title_embed.add_field(
            name=tx("achievements.statistics"),
            value=tx(
                "achievements.total_achievements_rarities_common_uncommon_rare",
                v0=(
                    len(
                        [
                            a
                            for a in ACHIEVEMENTS.values()
                            if not a.get("developer_only")
                        ]
                    )
                ),
            ),
            inline=False,
        )
        embeds.append(title_embed)

        for rarity in rarity_order:
            if not by_rarity[rarity]:
                continue
            embed = discord.Embed(
                title=tx(
                    "achievements.achievement_catalogue_83481e",
                    v0=(self.get_rarity_emoji(rarity)),
                ),
                color=self.get_rarity_color(rarity),
                timestamp=datetime.now(TZ_OFFSET),
            )
            for aid, adata in by_rarity[rarity]:
                adata = self.service.describe(aid)
                embed.add_field(
                    name=f"**{adata['name']}**\n{adata['description']}",
                    value=f"`{aid}`",
                    inline=False,
                )
            embeds.append(embed)

        await interaction.followup.send(embeds=embeds)

    @app_commands.command(
        name="achievement_info", description="Show details of an achievement"
    )
    @app_commands.describe(achievement="Achievement name or ID")
    @localized("interaction")
    async def achievement_info(
        self, interaction: discord.Interaction, achievement: str
    ) -> None:
        """查看成就詳細資訊"""
        achievement_id = None
        achievement_data = None

        if achievement in ACHIEVEMENTS:
            achievement_id = achievement
            achievement_data = self.service.describe(achievement)
        else:
            for aid, adata in ACHIEVEMENTS.items():
                translated = self.service.describe(aid)
                if any(
                    achievement.casefold() in name.casefold()
                    for name in (adata["name"], translated["name"])
                ):
                    achievement_id = aid
                    achievement_data = translated
                    break

        if not achievement_data:
            await interaction.response.send_message(
                tx("achievements.failed_achievement_not_found"), ephemeral=True
            )
            return

        embed = discord.Embed(
            title=achievement_data["name"],
            description=achievement_data["description"],
            color=self.get_rarity_color(achievement_data["rarity"]),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("achievements.rarity"),
            value=self.get_rarity_display(achievement_data["rarity"]),
            inline=False,
        )
        embed.add_field(
            name=tx("achievements.achievement_id"),
            value=f"`{achievement_id}`",
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    # ─────────────── 成就觸發 (供其他 Cog 呼叫) ───────────────

    def trigger_edit_achievement(self, user_id: int, guild_id: int) -> None:
        """觸發編輯成就"""
        self.service.unlock(user_id, guild_id, "first_edit")

    def trigger_delete_achievement(self, user_id: int, guild_id: int) -> None:
        """觸發刪除成就"""
        self.service.unlock(user_id, guild_id, "first_delete")

    def trigger_interaction_achievement(self, user_id: int, guild_id: int) -> None:
        """觸發互動成就"""
        self.service.unlock(user_id, guild_id, "first_interaction")

    def trigger_game_loss(self, user_id: int, guild_id: int, game_type: str) -> None:
        """觸發遊戲失敗成就"""
        if game_type == "russian_roulette":
            self.service.unlock(user_id, guild_id, "halo_broken")
        elif game_type == "submarine":
            self.service.unlock(user_id, guild_id, "kursk_sinking")

    def trigger_codex_achievement(self, user_id: int, guild_id: int) -> None:
        """觸發圖鑑成就"""
        self.service.unlock(user_id, guild_id, "achievement_explorer")

    def unlock_achievement(
        self, user_id: int, guild_id: int, achievement_id: str
    ) -> bool:
        """解鎖成就 (向後相容接口)"""
        return self.service.unlock(user_id, guild_id, achievement_id)


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(Achievements(bot))

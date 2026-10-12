import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import genshin

from src.services.genshin_service import GenshinService
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedModal
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage

TZ_OFFSET = timezone(timedelta(hours=8))


class CookieBindModal(LocalizedModal):
    """彈出式輸入視窗：安全輸入 Cookie 各個欄位"""

    def __init__(
        self, service: "GenshinService", cog: "GenshinCog", region: str
    ) -> None:
        title = (
            tx("genshin_cog.link_a_miyoushe_china_account")
            if region == "cn"
            else tx("genshin_cog.link_a_hoyolab_global_account")
        )
        super().__init__(title=title)
        self.service = service
        self.cog = cog
        self.region = region

        # 根據區域設定不同的欄位
        if region == "cn":
            self.ltoken = discord.ui.TextInput[Any](
                label="ltoken",
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_ltoken_value_a_long"),
                required=True,
            )
            self.ltuid = discord.ui.TextInput[Any](
                label="ltuid",
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_ltuid_value_the_numeric"),
                required=True,
            )
            self.cookie_token = discord.ui.TextInput[Any](
                label=tx("genshin_cog.cookie_token_optional_needed_for_gift"),
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_cookie_token_value"),
                required=False,
            )
            self.add_item(self.ltoken)
            self.add_item(self.ltuid)
            self.add_item(self.cookie_token)
        else:
            self.ltoken_v2 = discord.ui.TextInput[Any](
                label="ltoken_v2",
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_ltoken_v2_value_a"),
                required=True,
            )
            self.ltuid_v2 = discord.ui.TextInput[Any](
                label="ltuid_v2",
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_ltuid_v2_value_the"),
                required=True,
            )
            self.cookie_token_v2 = discord.ui.TextInput[Any](
                label=tx("genshin_cog.cookie_token_v2_optional_needed_for"),
                style=discord.TextStyle.short,
                placeholder=tx("genshin_cog.paste_the_cookie_token_v2_value"),
                required=False,
            )
            self.add_item(self.ltoken_v2)
            self.add_item(self.ltuid_v2)
            self.add_item(self.cookie_token_v2)

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        if self.region == "cn":
            ltoken_val = self.ltoken.value.strip()
            ltuid_val = self.ltuid.value.strip()
            cookie_token_val = self.cookie_token.value.strip()
            cookie_parts = [f"ltoken={ltoken_val};", f"ltuid={ltuid_val};"]
            if cookie_token_val:
                cookie_parts.append(f"cookie_token={cookie_token_val};")
                cookie_parts.append(f"account_id={ltuid_val};")
            field_names = ["ltoken", "ltuid"]
        else:
            ltoken_val = self.ltoken_v2.value.strip()
            ltuid_val = self.ltuid_v2.value.strip()
            cookie_token_val = self.cookie_token_v2.value.strip()
            cookie_parts = [f"ltoken_v2={ltoken_val};", f"ltuid_v2={ltuid_val};"]
            if cookie_token_val:
                cookie_parts.append(f"cookie_token_v2={cookie_token_val};")
                cookie_parts.append(f"account_id_v2={ltuid_val};")
            field_names = ["ltoken_v2", "ltuid_v2"]

        cookie_str = " ".join(cookie_parts)

        try:
            accounts = await self.service.bind_account(
                interaction.user.id, cookie_str, self.region
            )

            region_display = (
                tx("genshin_cog.china_miyoushe")
                if self.region == "cn"
                else tx("genshin_cog.global_hoyolab")
            )
            embed = discord.Embed(
                title=tx("genshin_cog.account_linked", v0=(region_display)),
                description=tx("genshin_cog.account_cookies_have_been_encrypted_and"),
                color=discord.Color.from_rgb(46, 204, 113),
            )

            for acc in accounts:
                game_name = self.cog._get_game_display_name(
                    self.service.map_game_biz_to_str(acc["game_biz"])
                )
                embed.add_field(
                    name=f" {game_name}",
                    value=tx(
                        "genshin_cog.nickname_uid_level_lv_server",
                        v0=(acc["nickname"]),
                        v1=(acc["uid"]),
                        v2=(acc["level"]),
                        v3=(acc["server_name"]),
                    ),
                    inline=True,
                )

            embed.set_footer(text=tx("genshin_cog.automatic_daily_check_in_is_enabled"))
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                tx(
                    "genshin_cog.linking_failed_check_that_and_are",
                    v0=(str(e)),
                    v1=(field_names[0]),
                    v2=(field_names[1]),
                    v3=(
                        tx("genshin_cog.miyoushe_china")
                        if self.region == "cn"
                        else tx("genshin_cog.hoyolab_global")
                    ),
                ),
                ephemeral=True,
            )


class TutorialView(LocalizedView):
    """用於顯示國服/國際服 Cookie 教學的按鈕選單"""

    i18n = {
        "global_tutorial.label": "genshin_cog.global_hoyolab_guide",
        "cn_tutorial.label": "genshin_cog.china_miyoushe_guide",
    }

    def __init__(self, cog: "GenshinCog") -> None:
        super().__init__(timeout=180)
        self.cog = cog

    def _create_tutorial_embed(self, region: str) -> discord.Embed:
        """建立教學 embed"""
        if region == "global":
            title = tx("genshin_cog.hoyolab_global_cookie_guide")
            color = discord.Color.from_rgb(52, 152, 219)
            url = "https://www.hoyolab.com/"
            site_name = tx("genshin_cog.hoyolab_website")
        else:
            title = tx("genshin_cog.miyoushe_china_cookie_guide")
            color = discord.Color.from_rgb(46, 204, 113)
            url = "https://www.miyoushe.com/"
            site_name = tx("genshin_cog.miyoushe_website")

        embed = discord.Embed(
            title=title,
            description=(
                tx("genshin_cog.follow_these_steps_to_obtain_hoyolab")
                if region == "global"
                else tx("genshin_cog.follow_these_steps_to_obtain_miyoushe")
            ),
            color=color,
        )
        embed.add_field(
            name=tx("genshin_cog.1_sign_in_to_the_website"),
            value=tx(
                "genshin_cog.open_in_a_desktop_browser_such", v0=(site_name), v1=(url)
            ),
            inline=False,
        )
        embed.add_field(
            name=tx("genshin_cog.2_open_developer_tools"),
            value=tx("genshin_cog.press_f12_on_the_website_or"),
            inline=False,
        )
        embed.add_field(
            name=tx("genshin_cog.3_open_cookie_storage"),
            value=(
                tx("genshin_cog.in_developer_tools_open_the_application")
                if region == "global"
                else tx("genshin_cog.expand_cookies_on_the_left_and")
            ),
            inline=False,
        )

        if region == "global":
            field4_value = tx("genshin_cog.in_the_cookies_table_find_these")
            field5_value = tx("genshin_cog.in_discord_run_mhy_bind_select")
        else:
            field4_value = tx("genshin_cog.in_the_cookies_table_find_these_e39310")
            field5_value = tx("genshin_cog.in_discord_run_mhy_bind_select_2a8fb7")

        embed.add_field(
            name=tx("genshin_cog.4_copy_each_value"), value=field4_value, inline=False
        )
        embed.add_field(
            name=tx("genshin_cog.5_complete_linking_in_discord"),
            value=field5_value,
            inline=False,
        )
        embed.set_footer(text=tx("genshin_cog.cookies_are_login_credentials_do_not"))
        return embed

    @discord.ui.button(
        label=" Global (HoYoLAB) guide", style=discord.ButtonStyle.primary
    )
    @localized("interaction")
    async def global_tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        embed = self._create_tutorial_embed("global")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="🇨🇳 China (Miyoushe) guide", style=discord.ButtonStyle.success
    )
    @localized("interaction")
    async def cn_tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        embed = self._create_tutorial_embed("cn")
        await interaction.response.edit_message(embed=embed, view=self)


class GenshinCog(commands.Cog):
    """HoYoLAB / 米游社 相關自動化與查詢功能"""

    # Personal tool: also usable in DMs and servers without the bot.
    mhy_group = app_commands.Group(
        name="mhy",
        description="HoYoLAB / Miyoushe",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    def __init__(self, bot: commands.Bot) -> None:
        """初始化 GenshinCog"""
        self.bot = bot
        self.service = GenshinService()

        # 啟動自動簽到背景任務
        self._auto_signin_loop.start()
        # 異步載入角色資料庫快取
        self._character_task = asyncio.create_task(self._init_character_names())

    async def cog_unload(self) -> None:
        """卸載 Cog 時取消背景任務"""
        self._auto_signin_loop.cancel()
        self._character_task.cancel()
        await asyncio.gather(self._character_task, return_exceptions=True)

    async def _init_character_names(self) -> None:
        """初始化角色資料庫快取"""
        try:
            print("[Genshin Cog] 正在下載與更新角色資料庫快取...")
            await genshin.utility.update_characters_any(
                langs=["zh-cn", "zh-tw", "en-us"]
            )
            print("[Genshin Cog] 角色資料庫快取更新完成！")
        except Exception as e:
            print(f"[Genshin Cog] 角色資料庫快取更新失敗: {e}")

    def _get_game_display_name(self, game_str: str) -> str:
        """取得遊戲顯示名稱"""
        mapping = {
            "genshin": tx("genshin_cog.genshin_impact"),
            "starrail": tx("genshin_cog.honkai_star_rail"),
            "zzz": tx("genshin_cog.zenless_zone_zero"),
            "honkai": tx("genshin_cog.honkai_impact_3rd"),
            "tot": tx("genshin_cog.tears_of_themis"),
        }
        return mapping.get(game_str.lower(), "HoYoLAB")

    def _format_seconds(self, seconds: int) -> str:
        """格式化秒數為可讀時間"""
        if seconds <= 0:
            return tx("genshin_cog.full")
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return tx("genshin_cog.about_hours_minutes", v0=(hours), v1=(minutes))
        return tx("genshin_cog.about_minutes", v0=(minutes))

    # ─────────────── 背景簽到任務 ───────────────

    @tasks.loop(minutes=30)
    async def _auto_signin_loop(self) -> None:
        now = datetime.now(TZ_OFFSET)
        # 設定在清晨 8:00 後自動進行簽到
        # 如果今日尚未執行，且目前時間已過 8:00 AM，則開始執行
        if now.hour >= 8:
            today_str = now.strftime("%Y-%m-%d")
            last_run = await run_storage(self.service.get_last_signin_date)
            if last_run != today_str:
                await run_storage(self.service.save_last_signin_date, today_str)
                print(f"[Genshin Cog] 啟動 {today_str} 自動每日簽到...")
                results = await self.service.run_global_auto_sign_in()

                # 私訊通知使用者
                for user_id, user_results in results.items():
                    await self._send_signin_report(user_id, user_results)

    @localized("user_id")
    async def _send_signin_report(self, user_id: int, user_results: list) -> None:
        try:
            user = self.bot.get_user(user_id)
            if user is None:
                user = await self.bot.fetch_user(user_id)
            if user:
                embed = discord.Embed(
                    title=tx("genshin_cog.hoyolab_miyoushe_automatic_daily_check_in"),
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                lines = []
                for res in user_results:
                    game_name = self._get_game_display_name(res["game"])
                    status_emoji = "" if res["success"] else ""
                    lines.append(
                        f"{status_emoji} **{game_name}** ({res['nickname']}): {res['message']}"
                    )
                embed.description = "\n".join(lines)
                embed.set_footer(
                    text=tx("genshin_cog.use_mhy_toggle_autosignin_to_disable")
                )
                await user.send(embed=embed)
        except Exception as e:
            print(f"[Genshin Cog] 無法發送通知給使用者 {user_id}: {e}")

    @_auto_signin_loop.before_loop
    async def _before_auto_signin(self) -> None:
        try:
            await self.bot.wait_until_ready()
        except RuntimeError:
            self._auto_signin_loop.cancel()

    # ─────────────── 斜線指令 ───────────────

    @mhy_group.command(
        name="bind",
        description="Link your HoYoLAB / Miyoushe cookie securely (opens a form)",
    )
    @app_commands.describe(region="Your region: Global (HoYoLAB) or China (Miyoushe)")
    @app_commands.choices(
        region=[
            app_commands.Choice(name="Global (HoYoLAB)", value="global"),
            app_commands.Choice(name="China (Miyoushe)", value="cn"),
        ]
    )
    @localized("interaction")
    async def mhy_bind(self, interaction: discord.Interaction, region: str) -> None:
        modal = CookieBindModal(self.service, self, region)
        await interaction.response.send_modal(modal)

    @mhy_group.command(
        name="tutorial", description="How to get your HoYoLAB / Miyoushe cookie"
    )
    @localized("interaction")
    async def mhy_tutorial(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=tx("genshin_cog.miyoushe_hoyolab_cookie_guide"),
            description=(tx("genshin_cog.account_cookies_are_required_for_automatic")),
            color=discord.Color.from_rgb(155, 89, 182),
            timestamp=datetime.now(TZ_OFFSET),
        )

        embed.set_footer(
            text=tx("genshin_cog.cookies_are_encrypted_before_storage_keep")
        )
        view = TutorialView(self)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @mhy_group.command(
        name="unbind",
        description="Unlink your HoYoLAB / Miyoushe account and delete the cookie",
    )
    @localized("interaction")
    async def mhy_unbind(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        success = await run_storage(self.service.unbind_account, interaction.user.id)
        if success:
            await interaction.followup.send(
                tx("genshin_cog.account_unlinked_the_stored_encrypted_cookies"),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                tx("genshin_cog.no_hoyolab_miyoushe_account_is_linked"), ephemeral=True
            )

    @mhy_group.command(
        name="status", description="Show your linked account and settings"
    )
    @localized("interaction")
    async def mhy_status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        user_data = self.service.get_bound_user(interaction.user.id)
        if not user_data:
            await interaction.followup.send(
                tx("genshin_cog.no_hoyolab_miyoushe_account_is_linked_3c194c"),
                ephemeral=True,
            )
            return

        region_display = (
            tx("genshin_cog.china_miyoushe")
            if user_data.get("region") == "cn"
            else tx("genshin_cog.global_hoyolab")
        )
        auto_signin_display = (
            tx("genshin_cog.enabled")
            if user_data.get("auto_sign_in", True)
            else tx("genshin_cog.disabled")
        )

        embed = discord.Embed(
            title=tx("genshin_cog.hoyolab_miyoushe_linking_status"),
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(
            name=tx("genshin_cog.account_region"), value=region_display, inline=True
        )
        embed.add_field(
            name=tx("genshin_cog.automatic_check_in"),
            value=auto_signin_display,
            inline=True,
        )

        accounts = user_data.get("game_accounts", [])
        if accounts:
            accounts_lines = []
            for acc in accounts:
                game_name = self._get_game_display_name(
                    self.service.map_game_biz_to_str(acc["game_biz"])
                )
                accounts_lines.append(
                    f"• **{game_name}** - {acc['nickname']} (UID: `{acc['uid']}`) [Lv.{acc['level']} - {acc['server_name']}]"
                )
            embed.add_field(
                name=tx("genshin_cog.linked_game_accounts"),
                value="\n".join(accounts_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name=tx("genshin_cog.linked_game_accounts"),
                value=tx("genshin_cog.no_linked_characters"),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @mhy_group.command(
        name="toggle_autosignin", description="Turn daily auto check-in on or off"
    )
    @app_commands.describe(enable="Whether to check in automatically every day")
    @localized("interaction")
    async def mhy_toggle_autosignin(
        self, interaction: discord.Interaction, enable: bool
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        success = await run_storage(
            self.service.toggle_auto_sign_in, interaction.user.id, enable
        )
        if success:
            status = (
                tx("settings.enabled_0ae5c7") if enable else tx("settings.disabled")
            )
            await interaction.followup.send(
                tx("genshin_cog.automatic_daily_check_in", v0=(status)), ephemeral=True
            )
        else:
            await interaction.followup.send(
                tx("genshin_cog.settings_could_not_be_saved_check"), ephemeral=True
            )

    @mhy_group.command(
        name="checkin", description="Check in to all your games for today now"
    )
    @localized("interaction")
    async def mhy_checkin(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.service.claim_daily_signin_for_user(
                interaction.user.id
            )

            embed = discord.Embed(
                title=tx("genshin_cog.daily_check_in_results"),
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )

            if not results:
                embed.description = tx(
                    "genshin_cog.no_characters_supporting_check_in_were"
                )
            else:
                lines = []
                for res in results:
                    game_name = self._get_game_display_name(res["game"])
                    status_emoji = "" if res["success"] else ""
                    lines.append(
                        f"{status_emoji} **{game_name}** ({res['nickname']}): {res['message']}"
                    )
                embed.description = "\n".join(lines)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                tx("genshin_cog.check_in_failed", v0=(str(e))), ephemeral=True
            )

    @mhy_group.command(
        name="notes",
        description="Show real-time notes for a game (resin, power, battery and so on)",
    )
    @app_commands.describe(game="The game")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="starrail"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
            app_commands.Choice(name="Honkai Impact 3rd", value="honkai"),
        ]
    )
    @localized("interaction")
    async def mhy_notes(self, interaction: discord.Interaction, game: str) -> None:
        await interaction.response.defer()

        try:
            notes = await self.service.get_notes(interaction.user.id, game)

            if game == "genshin":
                embed = discord.Embed(
                    title=tx("genshin_cog.genshin_impact_real_time_notes"),
                    color=discord.Color.from_rgb(62, 155, 150),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("genshin_cog.original_resin"),
                    value=tx(
                        "genshin_cog.full_in",
                        v0=(notes["current_resin"]),
                        v1=(notes["max_resin"]),
                        v2=(self._format_seconds(notes["resin_recovery"])),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.realm_currency"),
                    value=f" **{notes['current_currency']} / {notes['max_currency']}**",
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.daily_commissions"),
                    value=tx(
                        "genshin_cog.bonus_reward",
                        v0=(notes["commissions"]),
                        v1=(notes["max_commissions"]),
                        v2=(
                            tx("genshin_cog.claimed")
                            if notes["commission_reward_claimed"]
                            else tx("genshin_cog.not_claimed")
                        ),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.weekly_boss_discounts"),
                    value=tx(
                        "genshin_cog.remaining",
                        v0=(notes["weekly_boss_discounts"]),
                        v1=(notes["max_weekly_boss_discounts"]),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.parametric_transformer"),
                    value=f"️ **{notes['transformer_recovery']}**",
                    inline=True,
                )

                exp_list = []
                completed_count = 0
                for exp in notes["expeditions"]:
                    remained = exp["remained"]
                    status_text = (
                        tx("genshin_cog.completed")
                        if remained <= 0
                        else tx(
                            "genshin_cog.remaining_6cdafb",
                            v0=(self._format_seconds(remained)),
                        )
                    )
                    exp_list.append(tx("genshin_cog.expedition", v0=(status_text)))
                    if remained <= 0:
                        completed_count += 1

                embed.add_field(
                    name=tx(
                        "genshin_cog.expeditions",
                        v0=(completed_count),
                        v1=(notes["max_expeditions"]),
                    ),
                    value=(
                        "\n".join(exp_list)
                        if exp_list
                        else tx("genshin_cog.no_active_expeditions")
                    ),
                    inline=False,
                )

            elif game == "starrail":
                embed = discord.Embed(
                    title=tx("genshin_cog.honkai_star_rail_real_time_notes"),
                    color=discord.Color.from_rgb(75, 121, 161),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("genshin_cog.trailblaze_power"),
                    value=tx(
                        "genshin_cog.full_in",
                        v0=(notes["current_stamina"]),
                        v1=(notes["max_stamina"]),
                        v2=(self._format_seconds(notes["stamina_recovery"])),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.reserved_trailblaze_power"),
                    value=f" **{notes['reserve_stamina']} / 2400**",
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.daily_training"),
                    value=tx(
                        "genshin_cog.points",
                        v0=(notes["train_score"]),
                        v1=(notes["max_train_score"]),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.simulated_universe"),
                    value=tx(
                        "genshin_cog.points",
                        v0=(notes["rogue_score"]),
                        v1=(notes["max_rogue_score"]),
                    ),
                    inline=True,
                )

                exp_list = []
                completed_count = 0
                for exp in notes["expeditions"]:
                    remained = exp["remained"]
                    status_text = (
                        tx("genshin_cog.completed")
                        if remained <= 0
                        else tx(
                            "genshin_cog.remaining_6cdafb",
                            v0=(self._format_seconds(remained)),
                        )
                    )
                    exp_name = exp["name"] or tx("genshin_cog.assignment")
                    exp_list.append(f"• {exp_name} - {status_text}")
                    if remained <= 0:
                        completed_count += 1

                embed.add_field(
                    name=tx(
                        "genshin_cog.assignments",
                        v0=(completed_count),
                        v1=(notes["max_expeditions"]),
                    ),
                    value=(
                        "\n".join(exp_list)
                        if exp_list
                        else tx("genshin_cog.no_active_assignments")
                    ),
                    inline=False,
                )

            elif game == "zzz":
                embed = discord.Embed(
                    title=tx("genshin_cog.zenless_zone_zero_real_time_notes"),
                    color=discord.Color.from_rgb(247, 223, 30),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("genshin_cog.battery_charge"),
                    value=tx(
                        "genshin_cog.full_in",
                        v0=(notes["battery"]),
                        v1=(notes["max_battery"]),
                        v2=(self._format_seconds(notes["battery_recovery"])),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.daily_activity"),
                    value=f" **{notes['engagement']} / 400**",
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.daily_scratch_card"),
                    value=tx(
                        "genshin_cog.value",
                        v0=(
                            tx("genshin_cog.completed_e99b48")
                            if notes["scratch_completed"]
                            else tx("genshin_cog.not_completed")
                        ),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.video_store_status"),
                    value=f" **{notes['video_store']}**",
                    inline=False,
                )

            elif game == "honkai":
                embed = discord.Embed(
                    title=tx("genshin_cog.honkai_impact_3rd_real_time_notes"),
                    color=discord.Color.from_rgb(233, 30, 99),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name=tx("genshin_cog.stamina"),
                    value=tx(
                        "genshin_cog.full_in",
                        v0=(notes["current_stamina"]),
                        v1=(notes["max_stamina"]),
                        v2=(self._format_seconds(notes["stamina_recovery"])),
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.daily_missions"),
                    value=f" **{notes['train_score']}**",
                    inline=True,
                )

            embed.set_footer(
                text=tx(
                    "genshin_cog.uid_updated_at",
                    v0=(notes["uid"]),
                    v1=(datetime.now(TZ_OFFSET).strftime("%Y-%m-%d %H:%M:%S")),
                )
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                tx("genshin_cog.could_not_retrieve_real_time_notes", v0=(str(e))),
                ephemeral=True,
            )

    @mhy_group.command(
        name="redeem", description="Redeem a gift code for your linked game account"
    )
    @app_commands.describe(game="The game the code is for", code="The code to redeem")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="starrail"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
            app_commands.Choice(name="Honkai Impact 3rd", value="honkai"),
        ]
    )
    @localized("interaction")
    async def mhy_redeem(
        self, interaction: discord.Interaction, game: str, code: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.service.redeem_code(
                interaction.user.id, game, code.strip()
            )

            embed = discord.Embed(
                title=tx(
                    "genshin_cog.code_redemption_report",
                    v0=(self._get_game_display_name(game)),
                ),
                description=tx("genshin_cog.code", v0=(code)),
                color=discord.Color.from_rgb(155, 89, 182),
                timestamp=datetime.now(TZ_OFFSET),
            )

            for res in results:
                status_emoji = "" if res["success"] else ""
                embed.add_field(
                    name=f"{status_emoji} {res['nickname']} (`{res['uid']}`)",
                    value=res["message"],
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                tx("genshin_cog.redemption_failed", v0=(str(e))), ephemeral=True
            )

    @mhy_group.command(
        name="stats",
        description="Show your game stats (achievements, days active, chests)",
    )
    @app_commands.describe(game="The game")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="starrail"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
            app_commands.Choice(name="Honkai Impact 3rd", value="honkai"),
        ]
    )
    @localized("interaction")
    async def mhy_stats(self, interaction: discord.Interaction, game: str) -> None:
        await interaction.response.defer()

        try:
            stats = await self.service.get_stats(interaction.user.id, game)
            game_name = self._get_game_display_name(game)

            embed = discord.Embed(
                title=tx("genshin_cog.character_statistics", v0=(game_name)),
                color=discord.Color.from_rgb(142, 68, 173),
                timestamp=datetime.now(TZ_OFFSET),
            )

            embed.add_field(
                name=tx("genshin_cog.character_nickname"),
                value=stats["nickname"],
                inline=True,
            )
            embed.add_field(
                name=(
                    tx("genshin_cog.trailblaze_level")
                    if game == "starrail"
                    else (
                        tx("genshin_cog.inter_knot_level")
                        if game == "zzz"
                        else tx("genshin_cog.character_level")
                    )
                ),
                value=f"Lv.{stats['level']}",
                inline=True,
            )
            embed.add_field(
                name=tx("genshin_cog.active_days"),
                value=tx("audit_log.days", v0=(stats["days_active"])),
                inline=True,
            )

            if "achievements" in stats:
                embed.add_field(
                    name=tx("genshin_cog.achievements"),
                    value=f"{stats['achievements']}",
                    inline=True,
                )
            if "characters" in stats:
                embed.add_field(
                    name=tx("genshin_cog.characters_agents"),
                    value=f"{stats['characters']}",
                    inline=True,
                )
            if "chests_opened" in stats:
                embed.add_field(
                    name=tx("genshin_cog.chests_opened"),
                    value=f"{stats['chests_opened']}",
                    inline=True,
                )
            if "teapot_level" in stats and stats["teapot_level"] > 0:
                embed.add_field(
                    name=tx("genshin_cog.serenitea_pot_level"),
                    value=f"Lv.{stats['teapot_level']}",
                    inline=True,
                )
            if "bangboo_obtained" in stats:
                embed.add_field(
                    name=tx("genshin_cog.bangboo_obtained"),
                    value=f"{stats['bangboo_obtained']}",
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                tx("genshin_cog.could_not_retrieve_statistics", v0=(str(e))),
                ephemeral=True,
            )

    @mhy_group.command(name="abyss", description="Show your current Abyss stats")
    @app_commands.describe(game="The game")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="Genshin Impact", value="genshin"),
            app_commands.Choice(name="Honkai: Star Rail", value="starrail"),
            app_commands.Choice(name="Zenless Zone Zero", value="zzz"),
        ]
    )
    @localized("interaction")
    async def mhy_abyss(self, interaction: discord.Interaction, game: str) -> None:
        await interaction.response.defer()

        try:
            abyss = await self.service.get_abyss_stats(interaction.user.id, game)
            game_name = self._get_game_display_name(game)

            embed = discord.Embed(
                title=tx("genshin_cog.abyss_challenge_progress", v0=(game_name)),
                color=discord.Color.from_rgb(230, 126, 34),
                timestamp=datetime.now(TZ_OFFSET),
            )

            if game == "genshin":
                if not abyss["is_unlock"]:
                    embed.description = tx(
                        "genshin_cog.spiral_abyss_has_not_been_unlocked"
                    )
                else:
                    embed.add_field(
                        name=tx("genshin_cog.deepest_floor_reached"),
                        value=f"{abyss['max_floor']}",
                        inline=True,
                    )
                    embed.add_field(
                        name=tx("genshin_cog.total_stars"),
                        value=f"⭐ {abyss['total_stars']}",
                        inline=True,
                    )
                    embed.add_field(
                        name=tx("genshin_cog.battles_wins"),
                        value=tx(
                            "genshin_cog.battles_wins_29eccf",
                            v0=(abyss["total_battles"]),
                            v1=(abyss["total_wins"]),
                        ),
                        inline=True,
                    )

            elif game == "starrail":
                embed.add_field(
                    name=tx("genshin_cog.memory_of_chaos_moc"),
                    value=(
                        tx(
                            "genshin_cog.season_progress_stars",
                            v0=(abyss["moc_name"]),
                            v1=(abyss["moc_max"]),
                            v2=(abyss["moc_stars"]),
                        )
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.pure_fiction_pf"),
                    value=(
                        tx(
                            "genshin_cog.season_progress_stars",
                            v0=(abyss["pf_name"]),
                            v1=(abyss["pf_max"]),
                            v2=(abyss["pf_stars"]),
                        )
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.apocalyptic_shadow_as"),
                    value=(
                        tx(
                            "genshin_cog.season_progress_stars",
                            v0=(abyss["shadow_name"]),
                            v1=(abyss["shadow_max"]),
                            v2=(abyss["shadow_stars"]),
                        )
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=tx("genshin_cog.anomaly_arbitration_aa"),
                    value=(
                        tx(
                            "genshin_cog.season_progress_stars",
                            v0=(abyss["anomaly_name"]),
                            v1=(abyss["anomaly_max"]),
                            v2=(abyss["anomaly_stars"]),
                        )
                    ),
                    inline=True,
                )

            elif game == "zzz":
                embed.add_field(
                    name=tx("genshin_cog.shiyu_defense_progress"),
                    value=f"{abyss['shiyu_defense']}",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                tx("genshin_cog.could_not_retrieve_abyss_data", v0=(str(e))),
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(GenshinCog(bot))

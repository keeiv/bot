import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext import tasks
import genshin

from src.services.genshin_service import GenshinService

TZ_OFFSET = timezone(timedelta(hours=8))


class CookieBindModal(discord.ui.Modal):
    """彈出式輸入視窗：安全輸入 Cookie 各個欄位"""

    def __init__(self, service: "GenshinService", cog: "GenshinCog", region: str):
        title = (
            "安全綁定國服 (米游社) 帳號"
            if region == "cn"
            else "安全綁定國際服 (HoYoLAB) 帳號"
        )
        super().__init__(title=title)
        self.service = service
        self.cog = cog
        self.region = region

        # 根據區域設定不同的欄位
        if region == "cn":
            self.ltoken = discord.ui.TextInput(
                label="ltoken",
                style=discord.TextStyle.short,
                placeholder="請貼上 ltoken 的數值 (以 v2_CAIS 或 v2_CAES... 開頭的長字串)",
                required=True,
            )
            self.ltuid = discord.ui.TextInput(
                label="ltuid",
                style=discord.TextStyle.short,
                placeholder="請貼上 ltuid 的數值 (您的純數字米游社帳號 ID)",
                required=True,
            )
            self.cookie_token = discord.ui.TextInput(
                label="cookie_token (選填，兌換禮包碼與部分功能所需)",
                style=discord.TextStyle.short,
                placeholder="請貼上 cookie_token 的數值...",
                required=False,
            )
            self.add_item(self.ltoken)
            self.add_item(self.ltuid)
            self.add_item(self.cookie_token)
        else:
            self.ltoken_v2 = discord.ui.TextInput(
                label="ltoken_v2",
                style=discord.TextStyle.short,
                placeholder="請貼上 ltoken_v2 的數值 (以 v2_CAIS 或 v2_CAES... 開頭的長字串)",
                required=True,
            )
            self.ltuid_v2 = discord.ui.TextInput(
                label="ltuid_v2",
                style=discord.TextStyle.short,
                placeholder="請貼上 ltuid_v2 的數值 (您的純數字 HoYoLAB 帳號 ID)",
                required=True,
            )
            self.cookie_token_v2 = discord.ui.TextInput(
                label="cookie_token_v2 (選填，兌換禮包碼與部分功能所需)",
                style=discord.TextStyle.short,
                placeholder="請貼上 cookie_token_v2 的數值...",
                required=False,
            )
            self.add_item(self.ltoken_v2)
            self.add_item(self.ltuid_v2)
            self.add_item(self.cookie_token_v2)

    async def on_submit(self, interaction: discord.Interaction):
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
                "國服 (米游社)" if self.region == "cn" else "國際服 (HoYoLAB)"
            )
            embed = discord.Embed(
                title=f" {region_display} 帳號綁定成功",
                description="您的 Cookie 已被安全地加密儲存於伺服器中，並已連結以下帳號：",
                color=discord.Color.from_rgb(46, 204, 113),
            )

            for acc in accounts:
                game_name = self.cog._get_game_display_name(
                    self.service._map_game_biz_to_str(acc["game_biz"])
                )
                embed.add_field(
                    name=f" {game_name}",
                    value=f"**暱稱**: {acc['nickname']}\n**UID**: `{acc['uid']}`\n**等級**: Lv.{acc['level']}\n**伺服器**: {acc['server_name']}",
                    inline=True,
                )

            embed.set_footer(
                text="預設已為您開啟每日自動簽到，如有異動可使用 /mhy toggle_autosignin 調整。"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f" 綁定失敗：{str(e)}\n\n請確認您輸入的 `{field_names[0]}`、`{field_names[1]}` 是否正確且為{'米游社國服' if self.region == 'cn' else 'HoYoLAB 國際服'}的數值。\n"
                f"若有疑問，請輸入 `/mhy tutorial` 查看獲取教學。",
                ephemeral=True,
            )


class TutorialView(discord.ui.View):
    """用於顯示國服/國際服 Cookie 教學的按鈕選單"""

    def __init__(self, cog: "GenshinCog"):
        super().__init__(timeout=180)
        self.cog = cog

    def _create_tutorial_embed(self, region: str) -> discord.Embed:
        """建立教學 embed"""
        if region == "global":
            title = " 國際服 (HoYoLAB) Cookie 獲取教學"
            color = discord.Color.from_rgb(52, 152, 219)
            url = "https://www.hoyolab.com/"
            site_name = "HoYoLAB 官網"
        else:
            title = " 國服 (米游社) Cookie 獲取教學"
            color = discord.Color.from_rgb(46, 204, 113)
            url = "https://www.miyoushe.com/"
            site_name = "米游社官網"

        embed = discord.Embed(
            title=title,
            description=(
                "請跟隨以下步驟獲取您在 HoYoLAB 國際服的登入憑證："
                if region == "global"
                else "請跟隨以下步驟獲取您在米游社國服的登入憑證："
            ),
            color=color,
        )
        embed.add_field(
            name="1. 登入官網",
            value=f"請在電腦上使用 Chrome 或 Edge 等瀏覽器，開啟並登入 [{site_name}]({url})",
            inline=False,
        )
        embed.add_field(
            name="2. 開啟開發者工具",
            value="在官網頁面上按下鍵盤的 `F12` 鍵（或點選滑鼠右鍵，選擇「檢查」）。",
            inline=False,
        )
        embed.add_field(
            name="3. 進入 Cookies 存放區",
            value=(
                "在開發者工具頂部選單，點選「**Application (應用程式)**」頁籤（若沒看到，點擊 `>>` 展開選單）。\n"
                "接著在左側導覽列中展開「**Cookies**」，點擊 `https://www.hoyolab.com`"
                if region == "global"
                else "接著在左側導覽列中展開「**Cookies**」，點擊 `https://www.miyoushe.com`"
            ),
            inline=False,
        )

        if region == "global":
            field4_value = (
                "在中間出現的 Cookies 表格中，依序找到以下變數，並**複製其 Value (值)**：\n"
                "• **`ltoken_v2`**：通常以 `v2_CAIS` 或 `v2_CAES...` 開頭的超長代碼 (必要)\n"
                "• **`ltuid_v2`**：代表您帳號 ID 的純數字 (必要)\n"
                "• **`cookie_token_v2`**：用於兌換禮包代碼 (建議一併複製)"
            )
            field5_value = "回到 Discord，輸入 `/mhy bind` 並選擇 **國際服 (HoYoLAB)**，隨後在彈出的對話框中貼入剛才複製的各個欄位數值並提交即可！"
        else:
            field4_value = (
                "在中間出現的 Cookies 表格中，依序找到以下變數，並**複製其 Value (值)**：\n"
                "• **`ltoken`**：以 `v2_CAIS`、`v2_CAES` 或類似的長代碼 (必要)\n"
                "• **`ltuid`**：代表您帳號 ID 的純數字 (必要)\n"
                "• **`cookie_token`**：用於兌換禮包代碼 (建議一併複製)"
            )
            field5_value = "回到 Discord，輸入 `/mhy bind` 並選擇 **國服 (米游社)**，隨後在彈出的對話框中貼入剛才複製的各個欄位數值並提交即可！"

        embed.add_field(
            name="4. 複製各個欄位數值 (Value)", value=field4_value, inline=False
        )
        embed.add_field(
            name="5. 在 Discord 中完成綁定", value=field5_value, inline=False
        )
        embed.set_footer(
            text="️ 提示：Cookie 相當於您的登入密碼，請勿向任何第三方透露或截圖發送！"
        )
        return embed

    @discord.ui.button(
        label=" 國際服 (HoYoLAB) 教學", style=discord.ButtonStyle.primary
    )
    async def global_tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = self._create_tutorial_embed("global")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🇨🇳 國服 (米游社) 教學", style=discord.ButtonStyle.success)
    async def cn_tutorial(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = self._create_tutorial_embed("cn")
        await interaction.response.edit_message(embed=embed, view=self)


class GenshinCog(commands.Cog):
    """HoYoLAB / 米游社 相關自動化與查詢功能"""

    mhy_group = app_commands.Group(name="mhy", description="HoYoLAB / 米游社 功能組")

    def __init__(self, bot: commands.Bot):
        """初始化 GenshinCog"""
        self.bot = bot
        self.service = GenshinService()
        self.log_file = "data/storage/genshin_signin_log.json"

        # 啟動自動簽到背景任務
        self._auto_signin_loop.start()
        # 異步載入角色資料庫快取
        asyncio.create_task(self._init_character_names())

    def cog_unload(self):
        """卸載 Cog 時取消背景任務"""
        self._auto_signin_loop.cancel()

    async def _init_character_names(self):
        """初始化角色資料庫快取"""
        try:
            print("[Genshin Cog] 正在下載與更新角色資料庫快取...")
            await genshin.utility.update_characters_any(
                langs=["zh-cn", "zh-tw", "en-us"]
            )
            print("[Genshin Cog] 角色資料庫快取更新完成！")
        except Exception as e:
            print(f"[Genshin Cog] 角色資料庫快取更新失敗: {e}")

    def _load_last_run_date(self) -> str:
        """載入上次執行簽到的日期"""
        if not os.path.exists(self.log_file):
            return ""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_run_date", "")
        except Exception:
            return ""

    def _save_last_run_date(self, date_str: str) -> None:
        """儲存上次執行簽到的日期"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump({"last_run_date": date_str}, f)
        except Exception as e:
            print(f"[Genshin Cog] Failed to save signin log: {e}")

    def _get_game_display_name(self, game_str: str) -> str:
        """取得遊戲顯示名稱"""
        mapping = {
            "genshin": "原神",
            "starrail": "崩壞：星穹鐵道",
            "zzz": "絕區零",
            "honkai": "崩壞3rd",
            "tot": "未定事件簿",
        }
        return mapping.get(game_str.lower(), "HoYoLAB")

    def _format_seconds(self, seconds: int) -> str:
        """格式化秒數為可讀時間"""
        if seconds <= 0:
            return "已滿"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"約 {hours} 小時 {minutes} 分鐘"
        return f"約 {minutes} 分鐘"

    # ─────────────── 背景簽到任務 ───────────────

    @tasks.loop(minutes=30)
    async def _auto_signin_loop(self):
        now = datetime.now(TZ_OFFSET)
        # 設定在清晨 8:00 後自動進行簽到
        # 如果今日尚未執行，且目前時間已過 8:00 AM，則開始執行
        if now.hour >= 8:
            today_str = now.strftime("%Y-%m-%d")
            last_run = self._load_last_run_date()
            if last_run != today_str:
                self._save_last_run_date(today_str)
                print(f"[Genshin Cog] 啟動 {today_str} 自動每日簽到...")
                results = await self.service.run_global_auto_sign_in()

                # 私訊通知使用者
                for user_id, user_results in results.items():
                    try:
                        user = self.bot.get_user(user_id)
                        if user is None:
                            user = await self.bot.fetch_user(user_id)
                        if user:
                            embed = discord.Embed(
                                title=" HoYoLAB / 米游社 每日自動簽到報告",
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
                                text="可使用 /mhy toggle_autosignin 關閉此通知"
                            )
                            await user.send(embed=embed)
                    except Exception as e:
                        print(f"[Genshin Cog] 無法發送通知給使用者 {user_id}: {e}")

    @_auto_signin_loop.before_loop
    async def _before_auto_signin(self):
        try:
            await self.bot.wait_until_ready()
        except RuntimeError:
            self._auto_signin_loop.cancel()

    # ─────────────── 斜線指令 ───────────────

    @mhy_group.command(
        name="bind", description="安全綁定你的 HoYoLAB / 米游社 Cookie (會開啟視窗輸入)"
    )
    @app_commands.describe(
        region="選擇你的伺服器區域：國際服 (HoYoLAB) 或 國服 (米游社)"
    )
    @app_commands.choices(
        region=[
            app_commands.Choice(name="國際服 (HoYoLAB)", value="global"),
            app_commands.Choice(name="國服 (米游社)", value="cn"),
        ]
    )
    async def mhy_bind(self, interaction: discord.Interaction, region: str):
        modal = CookieBindModal(self.service, self, region)
        await interaction.response.send_modal(modal)

    @mhy_group.command(
        name="tutorial", description="獲取米游社 / HoYoLAB Cookie 的教學指引"
    )
    async def mhy_tutorial(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title=" 米游社 / HoYoLAB Cookie 獲取指引",
            description=(
                "為了能自動簽到與查詢便箋，本機器人需要安全綁定您的 Cookie。\n\n"
                "請點選下方對應區域的按鈕，即可查閱國服（米游社）或國際服（HoYoLAB）的詳細圖文教學："
            ),
            color=discord.Color.from_rgb(155, 89, 182),
            timestamp=datetime.now(TZ_OFFSET),
        )

        embed.set_footer(text="請注意：Cookie 僅會被 AES 加密存在本機，絕不會外洩。")
        view = TutorialView(self)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @mhy_group.command(
        name="unbind", description="解除綁定你的 HoYoLAB / 米游社 帳號並刪除 Cookie"
    )
    async def mhy_unbind(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        success = self.service.unbind_account(interaction.user.id)
        if success:
            await interaction.followup.send(
                " 已解除您的帳號連結，並已從本機器人伺服器中徹底清除您的加密 Cookie。",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                " 您尚未綁定任何 HoYoLAB/米游社 帳號。", ephemeral=True
            )

    @mhy_group.command(name="status", description="查看當前帳號綁定狀態與設定")
    async def mhy_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_data = self.service.get_bound_user(interaction.user.id)
        if not user_data:
            await interaction.followup.send(
                " 您尚未綁定 HoYoLAB/米游社 帳號，請先使用 `/mhy bind` 指令進行綁定。",
                ephemeral=True,
            )
            return

        region_display = (
            "國服 (米游社)" if user_data.get("region") == "cn" else "國際服 (HoYoLAB)"
        )
        auto_signin_display = (
            " 已開啟" if user_data.get("auto_sign_in", True) else " 已關閉"
        )

        embed = discord.Embed(
            title=" HoYoLAB / 米游社 綁定狀態",
            color=discord.Color.from_rgb(52, 152, 219),
            timestamp=datetime.now(TZ_OFFSET),
        )
        embed.add_field(name="帳號區域", value=region_display, inline=True)
        embed.add_field(name="自動簽到狀態", value=auto_signin_display, inline=True)

        accounts = user_data.get("game_accounts", [])
        if accounts:
            accounts_lines = []
            for acc in accounts:
                game_name = self._get_game_display_name(
                    self.service._map_game_biz_to_str(acc["game_biz"])
                )
                accounts_lines.append(
                    f"• **{game_name}** - {acc['nickname']} (UID: `{acc['uid']}`) [Lv.{acc['level']} - {acc['server_name']}]"
                )
            embed.add_field(
                name="連結的遊戲帳號", value="\n".join(accounts_lines), inline=False
            )
        else:
            embed.add_field(
                name="連結的遊戲帳號", value="無連結的遊戲角色", inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @mhy_group.command(
        name="toggle_autosignin", description="開啟或關閉每日自動簽到功能"
    )
    @app_commands.describe(enable="是否開啟每日自動簽到")
    async def mhy_toggle_autosignin(
        self, interaction: discord.Interaction, enable: bool
    ):
        await interaction.response.defer(ephemeral=True)

        success = self.service.toggle_auto_sign_in(interaction.user.id, enable)
        if success:
            status = "開啟" if enable else "關閉"
            await interaction.followup.send(
                f" 已成功將您的每日自動簽到功能調整為：**{status}**。", ephemeral=True
            )
        else:
            await interaction.followup.send(
                " 設定失敗，請確認您是否已經綁定帳號。", ephemeral=True
            )

    @mhy_group.command(name="checkin", description="手動觸發一次今日的所有遊戲簽到")
    async def mhy_checkin(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.service.claim_daily_signin_for_user(
                interaction.user.id
            )

            embed = discord.Embed(
                title=" 每日簽到結果",
                color=discord.Color.from_rgb(46, 204, 113),
                timestamp=datetime.now(TZ_OFFSET),
            )

            if not results:
                embed.description = "未在您的帳號中找到支援簽到的遊戲角色。"
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
            await interaction.followup.send(f" 簽到失敗：{str(e)}", ephemeral=True)

    @mhy_group.command(
        name="notes", description="查詢特定遊戲的實時便箋 (如原粹樹脂、開拓力、電量等)"
    )
    @app_commands.describe(game="選擇要查詢的遊戲")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="原神 (Genshin Impact)", value="genshin"),
            app_commands.Choice(
                name="崩壞：星穹鐵道 (Honkai: Star Rail)", value="starrail"
            ),
            app_commands.Choice(name="絕區零 (Zenless Zone Zero)", value="zzz"),
            app_commands.Choice(name="崩壞3rd (Honkai Impact 3rd)", value="honkai"),
        ]
    )
    async def mhy_notes(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer()

        try:
            notes = await self.service.get_notes(interaction.user.id, game)

            if game == "genshin":
                embed = discord.Embed(
                    title=" 原神 - 實時便箋",
                    color=discord.Color.from_rgb(62, 155, 150),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="原粹樹脂",
                    value=f" **{notes['current_resin']} / {notes['max_resin']}**\n(恢復滿需: {self._format_seconds(notes['resin_recovery'])})",
                    inline=True,
                )
                embed.add_field(
                    name="洞天寶錢",
                    value=f" **{notes['current_currency']} / {notes['max_currency']}**",
                    inline=True,
                )
                embed.add_field(
                    name="每日委託",
                    value=f" **{notes['commissions']} / {notes['max_commissions']}**\n(額外獎勵: {'已領取' if notes['commission_reward_claimed'] else '未領取'})",
                    inline=True,
                )
                embed.add_field(
                    name="週本樹脂減半",
                    value=f"️ 剩餘 **{notes['weekly_boss_discounts']} / {notes['max_weekly_boss_discounts']}** 次",
                    inline=True,
                )
                embed.add_field(
                    name="參量質變儀",
                    value=f"️ **{notes['transformer_recovery']}**",
                    inline=True,
                )

                exp_list = []
                completed_count = 0
                for exp in notes["expeditions"]:
                    remained = exp["remained"]
                    status_text = (
                        " 已完成"
                        if remained <= 0
                        else f"⏳ 剩餘 {self._format_seconds(remained)}"
                    )
                    exp_list.append(f"• 探索派遣 - {status_text}")
                    if remained <= 0:
                        completed_count += 1

                embed.add_field(
                    name=f"探索派遣 ({completed_count} / {notes['max_expeditions']})",
                    value="\n".join(exp_list) if exp_list else "無進行中的探索派遣",
                    inline=False,
                )

            elif game == "starrail":
                embed = discord.Embed(
                    title=" 崩壞：星穹鐵道 - 實時便箋",
                    color=discord.Color.from_rgb(75, 121, 161),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="開拓力",
                    value=f" **{notes['current_stamina']} / {notes['max_stamina']}**\n(恢復滿需: {self._format_seconds(notes['stamina_recovery'])})",
                    inline=True,
                )
                embed.add_field(
                    name="後備開拓力",
                    value=f" **{notes['reserve_stamina']} / 2400**",
                    inline=True,
                )
                embed.add_field(
                    name="每日實訓",
                    value=f" **{notes['train_score']} / {notes['max_train_score']}** 分",
                    inline=True,
                )
                embed.add_field(
                    name="模擬宇宙",
                    value=f" **{notes['rogue_score']} / {notes['max_rogue_score']}** 分",
                    inline=True,
                )

                exp_list = []
                completed_count = 0
                for exp in notes["expeditions"]:
                    remained = exp["remained"]
                    status_text = (
                        " 已完成"
                        if remained <= 0
                        else f"⏳ 剩餘 {self._format_seconds(remained)}"
                    )
                    exp_name = exp["name"] or "委託"
                    exp_list.append(f"• {exp_name} - {status_text}")
                    if remained <= 0:
                        completed_count += 1

                embed.add_field(
                    name=f"派遣委託 ({completed_count} / {notes['max_expeditions']})",
                    value="\n".join(exp_list) if exp_list else "無進行中的派遣委託",
                    inline=False,
                )

            elif game == "zzz":
                embed = discord.Embed(
                    title=" 絕區零 - 實時便箋",
                    color=discord.Color.from_rgb(247, 223, 30),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="電量",
                    value=f" **{notes['battery']} / {notes['max_battery']}**\n(恢復滿需: {self._format_seconds(notes['battery_recovery'])})",
                    inline=True,
                )
                embed.add_field(
                    name="每日活躍",
                    value=f" **{notes['engagement']} / 400**",
                    inline=True,
                )
                embed.add_field(
                    name="今日刮刮卡",
                    value=f"️ **{'已完成' if notes['scratch_completed'] else '未完成'}**",
                    inline=True,
                )
                embed.add_field(
                    name="錄影帶店狀態",
                    value=f" **{notes['video_store']}**",
                    inline=False,
                )

            elif game == "honkai":
                embed = discord.Embed(
                    title="️ 崩壞3rd - 實時便箋",
                    color=discord.Color.from_rgb(233, 30, 99),
                    timestamp=datetime.now(TZ_OFFSET),
                )
                embed.add_field(
                    name="體力",
                    value=f" **{notes['current_stamina']} / {notes['max_stamina']}**\n(恢復滿需: {self._format_seconds(notes['stamina_recovery'])})",
                    inline=True,
                )
                embed.add_field(
                    name="每日使命", value=f" **{notes['train_score']}**", inline=True
                )

            embed.set_footer(
                text=f"UID: {notes['uid']} | 數據更新時間: {datetime.now(TZ_OFFSET).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f" 查詢實時便箋時發生錯誤：{str(e)}", ephemeral=True
            )

    @mhy_group.command(name="redeem", description="為連結的遊戲帳號兌換禮包碼")
    @app_commands.describe(game="選擇禮包碼所屬遊戲", code="輸入兌換代碼 (Promo Code)")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="原神 (Genshin Impact)", value="genshin"),
            app_commands.Choice(
                name="崩壞：星穹鐵道 (Honkai: Star Rail)", value="starrail"
            ),
            app_commands.Choice(name="絕區零 (Zenless Zone Zero)", value="zzz"),
            app_commands.Choice(name="崩壞3rd (Honkai Impact 3rd)", value="honkai"),
        ]
    )
    async def mhy_redeem(self, interaction: discord.Interaction, game: str, code: str):
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.service.redeem_code(
                interaction.user.id, game, code.strip()
            )

            embed = discord.Embed(
                title=f" {self._get_game_display_name(game)} 兌換碼兌換報告",
                description=f"兌換代碼: `{code}`",
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
            await interaction.followup.send(f" 兌換失敗：{str(e)}", ephemeral=True)

    @mhy_group.command(
        name="stats",
        description="展示綁定角色基本統計數據（如成就數、活躍天數、箱子數）",
    )
    @app_commands.describe(game="選擇要查詢的遊戲")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="原神 (Genshin Impact)", value="genshin"),
            app_commands.Choice(
                name="崩壞：星穹鐵道 (Honkai: Star Rail)", value="starrail"
            ),
            app_commands.Choice(name="絕區零 (Zenless Zone Zero)", value="zzz"),
            app_commands.Choice(name="崩壞3rd (Honkai Impact 3rd)", value="honkai"),
        ]
    )
    async def mhy_stats(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer()

        try:
            stats = await self.service.get_stats(interaction.user.id, game)
            game_name = self._get_game_display_name(game)

            embed = discord.Embed(
                title=f" {game_name} 角色數據統計",
                color=discord.Color.from_rgb(142, 68, 173),
                timestamp=datetime.now(TZ_OFFSET),
            )

            embed.add_field(name="角色暱稱", value=stats["nickname"], inline=True)
            embed.add_field(
                name=(
                    "開拓等級"
                    if game == "starrail"
                    else "繩網等級" if game == "zzz" else "角色等級"
                ),
                value=f"Lv.{stats['level']}",
                inline=True,
            )
            embed.add_field(
                name="活躍天數", value=f"{stats['days_active']} 天", inline=True
            )

            if "achievements" in stats:
                embed.add_field(
                    name="達成成就", value=f"{stats['achievements']}", inline=True
                )
            if "characters" in stats:
                embed.add_field(
                    name="角色/代理人數量", value=f"{stats['characters']}", inline=True
                )
            if "chests_opened" in stats:
                embed.add_field(
                    name="開啟寶箱數", value=f"{stats['chests_opened']}", inline=True
                )
            if "teapot_level" in stats and stats["teapot_level"] > 0:
                embed.add_field(
                    name="塵歌壺等級", value=f"Lv.{stats['teapot_level']}", inline=True
                )
            if "bangboo_obtained" in stats:
                embed.add_field(
                    name="獲得邦布數", value=f"{stats['bangboo_obtained']}", inline=True
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f" 獲取統計數據時發生錯誤：{str(e)}", ephemeral=True
            )

    @mhy_group.command(name="abyss", description="展示綁定角色深淵統計數據 (當期)")
    @app_commands.describe(game="選擇要查詢的遊戲")
    @app_commands.choices(
        game=[
            app_commands.Choice(name="原神 (Genshin Impact)", value="genshin"),
            app_commands.Choice(
                name="崩壞：星穹鐵道 (Honkai: Star Rail)", value="starrail"
            ),
            app_commands.Choice(name="絕區零 (Zenless Zone Zero)", value="zzz"),
        ]
    )
    async def mhy_abyss(self, interaction: discord.Interaction, game: str):
        await interaction.response.defer()

        try:
            abyss = await self.service.get_abyss_stats(interaction.user.id, game)
            game_name = self._get_game_display_name(game)

            embed = discord.Embed(
                title=f" {game_name} 深淵挑戰進度",
                color=discord.Color.from_rgb(230, 126, 34),
                timestamp=datetime.now(TZ_OFFSET),
            )

            if game == "genshin":
                if not abyss["is_unlock"]:
                    embed.description = "此帳號當期尚未解鎖或挑戰深境螺旋。"
                else:
                    embed.add_field(
                        name="最深抵達層數", value=f"{abyss['max_floor']}", inline=True
                    )
                    embed.add_field(
                        name="獲得總星數",
                        value=f"⭐ {abyss['total_stars']}",
                        inline=True,
                    )
                    embed.add_field(
                        name="戰鬥/勝利次數",
                        value=f"{abyss['total_battles']} 次 / {abyss['total_wins']} 勝",
                        inline=True,
                    )

            elif game == "starrail":
                embed.add_field(
                    name="️ 混沌回憶 (MoC)",
                    value=(
                        f"**當前賽季**: {abyss['moc_name']}\n"
                        f"**最深進度**: {abyss['moc_max']}\n"
                        f"**獲得星數**: ⭐ {abyss['moc_stars']}"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name=" 虛構敘事 (PF)",
                    value=(
                        f"**當前賽季**: {abyss['pf_name']}\n"
                        f"**最深進度**: {abyss['pf_max']}\n"
                        f"**獲得星數**: ⭐ {abyss['pf_stars']}"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="️ 末日幻影 (AS)",
                    value=(
                        f"**當前賽季**: {abyss['shadow_name']}\n"
                        f"**最深進度**: {abyss['shadow_max']}\n"
                        f"**獲得星數**: ⭐ {abyss['shadow_stars']}"
                    ),
                    inline=True,
                )
                embed.add_field(
                    name="️ 異相仲裁 (AA)",
                    value=(
                        f"**當前賽季**: {abyss['anomaly_name']}\n"
                        f"**最深進度**: {abyss['anomaly_max']}\n"
                        f"**獲得星數**: ⭐ {abyss['anomaly_stars']}"
                    ),
                    inline=True,
                )

            elif game == "zzz":
                embed.add_field(
                    name="式輿防衛戰進度",
                    value=f"{abyss['shiyu_defense']}",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f" 獲取深淵數據時發生錯誤：{str(e)}", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(GenshinCog(bot))

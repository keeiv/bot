"""English and Traditional Chinese copy for genshin_cog."""

MESSAGES: dict[str, dict[str, str]] = {
    "genshin_cog.about_minutes": {"en": "About {v0} minutes", "zh": "約 {v0} 分鐘"},
    "genshin_cog.link_a_miyoushe_china_account": {
        "en": "Link a Miyoushe (China) account",
        "zh": "安全綁定國服 (米游社) 帳號",
    },
    "genshin_cog.link_a_hoyolab_global_account": {
        "en": "Link a HoYoLAB (global) account",
        "zh": "安全綁定國際服 (HoYoLAB) 帳號",
    },
    "genshin_cog.hoyolab_global_cookie_guide": {
        "en": " HoYoLAB (global) cookie guide",
        "zh": " 國際服 (HoYoLAB) Cookie 獲取教學",
    },
    "genshin_cog.hoyolab_website": {"en": "HoYoLAB website", "zh": "HoYoLAB 官網"},
    "genshin_cog.miyoushe_china_cookie_guide": {
        "en": " Miyoushe (China) cookie guide",
        "zh": " 國服 (米游社) Cookie 獲取教學",
    },
    "genshin_cog.miyoushe_website": {"en": "Miyoushe website", "zh": "米游社官網"},
    "genshin_cog.in_the_cookies_table_find_these": {
        "en": "In the Cookies table, find these entries and **copy their Value**:\n• **`ltoken_v2`**: a long token usually starting with `v2_CAIS` or `v2_CAES…` (required)\n• **`ltuid_v2`**: the numeric account ID (required)\n• **`cookie_token_v2`**: used to redeem gift codes (recommended)",
        "zh": "在中間出現的 Cookies 表格中，依序找到以下變數，並**複製其 Value (值)**：\n• **`ltoken_v2`**：通常以 `v2_CAIS` 或 `v2_CAES...` 開頭的超長代碼 (必要)\n• **`ltuid_v2`**：代表您帳號 ID 的純數字 (必要)\n• **`cookie_token_v2`**：用於兌換禮包代碼 (建議一併複製)",
    },
    "genshin_cog.in_discord_run_mhy_bind_select": {
        "en": "In Discord, run `/mhy bind`, select **Global (HoYoLAB)**, paste the copied values into the form and submit.",
        "zh": "回到 Discord，輸入 `/mhy bind` 並選擇 **國際服 (HoYoLAB)**，隨後在彈出的對話框中貼入剛才複製的各個欄位數值並提交即可！",
    },
    "genshin_cog.in_the_cookies_table_find_these_e39310": {
        "en": "In the Cookies table, find these entries and **copy their Value**:\n• **`ltoken`**: a long token starting with `v2_CAIS`, `v2_CAES` or similar (required)\n• **`ltuid`**: the numeric account ID (required)\n• **`cookie_token`**: used to redeem gift codes (recommended)",
        "zh": "在中間出現的 Cookies 表格中，依序找到以下變數，並**複製其 Value (值)**：\n• **`ltoken`**：以 `v2_CAIS`、`v2_CAES` 或類似的長代碼 (必要)\n• **`ltuid`**：代表您帳號 ID 的純數字 (必要)\n• **`cookie_token`**：用於兌換禮包代碼 (建議一併複製)",
    },
    "genshin_cog.in_discord_run_mhy_bind_select_2a8fb7": {
        "en": "In Discord, run `/mhy bind`, select **China (Miyoushe)**, paste the copied values into the form and submit.",
        "zh": "回到 Discord，輸入 `/mhy bind` 並選擇 **國服 (米游社)**，隨後在彈出的對話框中貼入剛才複製的各個欄位數值並提交即可！",
    },
    "genshin_cog.global_hoyolab_guide": {
        "en": " Global (HoYoLAB) guide",
        "zh": " 國際服 (HoYoLAB) 教學",
    },
    "genshin_cog.china_miyoushe_guide": {
        "en": "🇨🇳 China (Miyoushe) guide",
        "zh": "🇨🇳 國服 (米游社) 教學",
    },
    "genshin_cog.genshin_impact": {"en": "Genshin Impact", "zh": "原神"},
    "genshin_cog.honkai_star_rail": {"en": "Honkai: Star Rail", "zh": "崩壞：星穹鐵道"},
    "genshin_cog.zenless_zone_zero": {"en": "Zenless Zone Zero", "zh": "絕區零"},
    "genshin_cog.honkai_impact_3rd": {"en": "Honkai Impact 3rd", "zh": "崩壞3rd"},
    "genshin_cog.tears_of_themis": {"en": "Tears of Themis", "zh": "未定事件簿"},
    "genshin_cog.full": {"en": "Full", "zh": "已滿"},
    "genshin_cog.about_hours_minutes": {
        "en": "About {v0} hours, {v1} minutes",
        "zh": "約 {v0} 小時 {v1} 分鐘",
    },
    "genshin_cog.china_miyoushe": {"en": "China (Miyoushe)", "zh": "國服 (米游社)"},
    "genshin_cog.global_hoyolab": {"en": "Global (HoYoLAB)", "zh": "國際服 (HoYoLAB)"},
    "genshin_cog.enabled": {"en": " Enabled", "zh": " 已開啟"},
    "genshin_cog.disabled": {"en": " Disabled", "zh": " 已關閉"},
    "genshin_cog.1_sign_in_to_the_website": {
        "en": "1. Sign in to the website",
        "zh": "1. 登入官網",
    },
    "genshin_cog.open_in_a_desktop_browser_such": {
        "en": "Open [{v0}]({v1}) in a desktop browser such as Chrome or Edge and sign in.",
        "zh": "請在電腦上使用 Chrome 或 Edge 等瀏覽器，開啟並登入 [{v0}]({v1})",
    },
    "genshin_cog.2_open_developer_tools": {
        "en": "2. Open developer tools",
        "zh": "2. 開啟開發者工具",
    },
    "genshin_cog.press_f12_on_the_website_or": {
        "en": "Press `F12` on the website, or right-click and select Inspect.",
        "zh": "在官網頁面上按下鍵盤的 `F12` 鍵（或點選滑鼠右鍵，選擇「檢查」）。",
    },
    "genshin_cog.3_open_cookie_storage": {
        "en": "3. Open cookie storage",
        "zh": "3. 進入 Cookies 存放區",
    },
    "genshin_cog.4_copy_each_value": {
        "en": "4. Copy each Value",
        "zh": "4. 複製各個欄位數值 (Value)",
    },
    "genshin_cog.5_complete_linking_in_discord": {
        "en": "5. Complete linking in Discord",
        "zh": "5. 在 Discord 中完成綁定",
    },
    "genshin_cog.cookies_are_login_credentials_do_not": {
        "en": "️ Cookies are login credentials. Do not share them or send screenshots containing them.",
        "zh": "️ 提示：Cookie 相當於您的登入密碼，請勿向任何第三方透露或截圖發送！",
    },
    "genshin_cog.miyoushe_hoyolab_cookie_guide": {
        "en": " Miyoushe / HoYoLAB cookie guide",
        "zh": " 米游社 / HoYoLAB Cookie 獲取指引",
    },
    "genshin_cog.account_cookies_are_required_for_automatic": {
        "en": "Account cookies are required for automatic check-in and real-time notes.\n\nChoose the account region below to view the linking instructions.",
        "zh": "為了能自動簽到與查詢便箋，本機器人需要安全綁定您的 Cookie。\n\n請點選下方對應區域的按鈕，即可查閱國服（米游社）或國際服（HoYoLAB）的詳細圖文教學：",
    },
    "genshin_cog.cookies_are_encrypted_before_storage_keep": {
        "en": "Cookies are encrypted before storage. Keep account credentials private.",
        "zh": "Cookie 會加密後儲存。請勿公開帳號憑證。",
    },
    "genshin_cog.hoyolab_miyoushe_linking_status": {
        "en": " HoYoLAB / Miyoushe linking status",
        "zh": " HoYoLAB / 米游社 綁定狀態",
    },
    "genshin_cog.account_region": {"en": "Account region", "zh": "帳號區域"},
    "genshin_cog.automatic_check_in": {
        "en": "Automatic check-in",
        "zh": "自動簽到狀態",
    },
    "genshin_cog.no_characters_supporting_check_in_were": {
        "en": "No characters supporting check-in were found on this account.",
        "zh": "未在您的帳號中找到支援簽到的遊戲角色。",
    },
    "genshin_cog.paste_the_ltoken_value_a_long": {
        "en": "Paste the ltoken value (a long token starting with v2_CAIS or v2_CAES…)",
        "zh": "請貼上 ltoken 的數值 (以 v2_CAIS 或 v2_CAES... 開頭的長字串)",
    },
    "genshin_cog.paste_the_ltuid_value_the_numeric": {
        "en": "Paste the ltuid value (the numeric Miyoushe account ID)",
        "zh": "請貼上 ltuid 的數值 (您的純數字米游社帳號 ID)",
    },
    "genshin_cog.cookie_token_optional_needed_for_gift": {
        "en": "cookie_token (optional; needed for gift codes)",
        "zh": "cookie_token (選填，兌換禮包碼與部分功能所需)",
    },
    "genshin_cog.paste_the_cookie_token_value": {
        "en": "Paste the cookie_token value…",
        "zh": "請貼上 cookie_token 的數值...",
    },
    "genshin_cog.paste_the_ltoken_v2_value_a": {
        "en": "Paste the ltoken_v2 value (a long token starting with v2_CAIS or v2_CAES…)",
        "zh": "請貼上 ltoken_v2 的數值 (以 v2_CAIS 或 v2_CAES... 開頭的長字串)",
    },
    "genshin_cog.paste_the_ltuid_v2_value_the": {
        "en": "Paste the ltuid_v2 value (the numeric HoYoLAB account ID)",
        "zh": "請貼上 ltuid_v2 的數值 (您的純數字 HoYoLAB 帳號 ID)",
    },
    "genshin_cog.cookie_token_v2_optional_needed_for": {
        "en": "cookie_token_v2 (optional; needed for gift codes)",
        "zh": "cookie_token_v2 (選填，兌換禮包碼與部分功能所需)",
    },
    "genshin_cog.paste_the_cookie_token_v2_value": {
        "en": "Paste the cookie_token_v2 value…",
        "zh": "請貼上 cookie_token_v2 的數值...",
    },
    "genshin_cog.account_linked": {
        "en": " {v0} account linked",
        "zh": " {v0} 帳號綁定成功",
    },
    "genshin_cog.account_cookies_have_been_encrypted_and": {
        "en": "Account cookies have been encrypted and stored. Linked accounts:",
        "zh": "您的 Cookie 已被安全地加密儲存於伺服器中，並已連結以下帳號：",
    },
    "genshin_cog.automatic_daily_check_in_is_enabled": {
        "en": "Automatic daily check-in is enabled. Use /mhy toggle_autosignin to change this setting.",
        "zh": "預設已為您開啟每日自動簽到，如有異動可使用 /mhy toggle_autosignin 調整。",
    },
    "genshin_cog.follow_these_steps_to_obtain_hoyolab": {
        "en": "Follow these steps to obtain HoYoLAB global login credentials:",
        "zh": "請跟隨以下步驟獲取您在 HoYoLAB 國際服的登入憑證：",
    },
    "genshin_cog.follow_these_steps_to_obtain_miyoushe": {
        "en": "Follow these steps to obtain Miyoushe China login credentials:",
        "zh": "請跟隨以下步驟獲取您在米游社國服的登入憑證：",
    },
    "genshin_cog.in_developer_tools_open_the_application": {
        "en": "In developer tools, open the **Application** tab (use `>>` if it is hidden).\nExpand **Cookies** on the left and select `https://www.hoyolab.com`.",
        "zh": "在開發者工具頂部選單，點選「**Application (應用程式)**」頁籤（若沒看到，點擊 `>>` 展開選單）。\n接著在左側導覽列中展開「**Cookies**」，點擊 `https://www.hoyolab.com`",
    },
    "genshin_cog.expand_cookies_on_the_left_and": {
        "en": "Expand **Cookies** on the left and select `https://www.miyoushe.com`.",
        "zh": "接著在左側導覽列中展開「**Cookies**」，點擊 `https://www.miyoushe.com`",
    },
    "genshin_cog.account_unlinked_the_stored_encrypted_cookies": {
        "en": " Account unlinked. The stored encrypted cookies have been deleted.",
        "zh": " 已解除您的帳號連結，並已從本機器人伺服器中徹底清除您的加密 Cookie。",
    },
    "genshin_cog.no_hoyolab_miyoushe_account_is_linked": {
        "en": " No HoYoLAB / Miyoushe account is linked.",
        "zh": " 您尚未綁定任何 HoYoLAB/米游社 帳號。",
    },
    "genshin_cog.no_hoyolab_miyoushe_account_is_linked_3c194c": {
        "en": " No HoYoLAB / Miyoushe account is linked. Run `/mhy bind` first.",
        "zh": " 您尚未綁定 HoYoLAB/米游社 帳號，請先使用 `/mhy bind` 指令進行綁定。",
    },
    "genshin_cog.linked_game_accounts": {
        "en": "Linked game accounts",
        "zh": "連結的遊戲帳號",
    },
    "genshin_cog.no_linked_characters": {
        "en": "No linked characters",
        "zh": "無連結的遊戲角色",
    },
    "genshin_cog.automatic_daily_check_in": {
        "en": " Automatic daily check-in: **{v0}**.",
        "zh": " 已成功將您的每日自動簽到功能調整為：**{v0}**。",
    },
    "genshin_cog.settings_could_not_be_saved_check": {
        "en": " Settings could not be saved. Check that an account is linked.",
        "zh": " 設定失敗，請確認您是否已經綁定帳號。",
    },
    "genshin_cog.daily_check_in_results": {
        "en": " Daily check-in results",
        "zh": " 每日簽到結果",
    },
    "genshin_cog.uid_updated_at": {
        "en": "UID: {v0} | Updated at: {v1}",
        "zh": "UID: {v0} | 數據更新時間: {v1}",
    },
    "genshin_cog.code_redemption_report": {
        "en": " {v0} code redemption report",
        "zh": " {v0} 兌換碼兌換報告",
    },
    "genshin_cog.code": {"en": "Code: `{v0}`", "zh": "兌換代碼: `{v0}`"},
    "genshin_cog.character_statistics": {
        "en": " {v0} character statistics",
        "zh": " {v0} 角色數據統計",
    },
    "genshin_cog.character_nickname": {"en": "Character nickname", "zh": "角色暱稱"},
    "genshin_cog.active_days": {"en": "Active days", "zh": "活躍天數"},
    "genshin_cog.abyss_challenge_progress": {
        "en": " {v0} abyss challenge progress",
        "zh": " {v0} 深淵挑戰進度",
    },
    "genshin_cog.spiral_abyss_has_not_been_unlocked": {
        "en": "Spiral Abyss has not been unlocked or attempted this season.",
        "zh": "此帳號當期尚未解鎖或挑戰深境螺旋。",
    },
    "genshin_cog.nickname_uid_level_lv_server": {
        "en": "**Nickname**: {v0}\n**UID**: `{v1}`\n**Level**: Lv.{v2}\n**Server**: {v3}",
        "zh": "**暱稱**: {v0}\n**UID**: `{v1}`\n**等級**: Lv.{v2}\n**伺服器**: {v3}",
    },
    "genshin_cog.linking_failed_check_that_and_are": {
        "en": " Linking failed: {v0}\n\nCheck that `{v1}` and `{v2}` are valid credentials for {v3}.\nUse `/mhy tutorial` for instructions.",
        "zh": " 綁定失敗：{v0}\n\n請確認您輸入的 `{v1}`、`{v2}` 是否正確且為{v3}的數值。\n若有疑問，請輸入 `/mhy tutorial` 查看獲取教學。",
    },
    "genshin_cog.check_in_failed": {
        "en": " Check-in failed: {v0}",
        "zh": " 簽到失敗：{v0}",
    },
    "genshin_cog.genshin_impact_real_time_notes": {
        "en": " Genshin Impact — Real-time notes",
        "zh": " 原神 - 實時便箋",
    },
    "genshin_cog.original_resin": {"en": "Original Resin", "zh": "原粹樹脂"},
    "genshin_cog.full_in": {
        "en": " **{v0} / {v1}**\n(Full in: {v2})",
        "zh": " **{v0} / {v1}**\n(恢復滿需: {v2})",
    },
    "genshin_cog.realm_currency": {"en": "Realm Currency", "zh": "洞天寶錢"},
    "genshin_cog.daily_commissions": {"en": "Daily Commissions", "zh": "每日委託"},
    "genshin_cog.bonus_reward": {
        "en": " **{v0} / {v1}**\n(Bonus reward: {v2})",
        "zh": " **{v0} / {v1}**\n(額外獎勵: {v2})",
    },
    "genshin_cog.weekly_boss_discounts": {
        "en": "Weekly boss discounts",
        "zh": "週本樹脂減半",
    },
    "genshin_cog.remaining": {
        "en": "️ **{v0} / {v1}** remaining",
        "zh": "️ 剩餘 **{v0} / {v1}** 次",
    },
    "genshin_cog.parametric_transformer": {
        "en": "Parametric Transformer",
        "zh": "參量質變儀",
    },
    "genshin_cog.completed": {"en": " Completed", "zh": " 已完成"},
    "genshin_cog.remaining_6cdafb": {"en": "⏳ Remaining: {v0}", "zh": "⏳ 剩餘 {v0}"},
    "genshin_cog.expedition": {"en": "• Expedition — {v0}", "zh": "• 探索派遣 - {v0}"},
    "genshin_cog.expeditions": {
        "en": "Expeditions ({v0} / {v1})",
        "zh": "探索派遣 ({v0} / {v1})",
    },
    "genshin_cog.could_not_retrieve_real_time_notes": {
        "en": " Could not retrieve real-time notes: {v0}",
        "zh": " 查詢實時便箋時發生錯誤：{v0}",
    },
    "genshin_cog.redemption_failed": {
        "en": " Redemption failed: {v0}",
        "zh": " 兌換失敗：{v0}",
    },
    "genshin_cog.trailblaze_level": {"en": "Trailblaze Level", "zh": "開拓等級"},
    "genshin_cog.achievements": {"en": "Achievements", "zh": "達成成就"},
    "genshin_cog.characters_agents": {
        "en": "Characters / agents",
        "zh": "角色/代理人數量",
    },
    "genshin_cog.chests_opened": {"en": "Chests opened", "zh": "開啟寶箱數"},
    "genshin_cog.serenitea_pot_level": {
        "en": "Serenitea Pot level",
        "zh": "塵歌壺等級",
    },
    "genshin_cog.bangboo_obtained": {"en": "Bangboo obtained", "zh": "獲得邦布數"},
    "genshin_cog.could_not_retrieve_statistics": {
        "en": " Could not retrieve statistics: {v0}",
        "zh": " 獲取統計數據時發生錯誤：{v0}",
    },
    "genshin_cog.could_not_retrieve_abyss_data": {
        "en": " Could not retrieve abyss data: {v0}",
        "zh": " 獲取深淵數據時發生錯誤：{v0}",
    },
    "genshin_cog.no_active_expeditions": {
        "en": "No active expeditions",
        "zh": "無進行中的探索派遣",
    },
    "genshin_cog.honkai_star_rail_real_time_notes": {
        "en": " Honkai: Star Rail — Real-time notes",
        "zh": " 崩壞：星穹鐵道 - 實時便箋",
    },
    "genshin_cog.trailblaze_power": {"en": "Trailblaze Power", "zh": "開拓力"},
    "genshin_cog.reserved_trailblaze_power": {
        "en": "Reserved Trailblaze Power",
        "zh": "後備開拓力",
    },
    "genshin_cog.daily_training": {"en": "Daily Training", "zh": "每日實訓"},
    "genshin_cog.points": {
        "en": " **{v0} / {v1}** points",
        "zh": " **{v0} / {v1}** 分",
    },
    "genshin_cog.simulated_universe": {"en": "Simulated Universe", "zh": "模擬宇宙"},
    "genshin_cog.assignment": {"en": "Assignment", "zh": "委託"},
    "genshin_cog.assignments": {
        "en": "Assignments ({v0} / {v1})",
        "zh": "派遣委託 ({v0} / {v1})",
    },
    "genshin_cog.inter_knot_level": {"en": "Inter-Knot Level", "zh": "繩網等級"},
    "genshin_cog.character_level": {"en": "Character level", "zh": "角色等級"},
    "genshin_cog.deepest_floor_reached": {
        "en": "Deepest floor reached",
        "zh": "最深抵達層數",
    },
    "genshin_cog.total_stars": {"en": "Total stars", "zh": "獲得總星數"},
    "genshin_cog.battles_wins": {"en": "Battles / wins", "zh": "戰鬥/勝利次數"},
    "genshin_cog.battles_wins_29eccf": {
        "en": "{v0} battles / {v1} wins",
        "zh": "{v0} 次 / {v1} 勝",
    },
    "genshin_cog.memory_of_chaos_moc": {
        "en": "️ Memory of Chaos (MoC)",
        "zh": "️ 混沌回憶 (MoC)",
    },
    "genshin_cog.season_progress_stars": {
        "en": "**Season**: {v0}\n**Progress**: {v1}\n**Stars**: ⭐ {v2}",
        "zh": "**當前賽季**: {v0}\n**最深進度**: {v1}\n**獲得星數**: ⭐ {v2}",
    },
    "genshin_cog.pure_fiction_pf": {"en": " Pure Fiction (PF)", "zh": " 虛構敘事 (PF)"},
    "genshin_cog.apocalyptic_shadow_as": {
        "en": "️ Apocalyptic Shadow (AS)",
        "zh": "️ 末日幻影 (AS)",
    },
    "genshin_cog.anomaly_arbitration_aa": {
        "en": "️ Anomaly Arbitration (AA)",
        "zh": "️ 異相仲裁 (AA)",
    },
    "genshin_cog.no_active_assignments": {
        "en": "No active assignments",
        "zh": "無進行中的派遣委託",
    },
    "genshin_cog.zenless_zone_zero_real_time_notes": {
        "en": " Zenless Zone Zero — Real-time notes",
        "zh": " 絕區零 - 實時便箋",
    },
    "genshin_cog.battery_charge": {"en": "Battery Charge", "zh": "電量"},
    "genshin_cog.daily_activity": {"en": "Daily activity", "zh": "每日活躍"},
    "genshin_cog.daily_scratch_card": {"en": "Daily scratch card", "zh": "今日刮刮卡"},
    "genshin_cog.value": {"en": "️ **{v0}**", "zh": "️ **{v0}**"},
    "genshin_cog.video_store_status": {
        "en": "Video store status",
        "zh": "錄影帶店狀態",
    },
    "genshin_cog.shiyu_defense_progress": {
        "en": "Shiyu Defense progress",
        "zh": "式輿防衛戰進度",
    },
    "genshin_cog.miyoushe_china": {"en": "Miyoushe China", "zh": "米游社國服"},
    "genshin_cog.hoyolab_global": {"en": "HoYoLAB global", "zh": "HoYoLAB 國際服"},
    "genshin_cog.hoyolab_miyoushe_automatic_daily_check_in": {
        "en": " HoYoLAB / Miyoushe automatic daily check-in report",
        "zh": " HoYoLAB / 米游社 每日自動簽到報告",
    },
    "genshin_cog.use_mhy_toggle_autosignin_to_disable": {
        "en": "Use /mhy toggle_autosignin to disable this notification",
        "zh": "可使用 /mhy toggle_autosignin 關閉此通知",
    },
    "genshin_cog.claimed": {"en": "Claimed", "zh": "已領取"},
    "genshin_cog.not_claimed": {"en": "Not claimed", "zh": "未領取"},
    "genshin_cog.honkai_impact_3rd_real_time_notes": {
        "en": "️ Honkai Impact 3rd — Real-time notes",
        "zh": "️ 崩壞3rd - 實時便箋",
    },
    "genshin_cog.stamina": {"en": "Stamina", "zh": "體力"},
    "genshin_cog.daily_missions": {"en": "Daily missions", "zh": "每日使命"},
    "genshin_cog.completed_e99b48": {"en": "Completed", "zh": "已完成"},
    "genshin_cog.not_completed": {"en": "Not completed", "zh": "未完成"},
}

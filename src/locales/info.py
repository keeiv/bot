"""Messages for /user_info and /server_info.

The Chinese text is the original wording, unchanged.
"""

MESSAGES: dict[str, dict[str, str]] = {
    "info.none": {"en": "None", "zh": "無"},
    "info.unavailable": {"en": "Unavailable", "zh": "無法獲取"},
    # ── /user_info ─────────────────────────────────────────────────
    "info.user.title": {"en": "User info", "zh": "用戶資訊"},
    "info.user.target": {"en": "Target: {mention}", "zh": "目標：{mention}"},
    "info.user.status_line": {"en": "Status: {status}", "zh": "狀態：{status}"},
    "info.queried": {"en": "Queried at: {time}", "zh": "查詢時間：{time}"},
    "info.user.avatar": {"en": "User avatar", "zh": "用戶頭像"},
    "info.user.basic": {"en": "Basic info", "zh": "基本資料"},
    "info.user.id": {"en": "User ID", "zh": "用戶ID"},
    "info.user.username": {"en": "Username", "zh": "用戶名"},
    "info.user.display_name": {"en": "Display name", "zh": "顯示名稱"},
    "info.user.created": {"en": "Account created", "zh": "帳號創立時間"},
    "info.user.joined": {"en": "Joined server", "zh": "加入伺服器時間"},
    "info.user.account_status": {"en": "Account status", "zh": "帳號狀態"},
    "info.user.joined_unknown": {
        "en": "Unavailable, or not in this server",
        "zh": "無法獲取或不在伺服器內",
    },
    "info.user.bot": {"en": "Bot", "zh": "機器人"},
    "info.user.regular": {"en": "Regular user", "zh": "普通用戶"},
    "info.user.roles": {"en": "Roles", "zh": "角色"},
    "info.user.achievements": {"en": "Achievement progress", "zh": "成就進度"},
    "info.user.osu": {"en": "osu! info", "zh": "osu! 資訊"},
    "info.user.banner": {"en": "User banner", "zh": "用戶橫幅"},
    "info.user.osu_linked": {
        "en": "Linked: {name}\nLive data is unavailable right now; the link is kept.",
        "zh": "已綁定: {name}\n即時資料暫時無法取得，綁定仍保留。",
    },
    "info.user.osu_username": {"en": "Username: {value}", "zh": "用戶名: {value}"},
    "info.user.osu_global_rank": {
        "en": "Global rank: {value}",
        "zh": "全球排名: {value}",
    },
    "info.user.osu_country_rank": {
        "en": "Country rank: {value}",
        "zh": "國家排名: {value}",
    },
    "info.user.osu_pp": {"en": "PP: {value}", "zh": "PP: {value}"},
    "info.user.osu_accuracy": {"en": "Accuracy: {value}", "zh": "準確度: {value}"},
    "info.user.osu_link": {"en": "Link: {value}", "zh": "連結: {value}"},
    "info.user.osu_unranked": {"en": "Unranked", "zh": "未排名"},
    "info.user.osu_unknown": {"en": "Unknown", "zh": "未知"},
    "info.user.error": {
        "en": "[Error] Couldn't get the user's info. Please try again later.",
        "zh": "[錯誤] 無法獲取用戶資訊，請稍後重試。",
    },
    # ── /server_info ───────────────────────────────────────────────
    "info.server.title": {"en": "Server info", "zh": "伺服器資訊"},
    "info.server.name_line": {"en": "Server: **{name}**", "zh": "伺服器：**{name}**"},
    "info.server.member_total_line": {
        "en": "Total members: {count}",
        "zh": "成員總數：{count}",
    },
    "info.server.icon": {"en": "Server icon", "zh": "伺服器圖標"},
    "info.server.basic": {"en": "Basic info", "zh": "基本資料"},
    "info.server.name": {"en": "Server name", "zh": "伺服器名稱"},
    "info.server.id": {"en": "Server ID", "zh": "伺服器ID"},
    "info.server.created": {"en": "Created", "zh": "創建時間"},
    "info.server.owner": {"en": "Owner", "zh": "擁有者"},
    "info.server.members": {"en": "Member stats", "zh": "成員統計"},
    "info.server.members_total": {"en": "Total: {count}", "zh": "總計: {count}"},
    "info.server.members_humans": {"en": "Humans: {count}", "zh": "人類: {count}"},
    "info.server.members_bots": {"en": "Bots: {count}", "zh": "Bot: {count}"},
    "info.server.channels": {"en": "Channel stats", "zh": "頻道統計"},
    "info.server.channels_text": {"en": "Text: {count}", "zh": "文字: {count}"},
    "info.server.channels_voice": {"en": "Voice: {count}", "zh": "語音: {count}"},
    "info.server.channels_categories": {
        "en": "Categories: {count}",
        "zh": "分類: {count}",
    },
    "info.server.settings": {"en": "Server settings", "zh": "伺服器設定"},
    "info.server.role_count": {"en": "Role count", "zh": "角色數量"},
    "info.server.verification": {"en": "Verification level", "zh": "驗證等級"},
    "info.server.boost": {"en": "Boost info", "zh": "Boost 資訊"},
    "info.server.boost_tier": {"en": "Tier: {tier}", "zh": "等級: {tier}"},
    "info.server.boost_count": {"en": "Boosts: {count}", "zh": "Boosts: {count}"},
    "info.server.description": {"en": "Description", "zh": "描述"},
    "info.server.banner": {"en": "Server banner", "zh": "伺服器橫幅"},
    "info.server.only_in_server": {
        "en": "[Failed] This command can only be used in a server",
        "zh": "[失敗] 此命令只能在伺服器中使用",
    },
    "info.server.error": {
        "en": "[Error] Couldn't get the server info: {error}",
        "zh": "[錯誤] 無法獲取伺服器資訊: {error}",
    },
}

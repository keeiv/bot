"""English and Traditional Chinese copy for Arknights: Endfield (/endfield)."""

MESSAGES: dict[str, dict[str, str]] = {
    "endfield.profile_title": {
        "en": "[Endfield] {v0}",
        "zh": "[終末地] {v0}",
    },
    "endfield.region": {"en": "Server", "zh": "伺服器"},
    "endfield.authority_level": {"en": "Authority level", "zh": "權限等級"},
    "endfield.world_level": {"en": "World level", "zh": "世界等級"},
    "endfield.owned": {"en": "Owned", "zh": "持有"},
    "endfield.owned_value": {
        "en": "{v0} operators · {v1} weapons",
        "zh": "{v0} 名幹員 · {v1} 把武器",
    },
    "endfield.showcase": {"en": "Showcase ({v0})", "zh": "展示中的幹員（{v0}）"},
    "endfield.showcase_empty": {
        "en": "No operators shown. Add some to the showcase in the game's profile menu.",
        "zh": "沒有展示中的幹員。請在遊戲的個人名片設定展示幹員。",
    },
    "endfield.operator_line": {
        "en": "**{v0}** {v1} · Lv{v2} · potential {v3} · {v4} {v5}",
        "zh": "**{v0}** {v1} · Lv{v2} · 潛能 {v3} · {v4} {v5}",
    },
    "endfield.footer": {
        "en": "Public showcase data via Enka.Network",
        "zh": "資料來自 Enka.Network 的公開展示",
    },
    "endfield.operator_kind": {"en": "{v0} · {v1} · {v2}", "zh": "{v0} · {v1} · {v2}"},
    "endfield.level": {"en": "Level", "zh": "等級"},
    "endfield.potential": {"en": "Potential", "zh": "潛能"},
    "endfield.weapon": {"en": "Weapon", "zh": "武器"},
    "endfield.weapon_value": {
        "en": "{v0} {v1} · Lv{v2} · potential {v3}",
        "zh": "{v0} {v1} · Lv{v2} · 潛能 {v3}",
    },
    "endfield.gear_sets": {"en": "Gear sets", "zh": "裝備套組"},
    "endfield.skills": {"en": "Skills", "zh": "技能"},
    "endfield.operator_footer": {
        "en": "{v0} ({v1}) · public showcase via Enka.Network",
        "zh": "{v0}（{v1}）· 資料來自 Enka.Network 的公開展示",
    },
    "endfield.nobody": {"en": "nobody", "zh": "沒有"},
    "endfield.operator_not_shown": {
        "en": "[Info] {v0} is not in this showcase. Shown: {v1}",
        "zh": "[提示] 展示中沒有「{v0}」。目前展示：{v1}",
    },
    "endfield.roster_title": {
        "en": "[Endfield] {v0}'s operators",
        "zh": "[終末地] {v0} 的幹員",
    },
    "endfield.operators_owned": {"en": "{v0} operators", "zh": "{v0} 名幹員"},
    "endfield.stamina": {"en": "Stamina", "zh": "理智"},
    "endfield.roster_more": {
        "en": "{v0} more not shown · read from your SKPORT account",
        "zh": "另有 {v0} 名未列出 · 資料來自你的 SKPORT 帳號",
    },
    "endfield.roster_footer": {
        "en": "Read from your SKPORT account",
        "zh": "資料來自你的 SKPORT 帳號",
    },
    "endfield.link_title": {"en": "Link a SKPORT account", "zh": "連結 SKPORT 帳號"},
    "endfield.link_label": {"en": "Account token", "zh": "帳號憑證"},
    "endfield.link_placeholder": {
        "en": "Paste the whole page. See /endfield tutorial",
        "zh": "貼上整個頁面內容，步驟見 /endfield tutorial",
    },
    "endfield.linked": {
        "en": "[Success] Linked: {v0} operators found. Your token is stored encrypted; /endfield unbind removes it.",
        "zh": "[成功] 已連結，找到 {v0} 名幹員。憑證已加密保存，用 /endfield unbind 可以刪除。",
    },
    "endfield.not_linked": {
        "en": "[Info] No SKPORT account is linked. Use /endfield link; /endfield tutorial shows how.",
        "zh": "[提示] 還沒有連結 SKPORT 帳號。請用 /endfield link，步驟見 /endfield tutorial。",
    },
    "endfield.operator_not_owned": {
        "en": "[Info] You do not own an operator called {v0}.",
        "zh": "[提示] 你沒有名為「{v0}」的幹員。",
    },
    "endfield.tutorial_title": {
        "en": "[Endfield] Getting your SKPORT account token",
        "zh": "[終末地] 取得 SKPORT 帳號憑證",
    },
    "endfield.tutorial_body": {
        "en": "1. Sign in at {v0} with your game account, in a computer browser.\n2. In the same browser, open {v1}\n3. Copy everything on the page.\n4. Use /endfield link and paste it.\n\n**The token signs in to your SKPORT account, so treat it like a password.** Only paste it into /endfield link and never into a chat. It is stored encrypted and used only to read your own game card; /endfield unbind deletes it. Signing out of SKPORT may end it, and then you link again. SKPORT has no official API, so this could stop working. Servers in mainland China are not supported.",
        "zh": "1. 用電腦瀏覽器到 {v0} 登入遊戲帳號。\n2. 在同一個瀏覽器開啟 {v1}\n3. 複製頁面上的全部內容。\n4. 使用 /endfield link 貼上。\n\n**憑證可以登入你的 SKPORT 帳號，請當成密碼看待。** 只貼在 /endfield link，不要貼到任何聊天裡。它會加密保存，只用來讀取你自己的遊戲資料；/endfield unbind 可以刪除。登出 SKPORT 後憑證可能失效，屆時重新連結即可。SKPORT 沒有官方 API，這項功能之後可能失效。不支援中國大陸伺服器。",
    },
    "endfield.not_bound": {
        "en": "[Info] No Endfield UID is linked. Use /endfield bind with the UID from the game's profile menu.",
        "zh": "[提示] 還沒有綁定終末地 UID。請用 /endfield bind 填入遊戲個人名片上的 UID。",
    },
    "endfield.bound": {
        "en": "[Success] Linked {v0}. Only the public showcase is read; nothing secret is stored.",
        "zh": "[成功] 已綁定 {v0}。只讀取公開展示的資料，不保存任何密碼或憑證。",
    },
    "endfield.bound_unchecked": {
        "en": "[Success] Linked UID {v0}. Enka.Network did not answer just now, so it was not checked yet.",
        "zh": "[成功] 已綁定 UID {v0}。Enka.Network 暫時沒有回應，所以還沒確認這個 UID。",
    },
    "endfield.unbound": {
        "en": "[Success] Your Endfield link was removed.",
        "zh": "[成功] 已解除終末地綁定。",
    },
    "endfield.error_bad_token": {
        "en": "[Failed] SKPORT did not accept this token, or it has expired. Get a new one with /endfield tutorial.",
        "zh": "[失敗] SKPORT 不接受這個憑證，或憑證已過期。請依 /endfield tutorial 重新取得。",
    },
    "endfield.error_no_role": {
        "en": "[Failed] This SKPORT account has no Endfield character.",
        "zh": "[失敗] 這個 SKPORT 帳號沒有終末地角色。",
    },
    "endfield.error_no_key": {
        "en": "[Failed] The encryption key is not set up, so the token was not saved. Please tell the bot's owner.",
        "zh": "[失敗] 尚未設定加密金鑰，所以沒有保存憑證。請告知機器人擁有者。",
    },
    "endfield.error_bad_uid": {
        "en": "[Failed] That is not a UID. Copy the number from the game's profile menu.",
        "zh": "[失敗] 這不是 UID，請從遊戲的個人名片複製那串數字。",
    },
    "endfield.error_not_found": {
        "en": "[Failed] No player has this UID.",
        "zh": "[失敗] 找不到這個 UID 的玩家。",
    },
    "endfield.error_maintenance": {
        "en": "[Failed] The game is under maintenance or just updated; try again later.",
        "zh": "[失敗] 遊戲維護中或剛更新，請稍後再試。",
    },
    "endfield.error_rate_limited": {
        "en": "[Failed] Too many lookups right now; try again in a minute.",
        "zh": "[失敗] 查詢太頻繁，請一分鐘後再試。",
    },
    "endfield.error_unavailable": {
        "en": "[Failed] Enka.Network cannot be reached right now; try again later.",
        "zh": "[失敗] 暫時連不上 Enka.Network，請稍後再試。",
    },
}

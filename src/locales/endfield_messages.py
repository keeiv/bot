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

"""English and Traditional Chinese copy for the AI chat."""

MESSAGES: dict[str, dict[str, str]] = {
    "ai_chat.name_claude": {"en": "Sonnet", "zh": "十四行詩"},
    "ai_chat.name_gpt": {"en": "Dawn", "zh": "晨曦"},
    "ai_chat.chosen": {
        "en": "[Success] {v0} will answer you",
        "zh": "[成功] 之後由{v0}回應你",
    },
    "ai_chat.intro_claude": {
        "en": "...Pleased to meet you. I am Sonnet. Please take your time and tell me what is on your mind.",
        "zh": "……初次見面，我是十四行詩。有什麼想說的，請您慢慢說。",
    },
    "ai_chat.intro_gpt": {
        "en": "Hi hi! I'm Dawn! What shall we talk about today?",
        "zh": "嗨嗨！我是晨曦！今天想聊什麼呀？",
    },
    "ai_chat.how_to_talk": {
        "en": "Talk with /ai chat or @BOT. · Dawn draws with /ai image · switch with /ai choose",
        "zh": "用 /ai chat 或 @BOT. 聊天 · /ai image 請 Dawn 畫圖 · /ai choose 換人",
    },
    "ai_chat.no_allowance": {
        "en": "[Failed] Not enough allowance left for this (it needs {v0} points). Check it with /usage.",
        "zh": "[失敗] 你的額度不夠這次使用（需要 {v0} 點），可以用 /usage 查看。",
    },
    "ai_chat.dev_usage": {
        "en": "[Info] `>>>{v0} [number] 1` for you only · `>>>{v0} [number] 2` for everyone · `>>>{v0} reset` back to the default",
        "zh": "[提示] `>>>{v0} [編號] 1` 只改自己 · `>>>{v0} [編號] 2` 改全部人 · `>>>{v0} reset` 恢復預設",
    },
    "ai_chat.dev_list_title": {"en": "**{v0}** models", "zh": "**{v0}** 可用模型"},
    "ai_chat.dev_mark_default": {"en": "default", "zh": "預設"},
    "ai_chat.dev_mark_everyone": {"en": "everyone", "zh": "全部人"},
    "ai_chat.dev_mark_you": {"en": "you", "zh": "你"},
    "ai_chat.dev_set_self": {
        "en": "[Success] Your {v0} model is now {v1}.",
        "zh": "[成功] 已把你自己的 {v0} 換成 {v1}。",
    },
    "ai_chat.dev_set_all": {
        "en": "[Success] Everyone's {v0} model is now {v1} (personal choices still come first).",
        "zh": "[成功] 已把所有人的 {v0} 換成 {v1}（個人設定仍優先）。",
    },
    "ai_chat.dev_reset": {
        "en": "[Success] {v0} is back to the default for everyone ({v1}).",
        "zh": "[成功] {v0} 已全部恢復預設（{v1}）。",
    },
    "ai_chat.dev_bad_number": {
        "en": "[Failed] There is no such number; `>>>{v0}` lists them.",
        "zh": "[失敗] 沒有這個編號，用 `>>>{v0}` 查看清單。",
    },
    "ai_chat.choose_first": {
        "en": "[Info] Pick who answers you first with `/ai choose`.",
        "zh": "[提示] 請先用 `/ai choose` 選擇要和誰聊天。",
    },
    "ai_chat.busy": {
        "en": "[Info] Your previous message is still being answered. Please wait a moment.",
        "zh": "[提示] 上一則訊息還在回覆中，請稍等一下。",
    },
    "ai_chat.maintenance": {
        "en": "This feature is under maintenance. Please try again later.",
        "zh": "此功能暫時維護中 稍後再試",
    },
    "ai_chat.forgotten": {
        "en": "[Success] Your conversation has been cleared.",
        "zh": "[成功] 已清除這段對話的記憶。",
    },
}

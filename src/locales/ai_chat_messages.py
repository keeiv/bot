"""English and Traditional Chinese copy for the AI chat."""

MESSAGES: dict[str, dict[str, str]] = {
    "ai_chat.name_claude": {"en": "Sonnet", "zh": "十四行詩"},
    "ai_chat.name_gpt": {"en": "Dawn", "zh": "晨曦"},
    "ai_chat.chosen": {
        "en": "{v0} will answer you",
        "zh": "之後由{v0}回應你",
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
        "en": "Talk with /ai chat · switch with /ai choose",
        "zh": "用 /ai chat 聊天 · 用 /ai choose 換人",
    },
    "ai_chat.choose_first": {
        "en": "Pick who answers you first with `/ai choose`.",
        "zh": "請先用 `/ai choose` 選擇要和誰聊天。",
    },
    "ai_chat.busy": {
        "en": "Your previous message is still being answered. Please wait a moment.",
        "zh": "上一則訊息還在回覆中，請稍等一下。",
    },
    "ai_chat.maintenance": {
        "en": "This feature is under maintenance. Please try again later.",
        "zh": "此功能暫時維護中 稍後再試",
    },
    "ai_chat.forgotten": {
        "en": "Your conversation has been cleared.",
        "zh": "已清除這段對話的記憶。",
    },
}

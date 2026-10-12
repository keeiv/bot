"""Messages for the guide channel, language switching, and core notices."""

SITE = "https://botweb.shizune.life"
ISSUES = "https://github.com/keeiv/bot/issues"

MESSAGES: dict[str, dict[str, str]] = {
    # ── Guide channel ──────────────────────────────────────────────
    "guide.channel_name": {"en": "bot-guide", "zh": "bot-guide"},
    "guide.channel_topic": {
        "en": "How to use BOT. Admins can change the bot's language here.",
        "zh": "BOT. 的使用說明。管理員可以在這裡切換機器人語言。",
    },
    "guide.title": {"en": "Getting started with BOT.", "zh": "BOT. 使用說明"},
    "guide.intro": {
        "en": "Thanks for adding BOT. Here is what it does and where to start.",
        "zh": "感謝你邀請 BOT.。以下是它能做的事，以及從哪裡開始。",
    },
    "guide.start.name": {"en": "Start here", "zh": "從這裡開始"},
    "guide.start.value": {
        "en": "`/help` lists every command, grouped by what it does.\n"
        "Type `/` in any channel to browse them.",
        "zh": "`/help` 會依功能分類列出所有指令。\n在任何頻道輸入 `/` 也能瀏覽。",
    },
    "guide.setup.name": {"en": "Set it up", "zh": "設定"},
    "guide.setup.value": {
        "en": "Set up welcome messages, spam protection and tickets in the "
        f"dashboard: {SITE}/dashboard\n"
        "`/settings` shows the server's settings and changes the log and report "
        "channels without leaving Discord.",
        "zh": f"歡迎訊息、防洗版與工單可以在儀表板設定：{SITE}/dashboard\n"
        "`/settings` 可以直接在 Discord 裡查看伺服器設定，並設定日誌與舉報頻道。",
    },
    "guide.language.name": {"en": "Language", "zh": "語言"},
    "guide.language.value": {
        "en": "Server admins can switch the bot's replies between English and "
        "Chinese with the menu below or `/language`. In the `/` menu, command "
        "descriptions and options follow each member's own Discord language; "
        "command names stay in English.",
        "zh": "伺服器管理員可以用下方選單或 `/language` 在英文與中文之間切換機器人的"
        "回覆語言。`/` 選單裡的指令說明與選項會依照每位成員自己的 Discord 語言顯示，"
        "指令名稱維持英文。",
    },
    "guide.help.name": {"en": "Questions or bugs", "zh": "問題回報"},
    "guide.help.value": {
        "en": f"Open an issue on GitHub: {ISSUES}",
        "zh": f"到 GitHub 開 Issue：{ISSUES}",
    },
    "guide.footer": {
        "en": "Only members with the Manage Server permission can change the language.",
        "zh": "只有擁有「管理伺服器」權限的成員可以切換語言。",
    },
    "guide.select.placeholder": {"en": "Bot language", "zh": "機器人語言"},
    "guide.select.en": {"en": "Replies in English", "zh": "以英文回覆"},
    "guide.select.zh": {"en": "Replies in Chinese", "zh": "以中文回覆"},
    # ── Language switching ─────────────────────────────────────────
    "language.denied": {
        "en": "Only members with the Manage Server permission can change this "
        "server's language.",
        "zh": "只有擁有「管理伺服器」權限的成員可以切換這個伺服器的語言。",
    },
    "language.server_set": {
        "en": "This server now uses {language}.",
        "zh": "這個伺服器現在使用{language}。",
    },
    "language.personal_set": {
        "en": "Your language is now {language}. It applies in DMs and wherever you "
        "use BOT. as a personal app.",
        "zh": "你的語言已設為{language}。它會用在私訊，以及你以個人應用程式使用 BOT. 的地方。",
    },
    "language.current_server": {
        "en": "This server uses {language}. Server admins can change it with "
        "`/language`.",
        "zh": "這個伺服器使用{language}。伺服器管理員可以用 `/language` 切換。",
    },
    "language.current_personal": {
        "en": "Your language is {language}. Pick another one with `/language`.",
        "zh": "你的語言是{language}。可以用 `/language` 改成其他語言。",
    },
    "language.failed": {
        "en": "The language could not be saved. Please try again in a moment.",
        "zh": "語言設定沒有儲存成功，請稍後再試一次。",
    },
    # ── Blacklist notice (bot.py) ──────────────────────────────────
    "blacklist.title": {"en": "Access denied", "zh": "禁止使用"},
    "blacklist.body": {
        "en": "You have been blacklisted.\n\nReason: {reason}\nSource: {source}",
        "zh": "您已被加入黑名單。\n\n原因：{reason}\n來源：{source}",
    },
    "blacklist.no_reason": {"en": "No reason given", "zh": "未提供原因"},
    "blacklist.source_local": {"en": "Local blacklist", "zh": "本地黑名單"},
    "blacklist.source_api": {"en": "CatHome API", "zh": "CatHome API"},
    # ── Translate message (context menu) ───────────────────────────
    "translate.no_text": {
        "en": "That message has no text to translate.",
        "zh": "這則訊息沒有可以翻譯的文字。",
    },
    "translate.too_long": {
        "en": "That message is too long to translate.",
        "zh": "這則訊息太長，無法翻譯。",
    },
    "translate.choose": {"en": "Translate to:", "zh": "要翻譯成哪種語言："},
    "translate.placeholder": {"en": "Choose a language…", "zh": "選擇目標語言…"},
    "translate.failed": {
        "en": "Translation failed. Please try again later.",
        "zh": "翻譯失敗，請稍後再試。",
    },
    "translate.title": {"en": "Translated to {target}", "zh": "翻譯成{target}"},
    "translate.original": {"en": "Original", "zh": "原文"},
    "translate.result": {"en": "Translation", "zh": "翻譯結果"},
}

"""/help content in both languages.

The Chinese text is the original help copy (only renamed commands updated); the
English text is a translation of it, not a different help page.
"""

from dataclasses import dataclass

import discord


@dataclass(frozen=True)
class HelpBlock:
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class HelpCategory:
    key: str
    label: str
    description: str
    accent_color: discord.Color
    summary: str
    blocks: tuple[HelpBlock, ...]


MESSAGES: dict[str, dict[str, str]] = {
    "help.title": {"en": "Help", "zh": "幫助中心"},
    "help.current": {"en": "Section: **{label}**", "zh": "目前分區：**{label}**"},
    "help.placeholder": {"en": "Choose a help section", "zh": "選擇幫助分區"},
    "help.denied": {
        "en": "Only the person who ran the command can switch sections.",
        "zh": "只有發起指令的人可以切換幫助分區。",
    },
    "help.avatar": {"en": "Bot avatar", "zh": "機器人頭像"},
}

_BLUE = discord.Color.from_rgb(52, 152, 219)
_GREEN = discord.Color.from_rgb(46, 204, 113)
_RED = discord.Color.from_rgb(231, 76, 60)
_YELLOW = discord.Color.from_rgb(241, 196, 15)
_PURPLE = discord.Color.from_rgb(155, 89, 182)
_TEAL = discord.Color.from_rgb(26, 188, 156)

CATEGORIES: dict[str, tuple[HelpCategory, ...]] = {
    "zh": (
        HelpCategory(
            key="overview",
            label="總覽",
            description="機器人介紹與常用入口",
            accent_color=_BLUE,
            summary=(
                "功能完整的 Discord 機器人，包含管理、社群工具、遊戲、osu! 整合與 "
                "GitHub 監控。使用下拉選單可以切換不同分區。"
            ),
            blocks=(
                HelpBlock(
                    title="快速入口",
                    lines=(
                        "`/help` - 開啟這份互動式說明",
                        "`/language` - 切換機器人語言",
                        "`/achievements` - 查看成就進度",
                        "`/user_info` - 查看用戶資訊",
                        "`/server_info` - 查看伺服器資訊",
                    ),
                ),
                HelpBlock(
                    title="常用功能",
                    lines=(
                        "`/clear` - 清除指定數量的訊息",
                        "`/giveaway start` - 建立抽獎活動",
                        "`/osu bind` - 綁定 osu! 帳號",
                        "`/repo_track status` - 查看 keeiv/bot 追蹤狀態",
                    ),
                ),
                HelpBlock(
                    title="使用方式",
                    lines=(
                        "下方選單可切換到管理、防護、社群工具、遊戲整合與開發指南。",
                        "大部分管理類指令需要對應的伺服器權限才可使用。",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="moderation",
            label="管理與審計",
            description="管理指令、審計、外觀與舉報",
            accent_color=_GREEN,
            summary="伺服器日常管理、訊息紀錄、機器人外觀調整與舉報流程。",
            blocks=(
                HelpBlock(
                    title="管理指令",
                    lines=(
                        "`/message_log_settings` - 設置訊息日誌頻道",
                        "`/clear` - 清除指定數量的訊息",
                        "`/kick` - 踢出成員",
                        "`/ban` - 封禁成員",
                        "`/mute` - 禁言成員",
                        "`/warn` - 警告成員",
                    ),
                ),
                HelpBlock(
                    title="審計日誌",
                    lines=(
                        "自動記錄成員加入/離開、語音頻道異動、角色變更、暱稱變更。",
                        "也會追蹤頻道建立、刪除與修改等管理事件。",
                    ),
                ),
                HelpBlock(
                    title="機器人外觀",
                    lines=(
                        "`/bot_appearance name` - 更改機器人暱稱",
                        "`/bot_appearance avatar` - 更改機器人頭像 (需審核)",
                        "`/bot_appearance banner` - 更改機器人橫幅 (需審核)",
                    ),
                ),
                HelpBlock(
                    title="舉報系統",
                    lines=(
                        "右鍵訊息 > 應用程式 > `舉報訊息`（英文介面為 `Report message`）- 舉報可疑訊息",
                        "`/report_channel set` - 設定舉報接收頻道",
                        "`/report_channel status` - 查看舉報頻道設定",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="protection",
            label="防護系統",
            description="防炸群與白名單管理",
            accent_color=_RED,
            summary="針對洪水、重複訊息、提及轟炸、連結與突襲的保護機制。",
            blocks=(
                HelpBlock(
                    title="防炸群功能",
                    lines=(
                        "`/anti_spam setup` - 啟用/禁用防炸群",
                        "`/anti_spam flood` - 訊息洪水偵測設定",
                        "`/anti_spam duplicate` - 重複內容偵測",
                        "`/anti_spam mention` - 提及轟炸偵測",
                        "`/anti_spam link` - 連結/邀請偵測",
                        "`/anti_spam raid` - 突襲偵測",
                    ),
                ),
                HelpBlock(
                    title="進階設定",
                    lines=(
                        "`/anti_spam escalation` - 自動升級懲罰",
                        "`/anti_spam whitelist` - 白名單管理",
                        "`/anti_spam lockdown_off` - 解除封鎖",
                        "`/anti_spam status` - 查看完整狀態",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="community",
            label="社群工具",
            description="翻譯、抽獎、工單與資訊指令",
            accent_color=_YELLOW,
            summary="面向一般成員的常用工具與社群互動功能。",
            blocks=(
                HelpBlock(
                    title="翻譯",
                    lines=(
                        "右鍵訊息 > 應用程式 > `翻譯訊息`（英文介面為 `Translate message`）- 翻譯任意訊息",
                        "支援 14 種語言，自動偵測來源語言。",
                    ),
                ),
                HelpBlock(
                    title="抽獎",
                    lines=(
                        "`/giveaway start` - 建立抽獎活動",
                        "`/giveaway end` - 提前結束抽獎",
                        "`/giveaway reroll` - 重新抽取得獎者",
                        "`/giveaway list` - 查看進行中抽獎",
                    ),
                ),
                HelpBlock(
                    title="工單系統",
                    lines=(
                        "`>>>ticket setup #頻道 @身份組` - 設定工單系統",
                        "點擊「開啟工單」按鈕建立私人討論串",
                        "支援一般關閉與附原因關閉工單",
                    ),
                ),
                HelpBlock(
                    title="其他資訊",
                    lines=(
                        "`/achievements` - 查看成就",
                        "`/user_info` - 查看用戶資訊",
                        "`/server_info` - 查看伺服器資訊",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="integrations",
            label="遊戲與整合",
            description="遊戲、osu! 與 GitHub",
            accent_color=_PURPLE,
            summary="娛樂功能與外部服務整合，包含 osu! 和 GitHub 工作流。",
            blocks=(
                HelpBlock(
                    title="遊戲",
                    lines=(
                        "`/deep-sea-oxygen` - 深海氧氣瓶遊戲",
                        "`/russian-roulette` - 俄羅斯輪盤",
                    ),
                ),
                HelpBlock(
                    title="osu! 整合",
                    lines=(
                        "`/user_info_osu` - 查詢 osu! 玩家資料",
                        "`/osu bind` - 綁定 osu! 帳號",
                        "`/osu best` - 查詢 BP",
                        "`/osu recent` - 查詢最近遊玩",
                    ),
                ),
                HelpBlock(
                    title="GitHub 監控",
                    lines=(
                        "`/repo_watch set` - 設定倉庫監控",
                        "`/repo_track add` - 追蹤 keeiv/bot 更新",
                        "`/repo_track status` - 查看追蹤狀態",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="contribute",
            label="參與開發",
            description="PR 流程與程式碼規範",
            accent_color=_TEAL,
            summary="專案接受社群貢獻。小型更新可直接 PR，大型變更先開 Issue 討論。",
            blocks=(
                HelpBlock(
                    title="小型 / 中型更新",
                    lines=(
                        "不需要事先討論，直接提交 PR 即可。",
                        "例如：新增獨立指令、修復 Bug、更新文件、程式碼重構。",
                    ),
                ),
                HelpBlock(
                    title="大型更新",
                    lines=(
                        "必須先開 Issue 討論後再開發。",
                        "例如：新增依賴、架構變動、資料結構調整、破壞性變更。",
                    ),
                ),
                HelpBlock(
                    title="PR 提交流程",
                    lines=(
                        "1. Fork 倉庫並建立分支",
                        "2. 完成開發並確保通過 CI 檢查",
                        "3. 使用 Conventional Commits，例如 `feat:`、`fix:`、`docs:`",
                        "4. 提交 PR 並清楚描述變更內容",
                    ),
                ),
                HelpBlock(
                    title="程式碼規範",
                    lines=(
                        "遵循 PEP 8 與現有專案風格。",
                        "使用 Black + isort 格式化，並通過 flake8。",
                        "新功能建議補上對應測試。",
                        "倉庫：github.com/keeiv/bot",
                    ),
                ),
            ),
        ),
    ),
    "en": (
        HelpCategory(
            key="overview",
            label="Overview",
            description="What the bot does and where to start",
            accent_color=_BLUE,
            summary=(
                "A Discord bot for moderation, community tools, games, osu! and "
                "GitHub updates. Use the menu below to switch sections."
            ),
            blocks=(
                HelpBlock(
                    title="Start here",
                    lines=(
                        "`/help` - open this interactive help",
                        "`/language` - switch the bot's language",
                        "`/achievements` - see your achievement progress",
                        "`/user_info` - look up a member",
                        "`/server_info` - look up this server",
                    ),
                ),
                HelpBlock(
                    title="Popular",
                    lines=(
                        "`/clear` - delete a number of recent messages",
                        "`/giveaway start` - start a giveaway",
                        "`/osu bind` - link your osu! account",
                        "`/repo_track status` - see keeiv/bot tracking status",
                    ),
                ),
                HelpBlock(
                    title="How to use it",
                    lines=(
                        "The menu below switches between moderation, protection, "
                        "community tools, games and the contributor guide.",
                        "Most moderation commands need the matching server permission.",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="moderation",
            label="Moderation and logs",
            description="Moderation, audit logs, appearance and reports",
            accent_color=_GREEN,
            summary="Day-to-day moderation, message logs, the bot's appearance, and "
            "reports.",
            blocks=(
                HelpBlock(
                    title="Moderation",
                    lines=(
                        "`/message_log_settings` - set the message log channel",
                        "`/clear` - delete a number of recent messages",
                        "`/kick` - kick a member",
                        "`/ban` - ban a member",
                        "`/mute` - time out a member",
                        "`/warn` - warn a member",
                    ),
                ),
                HelpBlock(
                    title="Audit log",
                    lines=(
                        "Logs joins and leaves, voice channel moves, role and nickname "
                        "changes.",
                        "Also tracks channels being created, deleted and edited.",
                    ),
                ),
                HelpBlock(
                    title="Bot appearance",
                    lines=(
                        "`/bot_appearance name` - change the bot's nickname",
                        "`/bot_appearance avatar` - change the bot's avatar (reviewed)",
                        "`/bot_appearance banner` - change the bot's banner (reviewed)",
                    ),
                ),
                HelpBlock(
                    title="Reports",
                    lines=(
                        "Right-click a message > Apps > `Report message` - report it",
                        "`/report_channel set` - choose where reports go",
                        "`/report_channel status` - see the report channel",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="protection",
            label="Protection",
            description="Spam protection and allow lists",
            accent_color=_RED,
            summary="Protection against floods, repeated messages, mass mentions, "
            "links and raids.",
            blocks=(
                HelpBlock(
                    title="Spam protection",
                    lines=(
                        "`/anti_spam setup` - turn spam protection on or off",
                        "`/anti_spam flood` - message flood detection",
                        "`/anti_spam duplicate` - repeated content detection",
                        "`/anti_spam mention` - mass mention detection",
                        "`/anti_spam link` - link and invite detection",
                        "`/anti_spam raid` - raid detection",
                    ),
                ),
                HelpBlock(
                    title="Advanced",
                    lines=(
                        "`/anti_spam escalation` - escalating penalties",
                        "`/anti_spam whitelist` - manage the allow list",
                        "`/anti_spam lockdown_off` - lift a lockdown",
                        "`/anti_spam status` - full status",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="community",
            label="Community tools",
            description="Translation, giveaways, tickets and info",
            accent_color=_YELLOW,
            summary="Everyday tools for members and community activities.",
            blocks=(
                HelpBlock(
                    title="Translation",
                    lines=(
                        "Right-click a message > Apps > `Translate message`",
                        "14 languages, with the source language detected for you.",
                    ),
                ),
                HelpBlock(
                    title="Giveaways",
                    lines=(
                        "`/giveaway start` - start a giveaway",
                        "`/giveaway end` - end a giveaway early",
                        "`/giveaway reroll` - draw new winners",
                        "`/giveaway list` - see running giveaways",
                    ),
                ),
                HelpBlock(
                    title="Tickets",
                    lines=(
                        "`>>>ticket setup #channel @role` - set up tickets",
                        "Members press the open-ticket button to start a private thread",
                        "Tickets can be closed with or without a reason",
                    ),
                ),
                HelpBlock(
                    title="Info",
                    lines=(
                        "`/achievements` - see achievements",
                        "`/user_info` - look up a member",
                        "`/server_info` - look up this server",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="integrations",
            label="Games and integrations",
            description="Games, osu! and GitHub",
            accent_color=_PURPLE,
            summary="Games and connections to outside services, including osu! and "
            "GitHub.",
            blocks=(
                HelpBlock(
                    title="Games",
                    lines=(
                        "`/deep-sea-oxygen` - deep-sea oxygen game",
                        "`/russian-roulette` - Russian roulette",
                    ),
                ),
                HelpBlock(
                    title="osu!",
                    lines=(
                        "`/user_info_osu` - look up an osu! player",
                        "`/osu bind` - link your osu! account",
                        "`/osu best` - best plays",
                        "`/osu recent` - recent plays",
                    ),
                ),
                HelpBlock(
                    title="GitHub",
                    lines=(
                        "`/repo_watch set` - watch a repository",
                        "`/repo_track add` - follow keeiv/bot updates",
                        "`/repo_track status` - see tracking status",
                    ),
                ),
            ),
        ),
        HelpCategory(
            key="contribute",
            label="Contributing",
            description="Pull requests and code style",
            accent_color=_TEAL,
            summary="Contributions are welcome. Small changes can go straight to a "
            "PR; open an issue first for large ones.",
            blocks=(
                HelpBlock(
                    title="Small and medium changes",
                    lines=(
                        "No need to ask first - just open a PR.",
                        "For example: a new standalone command, a bug fix, docs, or "
                        "a refactor.",
                    ),
                ),
                HelpBlock(
                    title="Large changes",
                    lines=(
                        "Open an issue to discuss it before you start.",
                        "For example: new dependencies, architecture or data "
                        "structure changes, breaking changes.",
                    ),
                ),
                HelpBlock(
                    title="Pull request steps",
                    lines=(
                        "1. Fork the repository and create a branch",
                        "2. Make your change and make sure CI passes",
                        "3. Use Conventional Commits, such as `feat:`, `fix:`, `docs:`",
                        "4. Open the PR and describe what changed",
                    ),
                ),
                HelpBlock(
                    title="Code style",
                    lines=(
                        "Follow PEP 8 and the existing style.",
                        "Format with Black and isort, and pass flake8.",
                        "Add tests for new features where you can.",
                        "Repository: github.com/keeiv/bot",
                    ),
                ),
            ),
        ),
    ),
}

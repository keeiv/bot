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
_RUST = discord.Color.from_rgb(196, 92, 44)

CATEGORIES: dict[str, tuple[HelpCategory, ...]] = {
    "zh": (
        HelpCategory(
            key="overview",
            label="總覽",
            description="機器人介紹與常用入口",
            accent_color=_BLUE,
            summary=(
                "功能完整的 Discord 機器人，包含管理、社群工具、遊戲、遊戲帳號整合與 "
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
                        "`/mhy bind` - 綁定 HoYoLAB／米游社帳號",
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
            description="翻譯、AI 聊天、抽獎、工單與資訊指令",
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
                    title="AI 聊天",
                    lines=(
                        "`/ai choose` - 選擇回應你的角色：十四行詩（Claude，文靜的大小姐）或晨曦（GPT，活潑開朗）",
                        "`/ai chat` - 和選擇的角色聊天，之後只由她回應你",
                        "`@BOT. 訊息` - 在頻道直接提及機器人，角色以分身回覆",
                        "`/ai image` - 請 Dawn 畫一張圖（只有 GPT 能畫）",
                        "兩位都會在需要時上網查資料；每次使用會扣檔案工具的點數額度",
                        "`/ai forget` - 清除她對這段對話的記憶",
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
            description="遊戲、遊戲帳號與 GitHub",
            accent_color=_PURPLE,
            summary="娛樂功能與外部服務整合，包含 HoYoLAB、終末地和 GitHub 工作流。",
            blocks=(
                HelpBlock(
                    title="遊戲",
                    lines=(
                        "鏽輪與沉鐘在「鏽錨站」分區",
                        "`/pet adopt` - 領養夥伴（寓言、方舟、諾瓦）",
                        "`/pet panel` - 查看並照顧夥伴",
                        "`/pet expedition` - 派夥伴遠征",
                        "`/pet guide` - 夥伴玩法說明",
                    ),
                ),
                HelpBlock(
                    title="遊戲帳號",
                    lines=(
                        "`/mhy bind` - 綁定 HoYoLAB／米游社帳號",
                        "`/mhy notes` - 查看即時便箋",
                        "`/mhy checkin` - 立即簽到",
                        "`/endfield bind` - 綁定終末地 UID",
                        "`/endfield profile` - 查看終末地名片",
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
            key="station",
            label="鏽錨站",
            description="鏽輪與沉鐘：Discord 活動裡的兩張桌",
            accent_color=_RUST,
            summary=(
                "海退後的乾海，鹽漠上的鏽錨站。兩款遊戲都在 Discord 活動裡進行，"
                "2 到 6 人同桌，也能單人跟莊家練習；電腦、網頁與手機都能玩。"
            ),
            blocks=(
                HelpBlock(
                    title="怎麼開",
                    lines=(
                        "`/russian-roulette` - 開啟鏽輪",
                        "`/deep-sea-oxygen` - 開啟沉鐘",
                        "也可以進語音頻道，從活動列表選 BOT. 的「鏽錨站」",
                        "進去後按「入座」，有兩人以上就能「開局」",
                    ),
                ),
                HelpBlock(
                    title="鏽輪：六發左輪，一顆子彈",
                    lines=(
                        "輪到你至少扣一次扳機",
                        "空響拿鹽：第幾發就拿幾份，可以再扣或交槍收鹽",
                        "中彈少一袋水、沒收這輪的鹽；三袋水喝乾就出局",
                        "手數用完或有人出局時結算，沒出局的人比鹽",
                    ),
                ),
                HelpBlock(
                    title="鏽輪道具",
                    lines=(
                        "聽輪：偷聽下一發，只有你知道",
                        "轉輪：重新上膛，回到六分之一",
                        "讓手：這輪不扣也能交槍",
                        "退彈：把下一發退出來給大家看",
                        "破壞鏈鋸：下一槍變散彈槍。對自己開，空響鹽加倍、"
                        "中彈扣兩袋水；對別人開，空響自己扣 1 鹽、"
                        "中彈對方扣 1 袋水和這發的鹽，不加倍",
                    ),
                ),
                HelpBlock(
                    title="沉鐘：一口鐘，一瓶氣",
                    lines=(
                        "每輪暗中決定：留在鐘裡、出去 1 到 3 分鐘，或帶著袋子上浮",
                        "回鐘由短到長；氣不夠時，同一批回來的人全被關在外面",
                        "備用氣瓶救你一次，代價是丟掉一半；氣錶每人能讀一次精確值",
                        "撐到第 7 層海底每人多拿 12；氣用光就緊急上浮，袋子丟一半",
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
                "A Discord bot for moderation, community tools, games, game "
                "accounts and GitHub updates. Use the menu below to switch sections."
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
                        "`/mhy bind` - link your HoYoLAB / Miyoushe account",
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
            description="Translation, AI chat, giveaways, tickets and info",
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
                    title="AI chat",
                    lines=(
                        "`/ai choose` - pick who answers you: Sonnet (Claude, a quiet, refined young lady) or Dawn (GPT, lively and cheerful)",
                        "`/ai chat` - talk to the character you picked; only she answers you",
                        "`@BOT. message` - mention the bot in a channel and she replies in person",
                        "`/ai image` - ask Dawn to draw a picture (only GPT draws)",
                        "Both search the web when needed; each use takes points from the file-tool allowance",
                        "`/ai forget` - clear what she remembers of your conversation",
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
            description="Games, game accounts and GitHub",
            accent_color=_PURPLE,
            summary="Games and connections to outside services, including HoYoLAB, "
            "Endfield and GitHub.",
            blocks=(
                HelpBlock(
                    title="Games",
                    lines=(
                        "The Rust Wheel and the Sunken Bell: see Rust Anchor Station",
                        "`/pet adopt` - adopt a companion (Fable, Ark, Nova)",
                        "`/pet panel` - see and care for your companion",
                        "`/pet expedition` - send it on an expedition",
                        "`/pet guide` - how companions work",
                    ),
                ),
                HelpBlock(
                    title="Game accounts",
                    lines=(
                        "`/mhy bind` - link your HoYoLAB / Miyoushe account",
                        "`/mhy notes` - real-time notes",
                        "`/mhy checkin` - check in now",
                        "`/endfield bind` - link your Endfield UID",
                        "`/endfield profile` - your Endfield business card",
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
            key="station",
            label="Rust Anchor Station",
            description="The Rust Wheel and the Sunken Bell, played as an activity",
            accent_color=_RUST,
            summary=(
                "The Dry Sea, after the water left: a station on the salt. Both games "
                "run as a Discord activity, 2 to 6 at a table or alone against the "
                "house, on desktop, the web and phones."
            ),
            blocks=(
                HelpBlock(
                    title="Opening a table",
                    lines=(
                        "`/russian-roulette` - open the Rust Wheel",
                        "`/deep-sea-oxygen` - open the Sunken Bell",
                        "Or join a voice channel and pick BOT.'s Rust Anchor Station "
                        "from the activities",
                        "Take a seat; with two or more seated, deal in",
                    ),
                ),
                HelpBlock(
                    title="The Rust Wheel: one revolver, one round",
                    lines=(
                        "On your turn, pull at least once",
                        "An empty click pays as much salt as chambers fired; pull "
                        "again or hand the gun on and bank it",
                        "A live round costs a water skin and this turn's salt; drink "
                        "the last of three and you are out",
                        "When the turns run out or someone is out, the rest are "
                        "ranked by salt",
                    ),
                ),
                HelpBlock(
                    title="Rust Wheel tools",
                    lines=(
                        "Listen: hear the next chamber; only you learn it",
                        "Spin: reload, back to one in six",
                        "Pass: hand the gun on without pulling",
                        "Eject: drop the next chamber for everyone to see",
                        "Breaker chainsaw: the next shot is a scattergun. At "
                        "yourself, an empty chamber pays double and a live one "
                        "costs two skins; at a rival, an empty chamber costs you 1 "
                        "salt and a live one costs them a skin and the chamber's "
                        "salt, undoubled",
                    ),
                ),
                HelpBlock(
                    title="The Sunken Bell: one bell, one tank",
                    lines=(
                        "Each round choose in secret: stay in, go out 1 to 3 "
                        "minutes, or go up with your bag",
                        "Divers come back shortest first; when the air runs short, "
                        "that whole group is cut off",
                        "A spare bottle saves you once for half your load; each "
                        "diver may read the gauge exactly once",
                        "Reach level 7 and everyone aboard takes 12 more; an empty "
                        "tank halves every bag",
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

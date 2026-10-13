<div align="center">

<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo/bot-logo-wordmark-light.png">
    <img src="assets/logo/bot-logo-wordmark.png" alt="BOT." width="320">
  </picture>
</h1>

**一隻會顧門、會招呼客人、還會順手收拾的 Discord 機器人。**

防洗版與管理、歡迎與自動身分組、臨時語音、工單、小遊戲與成就、osu!／HoYoLAB／GitHub 整合、檔案工具，<br>
以及一個可以在網站上完成設定的儀表板。

[![CI](https://github.com/keeiv/bot/actions/workflows/ci.yml/badge.svg)](https://github.com/keeiv/bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776AB)
![discord.py](https://img.shields.io/badge/discord.py-2.7-5865F2)
![License](https://img.shields.io/badge/license-AGPL--3.0--only-F99549)

[網站與儀表板](https://botweb.shizune.life) ·
[功能一覽](#功能一覽) ·
[快速開始](#快速開始) ·
[開發指南](docs/DEVELOPMENT.md) ·
[文件導覽](docs/Home.md)

</div>

## 目錄

- [功能一覽](#功能一覽)
- [快速開始](#快速開始)
- [終端機控制台（Windows）](#終端機控制台windows)
- [權限](#權限)
- [資料與儲存](#資料與儲存)
- [專案結構](#專案結構)
- [授權](#授權)

## 功能一覽

| 範圍 | 做什麼 | 主要指令 |
| --- | --- | --- |
| 防護與管理 | 七種洗版偵測、自動加重處分、黑名單與申訴、舉報、訊息與審計日誌 | `/anti_spam` `/blacklist` `/appeal` `/clear` `/kick` `/ban` `/mute` `/warn` |
| 迎接新成員 | 歡迎訊息範本、自動身分組、年齡守門 | `/welcome` `/auto_role` `/age_guard` |
| 伺服器服務 | 工單、臨時語音、抽獎、身分組與表情符號、伺服器設定面板 | `>>>ticket` `/temp_voice` `/giveaway` `/role` `/emoji` `/settings` |
| 遊戲與成就 | 兩款雙人小遊戲、18 個成就 | `/deep-sea-oxygen` `/russian-roulette` `/achievements` |
| 帳號整合 | osu!、HoYoLAB／米游社、GitHub 倉庫通知 | `/osu` `/mhy` `/repo_watch` `/repo_track` |
| 工具 | 檔案轉換與壓縮（NovaGrid）、訊息翻譯 | `/convert` `/compress` `/usage` `翻譯訊息` |
| 語言 | 英文與中文介面，伺服器與個人各自設定 | `/language` |

下面依範圍列出完整內容。

> [!TIP]
> 在 Discord 輸入 `/help` 可以查看多頁說明；歡迎訊息、防洗版、工單等設定也能在[網站儀表板](https://botweb.shizune.life)完成。

### 防護與管理

**防洗版**：`/anti_spam` 群組有 11 個子指令（`setup`、`flood`、`duplicate`、`mention`、`link`、`raid`、`escalation`、`whitelist`、`lockdown_off`、`status`、`mute_duration`）。

| 偵測 | 預設門檻 | 預設處理 |
| --- | --- | --- |
| 洪水 | 10 秒內超過 10 則訊息 | 禁言 |
| 重複內容 | 30 秒內同樣內容 4 次 | 刪除訊息 |
| 大量提及 | 單則訊息 8 次提及 | 禁言 |
| 連結 | 15 秒內 5 個連結（Discord 邀請連結直接刪除） | 刪除訊息 |
| 表情 | 單則訊息 20 個表情 | 刪除訊息 |
| 換行 | 單則訊息 30 個換行 | 刪除訊息 |
| 突襲 | 30 秒內 10 人加入 | 封鎖頻道 |

處理方式共六種：警告、刪除訊息、禁言、踢出、封禁、封鎖頻道。10 分鐘內累計 3 次違規，會比這次最重的處分再升一級（最高到封鎖頻道）。洪水、重複、提及、連結與突襲的門檻可調整，也能設定白名單身分組與頻道；表情與換行目前使用預設門檻。

**黑名單與申訴**：`/blacklist add`／`remove`／`list`／`info` 管理本地黑名單並查詢 CatHome API（開發者限定）。被擋下的使用者可用 `/appeal` 提交、`/appeal_status` 查詢，由開發者審核；提交時沿用原本的封鎖原因，沒有另外填寫的表單。接受申訴只會移除本地黑名單，CatHome API 的封鎖仍須由對方解除。詳見 [黑名單指南](BLACKLIST_GUIDE.md)。

**舉報**：右鍵訊息 → 應用程式 → `舉報訊息`（英文介面為 `Report message`），送到 `/report_channel set` 設定的頻道；管理員可直接按按鈕禁言、封禁或警告，每個動作都附表單。`/report_channel status` 查看目前設定。

**日誌**：`/message_log_settings` 指定頻道，記錄機器人快取得到的非機器人成員訊息編輯與單筆刪除，範圍與限制見 [訊息日誌指南](MESSAGE_LOGGER_README.md)。審計日誌記錄成員加入／離開、語音異動、身分組與暱稱變更，以及頻道建立、刪除與修改。

**管理指令**：`/clear` 清除訊息、`/kick` 踢出、`/ban` 封禁、`/mute` 禁言、`/warn` 警告。

### 迎接新成員

- **歡迎訊息**：`/welcome setup` 設定頻道與範本，可用 `{user}`、`{server}`、`{count}`；`/welcome templates` 列出內建範本、`/welcome preview` 預覽、`/welcome disable` 停用。
- **自動身分組**：`/auto_role setup`／`list`／`remove` 管理加入時自動給予的身分組規則。
- **年齡守門**：從訊息中的「數字 + 歲」辨識未成年的年齡宣告，依設定移除成人身分組並加入指定身分組。`/age_guard set_adult_role`、`set_punishment_role`、`toggle`、`status`。

### 伺服器服務

- **工單**：`>>>ticket setup #頻道 @身分組` 建立面板。成員按「開啟工單」會建立私人討論串並通知工作人員身分組；可直接關閉或附原因關閉，討論串會鎖定保留紀錄。
- **臨時語音**：`/temp_voice setup` 設定觸發頻道、類別與名稱範本（預設 `{username}的家`），`status` 查看、`disable` 停用。成員加入觸發頻道就會得到自己的語音頻道，人都離開後自動刪除。房主可用 `envc*` 前綴指令管理：

  | 類型 | 指令 |
  | --- | --- |
  | 基本設定 | `envc*name`、`envc*limit`、`envc*bitrate` |
  | 隱私 | `envc*hide`／`unhide`、`envc*lock`／`unlock` |
  | 成員 | `envc*kick`、`envc*ban`／`unban` |
  | 房主 | `envc*transfer`、`envc*claim` |

- **抽獎**：`/giveaway start`（時長可寫 `1d12h30m`）、`end` 提前結束、`reroll` 重抽、`list` 列出；按按鈕參加，到期自動開獎。
- **身分組與表情符號**：`/role assign`／`remove`、`/emoji get`／`upload`。
- **設定面板**：`/settings` 用選單和按鈕查看與修改日誌頻道、舉報頻道、防洗版與歡迎訊息。
- **機器人外觀**：`/bot_appearance name` 改伺服器暱稱，`reset` 還原頭像或橫幅。`avatar`／`banner` 的圖片在設定 [AI 圖片審核節點](docs/image-review.md) 後，先由三個本地模型依序審核；AI 無法判定或未設定時，由開發者人工審核。

### 遊戲與成就

- `/deep-sea-oxygen` 深海氧氣瓶：雙人合作回合制，共享氧氣與道具。
- `/russian-roulette` 俄羅斯輪盤：雙人對戰，籌碼與道具。
- 成就共 18 個（普通 6、少見 7、稀有 5），涵蓋聊天、遊戲與社交。`/achievements` 查看進度，`/achievement_codex` 看全部成就，`/achievement_info` 看單一成就。

### 帳號整合

- **osu!**：`/osu bind`／`unbind` 綁定帳號，`/osu best`、`/osu recent` 查成績，`/user_info_osu` 查玩家資料。
- **HoYoLAB／米游社**：支援原神、崩壞：星穹鐵道、絕區零與崩壞3（深境螺旋等挑戰紀錄僅前三者），國際服與國服皆可。
  - 帳號：`/mhy bind` 綁定（Cookie 加密保存）、`unbind`、`status`、`tutorial` 取得 Cookie 的教學。
  - 日常：`/mhy toggle_autosignin` 每日自動簽到、`checkin` 手動簽到、`notes` 查便箋、`redeem` 兌換禮包碼。
  - 紀錄：`/mhy stats` 遊戲統計、`/mhy abyss` 挑戰紀錄。
- **GitHub**：`/repo_watch set`／`status`／`disable` 監控任意倉庫的提交；`/repo_track add`／`remove`／`status` 追蹤 keeiv/bot 的新提交與新開的 PR（不追蹤 PR 合併）。使用 `GITHUB_TOKEN`、共用快取與 ETag，遇到限流會依重試時間暫停。

### 工具

**檔案工具**

| 指令 | 用途 |
| --- | --- |
| `/convert` | 靜態圖片轉 PNG／JPG／WebP／PDF；UTF-8 CSV／TSV／JSON 平面表格互轉 |
| `/compress` | 用 NovaGrid 引擎壓縮圖片，可設定品質與最大尺寸；沒有變小就不扣點 |
| `/usage` | 等級、週用量與近三小時用量圖 |
| `/ir` | 重置券背包與使用紀錄 |

- 全部免費，點數只用來管理用量。首次使用即有 Free. 額度，使用滿 30 天升 Run.、60 天 Dash.、120 天 Grow.、180 天 Ultra.。
- 網站 `/tools` 與 Discord 共用同一份額度；網站或 `!convert [format]` 可依等級批次處理。
- 處理工作可以分給區網內另一台電腦。詳見 [檔案工具](docs/file-tools.md)、[NovaGrid 引擎](docs/novagrid.md)、[區網處理節點](docs/tool-worker.md)。

**翻譯**：右鍵訊息 → 應用程式 → `翻譯訊息`（英文介面為 `Translate message`），可選 14 種語言：繁體中文、簡體中文、英文、日文、韓文、法文、德文、西班牙文、俄文、葡萄牙文、泰文、越南文、印尼文、阿拉伯文。

### 語言（English／中文）

- 斜線指令名稱一律是英文；指令說明、參數與右鍵選單依 Discord 用戶端語言顯示英文或中文。
- 回覆、選單、按鈕與表單都有英文與中文兩版。在機器人所在的伺服器依伺服器語言；在私訊，或在機器人沒有加入的伺服器以個人應用程式使用時，依個人設定，沒有設定時依 Discord 用戶端語言。
- 新加入的伺服器預設英文，並建立 `#bot-guide` 說明頻道，可在選單切換語言（需「管理伺服器」權限）；功能上線前已加入的伺服器維持中文。
- `/language`：在機器人所在的伺服器切換伺服器語言（需「管理伺服器」權限），在私訊或個人應用程式中切換個人語言。

> [!NOTE]
> - 尚未翻譯：網站儀表板 API 的回應（維持中文以相容網站）、本機命令列工具，以及日誌。
> - 程式已標記可在個人應用程式使用的指令（`/help`、`/language`、`/osu`、`/user_info_osu`、`/mhy`、`/convert`、`/compress`、`/usage`、`/ir`、`翻譯訊息`）；要在 Discord Developer Portal 開啟 User Install 後才會出現。

### 網站儀表板

[botweb.shizune.life](https://botweb.shizune.life) 用 Discord 登入，選擇自己有管理權限的伺服器後，可以設定歡迎訊息、防洗版、年齡守門、臨時語音、工單、GitHub 通知與審計日誌，執行設定檢查與面板部署，也能查看機器人的即時狀態與 24 小時／7 天歷史。網站透過 Cloudflare Tunnel 呼叫機器人的本機 API，不直接連線資料庫。

### 其他

- `/help` 多頁說明，`/user_info` 查看使用者（含 osu! 綁定與成就進度），`/server_info` 查看伺服器。
- 指令錯誤統一處理：權限不足、冷卻中、參數錯誤等會以使用者的語言回覆；未預期的錯誤記錄到指定的錯誤頻道與終端機。
- 開發者專用：`/dev-status`（也有 `!dev-status`）、`>>>info` 開發者面板，以及檔案工具的測試等級與重置指令（見 [檔案工具](docs/file-tools.md)）。

## 快速開始

需要 Python 3.10 以上（目前部署使用 3.13）。

> [!IMPORTANT]
> **全新安裝請先使用 JSON 相容模式**（`STORAGE_BACKEND=json`）。MySQL 模式啟動前必須先完成資料搬移，而搬移工具只能從 `data/` 底下既有的 JSON／SQLite 資料搬移；目前還沒有直接建立空白 MySQL 資料庫的流程。正式環境使用 Oracle MySQL 8.4。

**開發者快速安裝**：`install.py` 從 GitHub 取得專案並完成開發環境的基本配置：檢查環境、取得程式碼（沒有 git 時改下載 ZIP）、建立虛擬環境、安裝依賴、建立空白的 `.env`，最後確認套件都能匯入。只使用 Python 內建功能。

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/keeiv/bot/main/install.py -OutFile install.py
python install.py
```

```bash
# Linux／macOS
curl -O https://raw.githubusercontent.com/keeiv/bot/main/install.py
python3 install.py
```

常用選項：`--dir` 指定安裝資料夾、`--test` 安裝後執行全部測試、`--no-dev` 不安裝開發工具、`--check` 只檢查環境、`--plain` 以純文字輸出、`--yes` 不詢問直接開始；完整選項見 `python install.py --help`。

> [!NOTE]
> 已安裝的資料夾再次執行會改為更新，不會更動 `.env` 與虛擬環境。安裝程式不會詢問或寫入任何密鑰，`DISCORD_TOKEN` 需要自行填入 `.env`。

以下是手動安裝的步驟。

**1. 安裝**

```bash
python -m venv .venv
```

啟用虛擬環境（Windows PowerShell：`.\.venv\Scripts\Activate.ps1`；Linux／macOS：`source .venv/bin/activate`）後安裝：

```bash
python -m pip install -r requirements.txt
```

**2. 設定 `.env`**（放在專案根目錄，不納入 Git）

```env
DISCORD_TOKEN=
OSU_CLIENT_ID=
OSU_CLIENT_SECRET=
GITHUB_TOKEN=
BLACKLIST_API_KEY=
GENSHIN_ENCRYPTION_KEY=
STORAGE_BACKEND=json
STORAGE_ROOT=
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=
BOT_API_ENABLED=false
BOT_API_HOST=127.0.0.1
BOT_API_PORT=8080
BOT_API_SECRET=
```

> [!WARNING]
> `.env` 含有 Discord Token、各項 API 金鑰、加密金鑰與資料庫密碼，已列在 `.gitignore`，不要提交，也不要貼到公開的地方。

> [!CAUTION]
> 已經有加密帳號時，必須沿用原本的 `GENSHIN_ENCRYPTION_KEY`；缺少時服務會停止初始化，不會用新金鑰覆蓋。全新安裝會產生並保存這把金鑰。

<details>
<summary>各項設定說明</summary>

- `STORAGE_ROOT` 可設為專案的絕對路徑；不設定時以啟動目錄為準，所以要從專案根目錄執行。
- `STORAGE_BACKEND` 只接受 `json` 或 `mysql`（不寫這一行等同 `json`，但不能留空白值）。完成第 3 步的搬移後再改為 `mysql`。MySQL 的資料庫與專用帳號要先建立，帳號需能建表與讀寫；使用 JSON 模式時 `MYSQL_*` 可以不填。
- 要讓網站連線，設定 `BOT_API_ENABLED=true` 與至少 32 字元的 `BOT_API_SECRET`。

</details>

**3. 改用 MySQL：從既有資料搬移（只需要一次，使用 JSON 模式時略過）**

> [!WARNING]
> 請先停止機器人，再執行搬移。

```bash
python -m src.migrate_storage
```

會先備份並核對 JSON／SQLite 來源、每份文件與各資料表，全部通過才寫入驗證標記；原檔不刪除，目的地有衝突就中止。Windows 的備份在 `%LOCALAPPDATA%\NewBotMySQL\backups`。MySQL 模式啟動前會檢查這個標記。

**4. 啟動**

```bash
python -m src.main
```

## 終端機控制台（Windows）

```bash
python -X utf8 -m src.control_panel
```

在同一個畫面啟動、停止與重新啟動機器人，查看運行狀態、資料庫連線與日誌，也能執行依賴安裝、測試與格式檢查，以及設定區網節點。操作方式與資料庫實例的處理見 [開發指南](docs/DEVELOPMENT.md#終端機控制台)。

## 權限

| 功能 | 需要的權限 |
| --- | --- |
| `/clear` | 管理訊息 |
| `/kick`、`/ban` | 踢出成員、封禁成員 |
| `/mute`、`/warn` | 禁言成員 |
| `/message_log_settings`、`/bot_appearance`、`>>>ticket setup` | 管理員 |
| `/anti_spam`、`/age_guard`、`/giveaway`、`/settings` | 預設只有管理員能用（Discord 指令的預設權限，伺服器可在「整合」設定裡調整） |
| `/report_channel set`／`status`、`/repo_watch set`／`disable` | 管理伺服器 |
| 用 `/language` 或 `#bot-guide` 切換機器人所在伺服器的語言（查詢目前語言、切換個人語言不需要） | 管理伺服器 |
| `/welcome setup`／`disable`、`/temp_voice`、`/repo_track add`／`remove` | 管理頻道 |
| `/role`、`/auto_role setup`／`remove` | 管理身分組 |
| `/emoji upload` | 管理表情符號 |
| `/blacklist`、開發者指令 | 開發者限定 |
| 其他指令，例如遊戲、成就、osu!、HoYoLAB、翻譯、檔案工具、`/repo_watch status`、`/repo_track status`、`/welcome templates`／`preview` | 不需要特殊權限 |

## 資料與儲存

| 位置 | 內容 |
| --- | --- |
| MySQL `documents` | 以原本的檔案路徑為鍵保存完整 JSON 與 SHA-256 校驗值：設定、成就、黑名單、osu! 綁定、加密帳號等 |
| MySQL `samples`、`cache_entries`、`metrics`、`audit_logs` | 運作歷史、快取、指標與審計資料 |
| MySQL `migration_sources`、`migration_state` | 搬移來源副本與驗證標記 |
| `data/logs/runtime.log` | 執行日誌，經背景佇列寫入，避免卡住 Discord 心跳 |
| `.env` | 連線資訊與加密金鑰，不納入 Git |

> [!NOTE]
> MySQL 模式不會寫回舊的 JSON／SQLite，資料庫失敗時也不會退回舊檔；保留的原檔只是搬移時的快照。

本機 MySQL 使用 `127.0.0.1:3307`，資料在 `%LOCALAPPDATA%\NewBotMySQL\data`。設定好 `start-mysql.ps1` 時，機器人啟動也會順便啟動尚未執行的本機資料庫（不適用遠端資料庫）。

> [!NOTE]
> 時間：Discord 日誌與介面顯示 UTC+8；GitHub 等外部資料與部分診斷使用 UTC，內部也使用 Unix 時間戳。

## 專案結構

```text
src/
  main.py               啟動入口
  bot.py                Bot、全域黑名單檢查與 Cog 自動載入
  cogs/core/            錯誤處理、設定、日誌、黑名單、外觀、語言、儀表板 API
  cogs/features/        防洗版、工單、臨時語音、抽獎、整合與檔案工具等功能
  cogs/games/           小遊戲
  services/             業務規則與資料保存，以及 NovaGrid、區網節點、圖片審核
  locales/              英文與中文的訊息目錄
  utils/                儲存、背景工作、翻譯與共用工具
  control_panel/        Windows 終端機控制台
services/               獨立外部整合（GitHub 客戶端、osu! API）
tests/                  自動化測試（CI：Python 3.10–3.13 與 MySQL 8.4）
docs/                   說明文件
```

<details>
<summary>主要依賴</summary>

版本由 `pyproject.toml` 統一管理；`requirements.txt` 安裝執行環境，`requirements-dev.txt` 安裝開發工具。

| 套件 | 用途 |
| --- | --- |
| discord.py | Discord Gateway、指令、事件與互動元件 |
| aiohttp | 非同步 HTTP 客戶端與儀表板 API |
| PyMySQL | MySQL 連線 |
| Pillow | 圖片轉換與 NovaGrid 壓縮 |
| ossapi | osu! API v2 |
| genshin、cryptography | HoYoLAB／米游社整合與 Cookie 加密 |
| deep-translator | 訊息翻譯 |
| psutil | 系統資源監控 |
| python-dotenv | 讀取 `.env` |
| rich | 終端機控制台畫面 |

</details>

想參與開發，先讀 [開發指南](docs/DEVELOPMENT.md) 與 [貢獻指南](CONTRIBUTING.md)；安裝、設定、部署與排查見 [文件導覽](docs/Home.md)。

## 授權

Copyright (c) 2026 Keeiv。

採用 **GNU Affero General Public License v3.0 only（AGPL-3.0-only）**，條文見 [LICENSE](LICENSE)，著作權聲明見 [NOTICE](NOTICE)。可以複製、修改、散布與商業使用；修改後透過網路提供服務時，須讓使用者能免費取得該版本完整的對應原始碼。原始碼不包含部署密鑰或使用者資料。

> [!NOTE]
> 這次授權變更不追溯取代已發布版本的 MIT 授權，舊聲明保留於 [LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt)。第三方元件保留各自的授權與著作權聲明。

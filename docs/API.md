# Discord 指令與儀表板 API

Discord 功能與現有指令見 [README](../README.md#主要功能)，完整參數以 Cog 的 `app_commands`／文字指令宣告為準。一般文字前綴為 `!`；部分功能使用專用前綴。osu! 綁定指令是 `/osu_bind`、`/osu_unbind`，不是另一套 `/osu bind` 子指令。

## 儀表板 HTTP API

實作見 [`DashboardAPI.create_app()`](../src/cogs/core/dashboard_api.py)。API 預設不啟用；本機預設位址為 `127.0.0.1:8080`。啟用設定見 [Configuration.md](Configuration.md)。

所有路由都需要共享密鑰，使用 `Authorization: Bearer ...`，或相容的 `X-Bot-Secret`。若提供 Authorization，會優先驗證該值。密鑰只放網站伺服器環境，不放瀏覽器程式。沒有驗證時回傳 401；Bot 尚未就緒時，除狀態路由外回傳 503。

| 方法 | 路由 | 用途 |
| --- | --- | --- |
| GET | `/guilds` | 伺服器清單 |
| GET | `/status` | 公開安全欄位的即時運作狀態 |
| GET | `/status/history` | 運作歷史 |
| GET／POST | `/account` | 個人綁定查詢及修改 |
| GET | `/guilds/{guild_id}/resources` | 頻道與角色 |
| POST | `/guilds/{guild_id}/checks` | 設定檢查 |
| GET／PATCH | `/guilds/{guild_id}/settings` | 讀取或保存一個設定區段 |
| POST | `/guilds/{guild_id}/panel` | 部署工單面板 |

個人資料與單一伺服器操作還需要 `X-Discord-User`。網站伺服器須從已驗證登入取得使用者 ID；管理路由會再次向 Discord 查詢成員並檢查 `manage_guild`。

PATCH 設定請求包含 `section`、`values` 與先前讀取的 `revision`；版本衝突回傳 409，參數錯誤回傳 400。設定資料寫入與保存交由公開 Service 方法完成，設定文件只接受該區段宣告的欄位。

程式介面與儲存模式見 [API-Reference.md](API-Reference.md)。

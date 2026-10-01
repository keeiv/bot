# 程式介面導覽

以下只列現有程式的主要介面；實際參數與完整行為以對應原始碼為準。Discord 指令與 HTTP 路由見 [API.md](API.md)。

## 入口

- [`src/main.py`](../src/main.py)：`main()` 檢查設定、準備儲存並執行 Bot。
- [`src/bot.py`](../src/bot.py)：`setup_hook()` 初始化；`load_cogs()` 自動掃描 `src/cogs`，不使用手動列表。
- [`src/migrate_storage.py`](../src/migrate_storage.py)：`migrate(root, backup)` 備份並核對資料；命令列入口為 `python -m src.migrate_storage`。

## 業務 Service

[`ManagementService`](../src/services/management_service.py) 提供 `get_guild_config()`、`get_tracked_repos()`、`add_tracked_repo()`、`remove_tracked_repo()`、`get_welcome_config()`、`set_welcome_config()`、`update_welcome_config()`、`clear_welcome_config()`、`get_auto_roles()`、`add_auto_role()` 與 `remove_auto_role()`。規則刪除使用從 1 開始的索引；不存在回傳 `None`。查詢回傳獨立副本。

[`GithubWatchService`](../src/services/github_watch_service.py) 管理通用 GitHub 訂閱；`update_config()` 保存設定，`record_commit()` 驗證輪詢前設定仍然相同後更新進度。

[`DashboardService`](../src/services/dashboard_service.py) 將公開網站欄位映射為 Service 的設定欄位，並驗證頻道、身份組與參數；`read()`／`write()` 使用公開 Service 方法，不直接改 Cog 快取。

其他 Service 見 [`src/services`](../src/services)；共用防刷屏管理器位於 [`src/utils/anti_spam.py`](../src/utils/anti_spam.py)。Cog 不應呼叫私有保存方法或自行修改設定副本後期望自動保存。

## 儲存與背景工作

[`document_store`](../src/utils/document_store.py)：`read_document(path)`、`write_document(path, data)`、`document_exists(path)` 與現有的 `open_document()` 相容介面。`StorageError` 表示儲存失敗，不能捕捉後當作空資料繼續寫入。

MySQL 模式的文件路徑是資料鍵，不是對本機 JSON 的寫入路徑。JSON 模式才使用實體檔案。詳見 [Configuration.md](Configuration.md)。

[`storage_worker`](../src/utils/storage_worker.py)：`await run_storage(function, *args, **kwargs)` 在背景序列化同步儲存工作；完整讀取、修改與保存須放在同一個呼叫內。

[`DatabaseManager`](../src/utils/database_manager.py) 提供非同步快取、指標與審計存取；連線池限制數量、等待逾時並淘汰失效連線。

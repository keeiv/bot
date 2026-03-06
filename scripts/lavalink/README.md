Lavalink 測試安裝說明

此資料夾包含 Lavalink 的簡易啟動範例（用於測試提交），並非強制在專案中啟用音樂功能。

提供兩種啟動方式：

- PowerShell（Windows）：`start-lavalink.ps1` 會自動下載 Lavalink.jar（若尚未下載）並啟動。
- Docker Compose：`docker-compose.yml` 範例會在容器啟動時下載 Lavalink.jar 並執行。

預設密碼與埠都在 `application.yml.sample` 中，可先複製為 `application.yml` 並修改密碼與網路設定。

注意事項：
- 需安裝 Java 17+（或在容器中使用 openjdk）。
- 這些檔案僅為測試/範例用途，正式部署請參考 Lavalink 官方文件與安全性設定。

測試提交說明：此變更為測試性提交，用於在 `beta` 分支驗證 CI/部署流程是否接受新增腳本。

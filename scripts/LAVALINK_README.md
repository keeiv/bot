Lavalink 測試說明
===================

此檔案包含如何在本機或測試環境啟動 Lavalink 節點並用於開發測試的說明。

快速步驟：

1. 安裝 Java 11+（Lavalink 需要 Java）
2. 下載 Lavalink.jar 並設定 `application.yml`（或使用預設）
3. 啟動 Lavalink：
   `java -jar Lavalink.jar`
4. 在專案中安裝 Python 客戶端：
   `pip install -r requirements.txt`（我們已加入 `wavelink`）
5. 設定環境變數：
   - `LAVALINK_HOST`（預設 127.0.0.1）
   - `LAVALINK_PORT`（預設 2333）
   - `LAVALINK_PASSWORD`（預設 youshallnotpass）

專案中已新增檔案：`src/utils/lavalink_node.py`（示範連線程式，僅作測試用途，非完整播放實作）。

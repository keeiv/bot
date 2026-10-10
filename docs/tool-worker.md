# 區域網路檔案處理節點

主機保留 Discord 連線、網站 API、MySQL 與用量帳本；獨立節點執行現有 NovaGrid 圖片壓縮、圖片／表格轉換與批次 ZIP 輸出。節點不需要機器人、網站或資料庫憑證。

## 建立與啟用

在主機的專案目錄執行，IP 須替換為兩台電腦的實際區網 IPv4：

```powershell
.venv\Scripts\python.exe -X utf8 -m src.tool_worker_setup build --worker-ip 192.168.1.20 --main-ip 192.168.1.10
```

套件輸出至 `data/worker-packages/novagrid-worker-*.zip`，主機配對設定為 `.file-tools-worker.json`。上述檔案包含專用連線金鑰，不納入 Git。建立時預設停用分工，不覆蓋既有配對設定。重新配對可用全域 `--config` 參數指定另一份設定檔；機器人使用非預設設定檔時，須設定 `FILE_TOOLS_WORKER_CONFIG`。

套件內附 Windows x64 Python 3.14.8、Pillow 12.3.0、aiohttp 3.14.4，以及所需的相依套件。Python 下載來自固定官方 HTTPS URL，並核對官方發布的 SHA-256；不依賴舊電腦現有 Python。套件也包含本版本處理程式原始碼、LICENSE 與相依套件授權資訊。

舊電腦操作：

1. 解壓縮整個套件至固定位置。
2. 以系統管理員身分執行 `setup_firewall.cmd`，建立僅允許主機 IP 連入指定程式與 TCP 8787 的防火牆規則。
3. 以一般使用者身分執行 `start_worker.cmd`，保持電腦開機、停用睡眠。

主機執行：

```powershell
.venv\Scripts\python.exe -X utf8 -m src.tool_worker_setup check
.venv\Scripts\python.exe -X utf8 -m src.tool_worker_setup enable
```

`check` 驗證 HTTPS、授權、引擎原始碼校驗與實際透明圖片轉換，不建立用戶帳本紀錄或扣點。`enable` 會重新完成相同驗證，通過後才修改配對設定。重啟機器人後啟用分工。亦可使用本機 `run_bot.bat` 的 `[W] LAN file-worker settings` 選單完成檢查與切換。

兩台電腦的位址變更時須更新配對與防火牆設定，建議在路由器設定 DHCP 位址保留。VPN 須允許區網連線；同一 Wi-Fi 的裝置隔離也可能阻擋連線。此服務使用區網位址，不需要路由器轉發埠號或另外建立 Tunnel。

## 執行限制與結算

- HTTPS 使用固定 SHA-256 憑證校驗，不關閉 TLS 驗證，也不跟隨 HTTP 重新導向。
- 節點使用獨立的 256 位元連線金鑰，只接受配對主機及本機回環來源。引擎校驗包括 `novagrid.py` 與 `tool_worker.py` 的實際內容，避免版本名稱相同、內容卻不同的情況。
- 每批 1～16 件，輸入／輸出各最多 64 MiB。主機依原有等級、檔案大小及額度核對後才預留點數，節點再次驗證輸入上限。
- 節點一次一件工作。主機最多保留兩件排隊或處理工作，遠端請求含傳輸最多 120 秒。主機從預留前起計算 240 秒的總截止時間，包含準備檔案與排隊，低於 300 秒的額度預留有效期；檔案準備超過截止時間時，不再送出處理請求。
- 處理程序沿用各等級的時間上限。Windows 工作程序採較低優先權；逾時、服務關閉或請求中斷時，終止並等待該程序結束。
- 原始檔採串流傳送並使用節點自行產生的暫存檔名。結果以大小與 SHA-256 核對，核對失敗不開放下載。節點暫存目錄在請求結束後清除，主機下載結果仍保留 20 分鐘。
- 點數沿用檔案大小與工作程序實際處理時間，排隊及網路傳輸不計點。節點離線、傳輸失敗、處理失敗或超時會釋放預留，不自行轉回主機進行圖片編碼。資料庫交易結果尚待核對時，仍沿用既有結算重試機制。

更新引擎後，須同步套件中的原始碼並重新啟動處理節點；內容不一致時，主機會拒絕使用該節點。

## 恢復主機處理

```powershell
.venv\Scripts\python.exe -X utf8 -m src.tool_worker_setup disable
```

重啟機器人後恢復本機處理，帳號、年資、用量、重置券與 JSON 資料保持原樣。網站 API 位址沿用主機原本的設定。

驗證：`pytest tests/test_tool_remote.py tests/test_file_tools.py`。測試使用回環 HTTPS、臨時憑證與臨時帳本，不連線到正式資料庫。

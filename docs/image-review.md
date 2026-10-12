# AI 圖片審核節點

`/bot_appearance avatar` 與 `/bot_appearance banner` 上傳的圖片，先交給另一台電腦上的本地 AI 模型審核。只有 AI 無法給出結果時，才改用原本的開發者人工審核。這個節點與 NovaGrid 檔案處理節點互相獨立：各自的套件、金鑰、憑證與埠號（審核節點用 TCP 8788）。

## 審核流程

每張圖片依序經過三個階段，三個都是 Ollama 上的本地視覺模型：

| 階段 | 預設模型 | 下載大小 | 做什麼 |
| --- | --- | --- | --- |
| 1 快速 | `qwen3-vl:2b-instruct` | 1.9 GB | 判斷色情、暴力、違反 Discord 規範的內容 |
| 2 中級 | `qwen3-vl:4b-thinking` | 3.3 GB | 先思考，再找第 1 階段可能遺漏的地方 |
| 3 嚴格 | `qwen3-vl:8b-thinking` | 6.1 GB | 思考後做最後、最嚴格的檢查 |

下載大小取自 [Ollama 模型頁](https://ollama.com/library/qwen3-vl/tags)。三個模型都是同一系列的視覺模型，提示詞放在 `src/services/moderation_protocol.py`。

- 任一階段判定「不安全」就拒絕，後面的階段不再執行。
- 第 1、2 階段「無法確定」會交給下一階段看得更仔細；第 3 階段「無法確定」視為拒絕。
- 三個階段都完成、沒有任何「不安全」，且第 3 階段判定「安全」，才算通過。主機會再核對一次，節點無法只回報「通過」卻缺少階段紀錄。
- 任何一個階段沒有回覆（Ollama 沒在執行、模型逾時、回覆不是有效的判定、圖片讀不出來），整張圖就是「無法判定」，機器人改送開發者人工審核。模型的猜測永遠不會被當成通過。

動態圖片最多取 3 個畫格一起判斷。圖片在送給模型前縮到最長邊 1024 px。

## 機器人端的行為

| 結果 | 機器人做什麼 |
| --- | --- |
| 通過 | 直接套用頭像或橫幅，回覆申請者，並私訊開發者一則紀錄（含圖片） |
| 拒絕 | 不套用，告訴申請者被判定的類別（色情／暴力／違反 Discord 規範），並私訊開發者一則紀錄（不含圖片） |
| 無法判定 | 照舊送出人工審核請求給開發者 |

申請者只看到類別，看不到模型寫的理由。一次最多同時審核兩張圖片；第三張最多等 30 秒，等不到就改人工。節點失敗後的 2 分鐘內，新的申請直接改人工，避免每個人都等到逾時。

每階段的時間上限為 90、180、300 秒。在沒有獨立顯示卡的舊電腦上，思考模型可能需要數分鐘；超過上限就改人工。

## 建立與啟用

在主機的專案目錄執行，IP 換成兩台電腦的實際區網 IPv4：

```powershell
.venv\Scripts\python.exe -X utf8 -m src.moderation_worker_setup build --worker-ip 192.168.1.20 --main-ip 192.168.1.10
```

可用 `--model1`、`--model2`、`--model3` 換掉預設模型（必須是 Ollama 上的視覺模型）。套件輸出至 `data/worker-packages/image-review-worker-*.zip`，主機的配對設定是 `.image-review-worker.json`；兩者都含連線金鑰，不納入 Git。建立時預設不啟用。機器人使用其他設定檔時，設定 `IMAGE_REVIEW_WORKER_CONFIG`。

套件內附 Windows x64 Python 3.14.8（核對官方 SHA-256）、aiohttp、Pillow、rich。

另一台電腦：

1. 解壓縮整個套件至固定位置。
2. 以系統管理員身分執行 `setup_firewall.cmd`，只允許主機 IP 連入 TCP 8788。
3. 執行 `start_review.cmd`，保持視窗開啟。

`start_review.cmd` 啟動後會自動：

- 找不到 Ollama 時安裝它。優先用 `winget install -e --id Ollama.Ollama`；沒有 winget 就從 `https://ollama.com/download/OllamaSetup.exe` 下載，Windows 數位簽章必須有效才會執行，畫面會顯示簽署者。
- 啟動 Ollama（同時只載入一個模型、兩張圖平行處理，適合記憶體較少的電腦）。若 Ollama 已經在系統匣執行，就沿用它，這兩個設定不會套用。
- 下載還沒有的模型，畫面顯示進度。第一次約 11 GB，之後只檢查不重下載。
- 任何一步失敗都會在 30 秒後重試；準備好之前，節點拒絕審核請求，機器人會改人工。

主機驗證與啟用：

```powershell
.venv\Scripts\python.exe -X utf8 -m src.moderation_worker_setup check --quick   # 連線與模型
.venv\Scripts\python.exe -X utf8 -m src.moderation_worker_setup check           # 再實際審核一張測試圖
.venv\Scripts\python.exe -X utf8 -m src.moderation_worker_setup enable
```

`enable` 會先完成完整驗證才修改設定，重啟機器人後生效。`run_bot.bat` 控制台的 `R`（圖片審核工作站）提供相同功能。

## 停用

```powershell
.venv\Scripts\python.exe -X utf8 -m src.moderation_worker_setup disable
```

重啟機器人後，所有申請恢復為人工審核。

## 安全與隱私

- 與 NovaGrid 節點相同：HTTPS 以固定 SHA-256 憑證指紋校驗，256 位元連線金鑰，只接受配對主機與本機回環。節點與主機的審核程式碼必須一致（核對 `moderation_protocol.py`、`moderation_engine.py` 的內容），否則主機拒用。
- 圖片只在記憶體中處理，不寫入節點硬碟，請求結束即丟棄。節點只連線本機的 Ollama（`127.0.0.1`），不經過代理。
- AI 判斷可能有誤，包括誤擋與漏判；機器人會把每個 AI 決定私訊給開發者留存。

驗證：`pytest tests/test_image_review.py`。測試以模擬的 Ollama 扮演三個模型，檢查的是流程、傳輸與退回人工的邏輯，不代表任何模型的判斷品質。

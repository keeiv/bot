# 部署指南

目前部署是 Windows 本機機器人與 Oracle MySQL，加上 Vercel 網站與 Cloudflare Tunnel。專案要求 Python 3.10 以上，目前本機使用 Python 3.13。首次設定見 [Installation.md](Installation.md)。

## 更新程序

1. 檢查變更是否涉及資料、環境變數或依賴；停止機器人後再更新。
2. 更新程式及依賴，保留 `.env`、使用者資料、加密金鑰與備份。
3. 若涉及儲存遷移，依 [README](../README.md#安裝) 備份、搬移與核對。已完成遷移的正常程式更新不必重跑舊快照搬移。
4. 從根目錄執行 `python -m src.main`，確認儲存檢查、Cog 載入及 Discord 登入成功。
5. 啟用儀表板時，檢查網站伺服器與本機 API 的密鑰及 Tunnel API 網址是否一致。

本機啟動流程只有在 Windows、MySQL 主機為本機、連接埠為 3307，且 `%LOCALAPPDATA%\NewBotMySQL\start-mysql.ps1` 存在時，才會嘗試啟動該 Oracle 實例；其他安裝方式需自行啟動資料庫。不要影響另外運行的 XAMPP 資料庫。

`bot.lock` 用於檢查重複程序。先確認記錄的程序是否仍存在，不能直接刪檔並開第二個 Bot。

## 網站與 Tunnel

網站和機器人使用不同倉庫。機器人 Python 修改需要重啟本機 Bot；不會自動部署網站。固定的 Cloudflare Tunnel API 子網域不必每次換網址，但本機資料庫、Bot、Tunnel 程序與網路仍需運行。

## 自動化範圍

[CI](CI-CD.md) 執行測試與品質檢查，不會重啟本機 Bot、部署 Vercel 或自動安裝 MySQL。本倉庫沒有提供可依循的 Dockerfile、容器映像發布流程或 `scripts/deploy.py`；部署命令以目前存在的模組入口為準。

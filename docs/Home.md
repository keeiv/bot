# 專案文件

Discord 機器人的功能與技術棧見 [README](../README.md)。目前部署使用 Python 3.13、discord.py 與 Oracle MySQL 8.4；專案最低 Python 版本為 3.10。

## 接手順序

1. [安裝與啟動](Installation.md)：虛擬環境、環境變數與入口。
2. [設定與儲存](Configuration.md)：JSON 相容模式與 MySQL 正式儲存。
3. [開發指南](DEVELOPMENT.md)：目錄、Cog 自動載入與 Service 界線。
4. [貢獻指南](../CONTRIBUTING.md)：測試、品質檢查與提交規範。

## 操作與參考

- [部署](DEPLOYMENT.md)
- [CI](CI-CD.md)
- [故障排查](Troubleshooting.md)
- [程式介面](API-Reference.md)
- [Discord 指令與儀表板 API](API.md)

`docs/audits/` 是當時版本的歷史稽核與證據，不能當作目前安裝或設定指南。版本與依賴以 `pyproject.toml` 及 CI 工作流程為準。

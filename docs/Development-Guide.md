# 開發指南入口

開發流程集中在 [DEVELOPMENT.md](DEVELOPMENT.md)，避免兩份指南各自描述不同的載入方式與版本要求。

- Python 最低版本為 3.10；目前本機部署使用 3.13。
- `src/cogs` 自動掃描載入，不需要手動修改載入清單。
- Cog 透過公開 Service 方法修改及保存資料。
- 儲存、測試隔離與提交規範見 [CONTRIBUTING.md](../CONTRIBUTING.md)。

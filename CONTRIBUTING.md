# 貢獻指南

感謝您對本項目的興趣！我們歡迎各種形式的貢獻。

## 開發環境設置

### 前置需求
- Python 3.9+
- Git

### 安裝步驟
1. Fork 本倉庫
2. Clone 您的 fork：`git clone https://github.com/your-username/bot.git`
3. 進入項目目錄：`cd bot`
4. 創建虛擬環境：`python -m venv venv`
5. 啟動虛擬環境：
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`
6. 安裝依賴：`pip install -r requirements.txt -r requirements-dev.txt`

## 代碼風格

### 基本要求
- 使用 Python 3.9+ 語法
- 遵循 PEP 8 基本規範
- 添加適當的註釋和文檔

### 代碼格式化
我們使用以下工具確保代碼質量：
- **Black**: 自動代碼格式化
- **isort**: 導入語句排序
- **flake8**: 代碼風格檢查

```bash
# 格式化代碼
black src/ tests/
isort src/ tests/

# 檢查代碼風格
flake8 src/ tests/
```

## 測試

### 運行測試
```bash
# 運行所有測試
pytest -v

# 運行特定測試
pytest tests/test_bot_startup.py -v
```

### 測試覆蓋率
我們鼓勵為新功能添加測試。運行測試時會自動生成覆蓋率報告。

## 提交流程

### 1. 創建分支
```bash
git checkout -b feature/your-feature-name
```

### 2. 進行更改
- 編寫代碼
- 添加測試
- 確保所有測試通過

### 3. 提交更改
```bash
git add .
git commit -m "feat: add your feature description"
```

### 4. 推送並創建 Pull Request
```bash
git push origin feature/your-feature-name
```

然後在 GitHub 上創建 Pull Request。

## Pull Request 指南

### PR 標題
使用以下前缀：
- `feat:` 新功能
- `fix:` 錯誤修復
- `docs:` 文檔更新
- `style:` 代碼格式化
- `refactor:` 代碼重構
- `test:` 測試相關

### PR 描述
請包含：
- 變更的簡要描述
- 相關問題的編號（如果有）
- 如何測試這些變更
- 截圖（如果適用）

## 代碼語言

### 命名規範
- **函數和變量**: 使用英文命名（推薦）
- **類名**: 使用英文命名（推薦）
- **註釋**: 可以使用中文或英文
- **文檔字符串**: 可以使用中文或英文

### 靈活政策
- 我們理解中文開發者的需求
- 函數和變量名鼓勵使用英文，但不是強制要求
- 註釋和文檔可以使用中文
- 用戶界面文本可以使用中文

## 倉庫結構

```
bot/
├── src/              # 主要源代碼
│   ├── bot.py        # 機器人主程序
│   ├── cogs/         # 機器人功能模組
│   └── utils/        # 工具函數
├── tests/            # 測試文件
├── docs/             # 文檔
├── scripts/          # 腳本工具
└── requirements.txt  # 依賴列表
```

## 發布流程

1. 更新版本號
2. 更新 CHANGELOG.md
3. 創建 release tag
4. GitHub Actions 會自動處理發布

## 社區行為準則

### 我們的承諾
- 對所有貢獻者保持尊重
- 提供友善和包容的環境
- 歡迎新手和經驗豐富的開發者

### 不當行為
- 騷擾或歧視性語言
- 人身攻擊或侮辱
- 發布不當內容

## 獲得幫助

如果您需要幫助：
1. 查看現有的 Issues
2. 創建新的 Issue
3. 在 Discord 社群中提問
4. 查看文檔和 README

## 許可證

通過貢獻代碼，您同意您的貢獻將在與項目相同的許可證下發布。

## 感謝

感謝所有為本項目做出貢獻的開發者！您的貢獻讓這個項目變得更好。

---

**如果您有任何問題，請隨時提問！我們很樂意幫助新貢獻者入門。**

# 底層維護快速參考指南

一份簡明的維護建議快速查找手冊。

## 📋 快速索引

### 按問題類型

| 問題 | 優先級 | 文檔 | 代碼示例 |
|------|--------|------|---------|
| 日誌記錄混亂 | 🔴 高 | MAINTENANCE_SUGGESTIONS.md | MAINTENANCE_IMPLEMENTATION_GUIDE.md |
| 異常捕捉過度通用 | 🔴 高 | CODE_SCAN_SUMMARY.md | MAINTENANCE_IMPLEMENTATION_GUIDE.md |
| 依賴版本未固定 | 🔴 高 | MAINTENANCE_SUGGESTIONS.md | requirements.txt |
| 缺少數據驗證 | 🟡 中 | CODE_SCAN_SUMMARY.md | MAINTENANCE_IMPLEMENTATION_GUIDE.md |
| 無健康檢查 | 🟡 中 | MAINTENANCE_SUGGESTIONS.md | MAINTENANCE_IMPLEMENTATION_GUIDE.md |
| 資源清理不完善 | 🟡 中 | CODE_SCAN_SUMMARY.md | MAINTENANCE_IMPLEMENTATION_GUIDE.md |
| 測試覆蓋不足 | 🟢 低 | MAINTENANCE_SUGGESTIONS.md | - |

### 按受影響文件

| 文件 | 問題數 | 主要問題 |
|------|--------|---------|
| src/main.py | 5 | print() 日誌, 異常捕捉過度通用 |
| src/bot.py | 3 | 日誌記錄, 資源清理 |
| src/utils/blacklist_manager.py | 4 | 異常捕捉過度通用, 驗證不足 |
| src/cogs/features/achievements.py | 8 | 異常捕捉過度通用 |
| src/cogs/features/anti_spam.py | 2 | 異常捕捉過度通用 |
| requirements.txt | 3 | 版本未固定 |

---

## 🚀 快速實施清單

### 第一天（30分鐘 - 關鍵修復）

```bash
# 1. 固定依賴版本
# 編輯 requirements.txt，將以下行：
#     ossapi → ossapi>=0.8.0,<1.0.0
#     psutil → psutil>=5.9.0,<6.0.0
#     aiohttp → aiohttp>=3.8.0,<4.0.0

# 2. 創建日誌系統
# 複製 MAINTENANCE_IMPLEMENTATION_GUIDE.md 中的代碼
# 新建文件: src/utils/logger_system.py

# 3. 提交
git add -A && git commit -m "fix: 基礎維護改進 - 依賴版本固定、日誌系統" && git push
```

### 第二天（2小時 - 異常處理）

```bash
# 1. 更新 src/utils/blacklist_manager.py
# 參考 MAINTENANCE_IMPLEMENTATION_GUIDE.md 的特定化異常示例

# 2. 分別更新其他 Cogs：
#    - src/cogs/features/achievements.py
#    - src/cogs/features/anti_spam.py
#    - src/utils/config_optimizer.py

# 3. 更新 src/main.py 和 src/bot.py
# 從 print() 改為使用 logger

# 4. 測試
python -m pytest tests/ -v

# 5. 提交
git add -A && git commit -m "refactor: 特定化異常捕捉、實施結構化日誌" && git push
```

### 第三天（1.5小時 - 驗證和監控）

```bash
# 1. 實現驗證層
# 複製 MAINTENANCE_IMPLEMENTATION_GUIDE.md 中的 validation.py
# 新建文件: src/utils/validation.py

# 2. 在 Cogs 中集成驗證
# 主要修改: src/cogs/core/blacklist.py

# 3. 實現健康檢查
# 複製 MAINTENANCE_IMPLEMENTATION_GUIDE.md 中的 health_check.py
# 新建文件: src/utils/health_check.py

# 4. 集成到 Bot
# 修改: src/bot.py（見 MAINTENANCE_IMPLEMENTATION_GUIDE.md）

# 5. 提交
git add -A && git commit -m "feat: 添加驗證層和健康檢查系統" && git push
```

---

## 📊 改進影響矩陣

### 修復依賴版本

**時間:** 5 分鐘  
**風險:** 低  
**收益:** 高  
**影響範圍:** 整個項目  

```bash
# 編輯 requirements.txt
ossapi>=0.8.0,<1.0.0
psutil>=5.9.0,<6.0.0
aiohttp>=3.8.0,<4.0.0
```

---

### 實施日誌系統

**時間:** 1 小時  
**風險:** 低  
**收益:** 高  
**影響範圍:** 全項目  

**前置：**
- 創建 `src/utils/logger_system.py`
- 更新 `src/main.py` 的 print() 語句

**預期成果：**
- ✓ 結構化日誌記錄
- ✓ JSON 格式日誌（用於自動化分析）
- ✓ 日誌文件輪轉
- ✓ 日誌級別區分

---

### 特定化異常捕捉

**時間:** 2 小時  
**風險:** 中  
**收益:** 高  
**影響範圍:** 5+ 個文件

**受影響文件清單：**
1. `src/utils/blacklist_manager.py` (4 處)
2. `src/utils/config_optimizer.py` (1 處)
3. `src/cogs/features/achievements.py` (6 處)
4. `src/cogs/features/anti_spam.py` (2 處)
5. `src/utils/api_optimizer.py` (部分)

**預期成果：**
- ✓ 更清晰的錯誤信息
- ✓ 更容易診斷問題
- ✓ 更好的日誌追蹤

---

### 創建驗證層

**時間:** 1.5 小時  
**風險:** 低  
**收益:** 中  
**影響範圍:** Cog 層

**新建文件：** `src/utils/validation.py`

**使用位置：**
- `src/cogs/core/blacklist.py` - 用戶 ID, 申訴原因, 禁言原因驗證

**預期成果：**
- ✓ 統一的數據驗證
- ✓ 更好的數據完整性
- ✓ 更清晰的驗證錯誤信息

---

### 實施健康檢查

**時間:** 1.5 小時  
**風險:** 低  
**收益:** 中  
**影響範圍:** 機器人核心

**新建文件：** `src/utils/health_check.py`

**核心檢查：**
- Discord 連接狀態
- 內存使用率
- 文件系統可訪問性
- 配置文件完整性

**預期成果：**
- ✓ 自動監控系統健康
- ✓ 及時檢測資源問題
- ✓ 完備的診斷日誌

---

## 🔧 常見任務速查

### 添加新的日誌記錄

```python
from src.utils.logger_system import app_logger

# 簡單日誌
app_logger.info("User added to blacklist")

# 帶上下文信息
app_logger.error(
    "Failed to load blacklist",
    extra={
        'file': self.blacklist_file,
        'error': str(e)
    },
    exc_info=True  # 包含堆棧跟蹤
)
```

### 特定化異常捕捉

```python
# 不好 ❌
try:
    do_something()
except Exception as e:
    print(f"Error: {e}")

# 好 ✓
try:
    do_something()
except FileNotFoundError:
    app_logger.debug("File not found")
except json.JSONDecodeError as e:
    app_logger.error("Invalid JSON", extra={'error': str(e)})
except Exception as e:
    app_logger.critical("Unexpected error", exc_info=True)
```

### 驗證用戶輸入

```python
from src.utils.validation import UserValidator, BlacklistValidator

try:
    user_id = UserValidator.validate_user_id(user.id)
    reason = BlacklistValidator.validate_appeal_reason(reason_text)
except ValidationError as e:
    app_logger.warning(f"Validation failed: {e}")
    await interaction.response.send_message(str(e), ephemeral=True)
```

---

## 📚 文檔導航

### 開始閱讀

1. **新手入門** → `CODE_SCAN_SUMMARY.md` (5分鐘)
2. **詳細建議** → `MAINTENANCE_SUGGESTIONS.md` (15分鐘)
3. **實現代碼** → `MAINTENANCE_IMPLEMENTATION_GUIDE.md` (30分鐘)

### 尋找具體幫助

- 日誌相關？→ MAINTENANCE_IMPLEMENTATION_GUIDE.md (第 1 節)
- 異常捕捉？→ MAINTENANCE_IMPLEMENTATION_GUIDE.md (第 2 節)
- 驗證層？→ MAINTENANCE_IMPLEMENTATION_GUIDE.md (第 3 節)
- 健康檢查？→ MAINTENANCE_IMPLEMENTATION_GUIDE.md (第 4 節)

---

## ✅ 驗證檢查清單

實施完成後，逐項檢查：

- [ ] 所有 print() 都改成 logger 調用
- [ ] 所有 `except Exception` 都改成特定異常
- [ ] 依賴版本號都已固定
- [ ] 驗證層已創建並集成
- [ ] 健康檢查已部署並執行
- [ ] 所有修改都有單元測試
- [ ] 代碼已通過 lint 檢查（flake8, mypy）
- [ ] 變更已記錄在 changelog 中
- [ ] 所有測試通過
- [ ] 代碼已推送到遠端

---

## 🎯 預期時間線

| 階段 | 狀態 | ETA |
|------|------|-----|
| 🔴 高優先級 (3 項) | 未開始 | 3-4h |
| 🟡 中優先級 (3 項) | 未開始 | 4-5h |
| 🟢 低優先級 (3 項) | 未開始 | 4-5h |
| **總計** | - | **11-14h** |

---

## 💬 常見問題

**Q: 我應該從哪裡開始？**  
A: 從依賴版本修復開始（5分鐘），然後實施日誌系統（1小時）。

**Q: 是否可以並行進行？**  
A: 不建議。按順序進行以避免衝突。

**Q: 實施過程中需要停機嗎？**  
A: 不需要。所有改進都是向後兼容的。

**Q: 如何確保質量？**  
A: 在每個步驟後運行測試。見驗證檢查清單。

**Q: 我可以跳過某些項目嗎？**  
A: 高優先級項目必須做。中/低優先級可根據時間調整。

---

**最後更新:** 2026-02-27  
**版本:** 1.0  
**維護者:** GitHub Copilot

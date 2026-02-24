# CI/CD Pipeline

## 概述

本項目使用簡化的 CI/CD 流水線，專注於核心測試功能。

## CI 工作流程

### 主要 CI 工作流程

**文件**: `.github/workflows/ci.yml`

**目的**: 核心持續集成測試

**觸發條件**:
- Pull requests 到 main 分支
- Push 到 main 和 develop 分支
- 手動觸發

**作業配置**:

#### 測試矩陣
```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11']
    os: [ubuntu-latest]
```

#### 作業步驟
1. **環境設置**
   - 檢出代碼
   - 設置 Python 版本
   - 緩存依賴

2. **依賴安裝**
   - 安裝生產依賴
   - 安裝開發依賴
   - 驗證安裝

3. **運行測試**
   - 執行 pytest
   - 生成測試報告

4. **上傳覆蓋率**
   - 上傳到 Codecov
   - 生成覆蓋率報告

## 開發工作流程

### 本地開發

1. **設置環境**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. **運行測試**
   ```bash
   pytest -v
   ```

3. **代碼格式化**
   ```bash
   black src/ tests/
   isort src/ tests/
   flake8 src/ tests/
   ```

### 提交流程

1. **創建功能分支**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **進行更改**
   - 編寫代碼
   - 添加測試
   - 運行本地測試

3. **提交更改**
   ```bash
   git add .
   git commit -m "feat: add your feature"
   git push origin feature/your-feature
   ```

4. **創建 Pull Request**
   - 在 GitHub 上創建 PR
   - CI 會自動運行測試
   - 等待審查和合併

## 代碼品質

### 格式化工具

- **Black**: 自動代碼格式化
- **isort**: 導入語句排序
- **flake8**: 代碼風格檢查

### 英文標準

我們採用靈活的英文標準政策：

- **函數和變量名**: 鼓勵使用英文，但不是強制要求
- **註釋**: 可以使用中文或英文
- **文檔**: 可以使用中文或英文
- **用戶界面**: 可以使用中文

## 測試策略

### 測試類型

- **單元測試**: 測試個別函數和類
- **集成測試**: 測試模組間交互
- **功能測試**: 測試完整功能流程

### 測試覆蓋率

- 目標：保持良好的測試覆蓋率
- 工具：pytest + coverage
- 報告：自動上傳到 Codecov

## 故障排除

### 常見問題

**CI 失敗**
1. 檢查測試是否在本地通過
2. 確認依賴版本正確
3. 查看錯誤日誌

**測試失敗**
1. 運行本地測試：`pytest -v`
2. 檢查測試環境設置
3. 確認所有依賴已安裝

**格式化問題**
1. 運行 Black：`black src/ tests/`
2. 運行 isort：`isort src/ tests/`
3. 檢查 flake8：`flake8 src/ tests/`

### 獲得幫助

如果遇到問題：
1. 查看 CI 日誌
2. 檢查現有 Issues
3. 創建新的 Issue
4. 聯繫項目維護者

## 最佳實踐

### 開發建議

1. **保持測試簡單**: 專注於核心功能測試
2. **及時提交**: 小步驟提交，避免大型 PR
3. **文檔更新**: 重要變更需要更新文檔
4. **代碼審查**: 主動審查他人的代碼

### CI/CD 建議

1. **快速反饋**: 保持 CI 快速運行
2. **穩定性**: 確保 CI 可靠性
3. **簡單配置**: 避免過度複雜的配置
4. **文檔同步**: 保持文檔與實際配置同步

---

**這個簡化的 CI/CD 流程專注於核心功能，確保開發效率和代碼品質的平衡。**

# 持續整合

實際工作流程為 [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)。推送到 `main`／`develop`、對 `main` 提交 Pull Request，以及手動觸發時執行。

## 一般測試與品質

Ubuntu 上分別使用 Python 3.10、3.11、3.12、3.13，安裝執行與開發依賴，執行 pytest、覆蓋率、Flake8、Black、isort 與 Bandit。覆蓋率上傳設定見工作流程；不能把通過 CI 等同所有功能都已有測試。

## MySQL 整合

另有獨立 `mysql-integration` 工作，使用 MySQL 8.4 容器與 Python 3.13。它設定 `MYSQL_INTEGRATION_TEST=1`、獨立測試帳號與 `_test` 資料庫，執行資料遷移、實機儲存、連線恢復與故障測試。

這項工作在 CI 固定執行，失敗會使工作流程失敗；本機一般測試未配置 MySQL 時跳過整合測試屬預期。分支是否要求指定狀態檢查由 GitHub 分支保護設定決定，工作流程本身不會修改該設定。

本機重現、測試資料隔離與品質命令見 [CONTRIBUTING.md](../CONTRIBUTING.md)。CI 不會部署網站或重啟本機服務，部署流程見 [DEPLOYMENT.md](DEPLOYMENT.md)。

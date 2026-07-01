"""伺服器管理業務邏輯服務 (倉庫追蹤 / 歡迎訊息 / GitHub 輪詢)"""

from datetime import datetime
from datetime import timezone
import json
import os
import shutil
from typing import Optional

import aiohttp

from src.utils.time_utils import format_datetime as _format_time
from src.utils.time_utils import TZ_OFFSET

_DATA_FILE = "data/storage/management.json"


class ManagementService:
    """伺服器管理資料存取與 GitHub 輪詢邏輯"""

    def __init__(self) -> None:
        os.makedirs("data/storage", exist_ok=True)
        self._config: dict = self._load()
        self._session: Optional[aiohttp.ClientSession] = None

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict:
        if not os.path.exists(_DATA_FILE):
            return {}
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        """儲存設定 (原子寫入 + 備份機制)"""
        _temp = _DATA_FILE + ".tmp"
        try:
            with open(_temp, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            if os.path.exists(_DATA_FILE):
                shutil.copy2(_DATA_FILE, f"{_DATA_FILE}.backup")
            os.replace(_temp, _DATA_FILE)
        except OSError as e:
            print(f"[錯誤] 儲存管理設定失敗: {e}")
            try:
                os.unlink(_temp)
            except OSError:
                pass
            backup = f"{_DATA_FILE}.backup"
            if os.path.exists(backup):
                print("[錯誤] 正在從備份還原...")
                shutil.copy2(backup, _DATA_FILE)

    @property
    def config(self) -> dict:
        """取得完整設定字典"""
        return self._config

    def get_guild_config(self, guild_id: str) -> dict:
        """取得伺服器設定"""
        return self._config.get(guild_id, {})

    def update_guild_config(self, guild_id: str, data: dict) -> None:
        """更新伺服器設定的指定欄位"""
        self._config.setdefault(guild_id, {}).update(data)
        self.save()

    # ─────────────── 倉庫追蹤 ───────────────

    def add_tracked_repo(
        self, guild_id: str, owner: str, repo: str, channel_id: int
    ) -> None:
        """新增倉庫追蹤"""
        repo_key = f"{owner}/{repo}"
        self._config.setdefault(guild_id, {}).setdefault("tracked_repos", {})[
            repo_key
        ] = {
            "owner": owner,
            "repo": repo,
            "channel_id": channel_id,
            "last_commit": None,
            "last_pr": None,
        }
        self.save()

    def remove_tracked_repo(self, guild_id: str, repo_key: str) -> bool:
        """移除倉庫追蹤，回傳是否存在"""
        repos = self._config.get(guild_id, {}).get("tracked_repos", {})
        if repo_key not in repos:
            return False
        del repos[repo_key]
        self.save()
        return True

    def get_tracked_repos(self, guild_id: str) -> dict:
        """取得伺服器所有追蹤倉庫"""
        return self._config.get(guild_id, {}).get("tracked_repos", {})

    # ─────────────── 歡迎訊息 ───────────────

    def get_welcome_config(self, guild_id: str) -> dict:
        """取得歡迎訊息設定"""
        return self._config.get(guild_id, {}).get("welcome", {})

    def set_welcome_config(self, guild_id: str, config: dict) -> None:
        """設定歡迎訊息"""
        self._config.setdefault(guild_id, {})["welcome"] = config
        self.save()

    # ─────────────── HTTP Session ───────────────

    async def get_session(self) -> aiohttp.ClientSession:
        """取得或建立 HTTP Session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": "Discord-Bot/1.0"},
            )
        return self._session

    async def close_session(self) -> None:
        """關閉 HTTP Session"""
        if self._session and not self._session.closed:
            await self._session.close()

    # ─────────────── GitHub 輪詢 ───────────────

    async def check_repo_updates(
        self, guild_id: str, repo_key: str, repo_data: dict
    ) -> list[dict]:
        """
        檢查單一倉庫的 Commit/PR 更新。

        回傳事件列表，每筆含 type ('commit'|'pr')、embed_data、channel_id。
        """
        session = await self.get_session()
        owner = repo_data["owner"]
        repo = repo_data["repo"]
        events: list[dict] = []
        has_changes = False

        try:
            # 檢查最新 Commit
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            async with session.get(commits_url) as resp:
                if resp.status == 200:
                    commits = await resp.json()
                    if commits and commits[0]["sha"] != repo_data.get("last_commit"):
                        latest = commits[0]
                        repo_data["last_commit"] = latest["sha"]
                        has_changes = True
                        author = latest.get("author") or {}
                        events.append(
                            {
                                "type": "commit",
                                "channel_id": repo_data["channel_id"],
                                "repo_key": repo_key,
                                "title": f"[GitHub] {repo_key} 新 Commit",
                                "description": latest["commit"]["message"][:200],
                                "url": latest["html_url"],
                                "sha": latest["sha"][:7],
                                "date": _format_time(
                                    datetime.fromisoformat(
                                        latest["commit"]["committer"]["date"]
                                    )
                                ),
                                "author_name": author.get(
                                    "login",
                                    latest["commit"]["author"]["name"],
                                ),
                                "author_url": author.get("html_url", ""),
                                "author_avatar": author.get("avatar_url", ""),
                            }
                        )
                elif resp.status == 403:
                    print(f"[警告] GitHub API 速率限制 ({repo_key})")

            # 檢查最新 PR
            prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            async with session.get(prs_url) as resp:
                if resp.status == 200:
                    prs = await resp.json()
                    if prs and prs[0]["number"] != repo_data.get("last_pr"):
                        latest = prs[0]
                        repo_data["last_pr"] = latest["number"]
                        has_changes = True
                        events.append(
                            {
                                "type": "pr",
                                "channel_id": repo_data["channel_id"],
                                "repo_key": repo_key,
                                "title": f"[GitHub] {repo_key} 新 Pull Request",
                                "description": latest["title"][:200],
                                "url": latest["html_url"],
                                "pr_number": str(latest["number"]),
                                "state": latest["state"].title(),
                                "author_name": latest["user"]["login"],
                                "author_url": latest["user"]["html_url"],
                                "author_avatar": latest["user"]["avatar_url"],
                            }
                        )
                elif resp.status == 403:
                    print(f"[警告] GitHub API 速率限制 PR ({repo_key})")

        except aiohttp.ClientError as e:
            print(f"[錯誤] 網路錯誤 ({repo_key}): {e}")
        except Exception as e:
            print(f"[錯誤] 意外錯誤 ({repo_key}): {e}")

        if has_changes:
            self.save()

        return events

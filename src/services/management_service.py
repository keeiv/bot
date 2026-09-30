"""伺服器管理業務邏輯服務 (倉庫追蹤 / 歡迎訊息 / GitHub 輪詢)"""

import asyncio
from datetime import datetime
import json
import logging
import os
import shutil
import time
from typing import Any, Optional

import aiohttp

from src.utils.document_store import document_exists
from src.utils.document_store import open_document
from src.utils.document_store import using_mysql
from src.utils.document_store import write_document
from src.utils.time_utils import format_datetime as _format_time

log = logging.getLogger(__name__)

_DATA_FILE = "data/storage/management.json"


class ManagementService:
    """伺服器管理資料存取與 GitHub 輪詢邏輯"""

    def __init__(self) -> None:
        os.makedirs("data/storage", exist_ok=True)
        self._config: dict[Any, Any] = self._load()
        self._session: Optional[aiohttp.ClientSession] = None
        self._github_lock = asyncio.Lock()
        self._github_retry_at = 0.0
        self._github_backoff = 60.0
        self._github_cache: dict[str, tuple[float, list[Any], str | None]] = {}
        self._github_failed_until: dict[str, float] = {}

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict[Any, Any]:
        if not document_exists(_DATA_FILE):
            return {}
        try:
            with open_document(_DATA_FILE, "r", encoding="utf-8") as f:
                result_value = json.load(f)
                if not isinstance(result_value, dict):
                    raise TypeError("Unexpected stored or API value: expected dict")
                return result_value
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        """儲存設定 (原子寫入 + 備份機制)"""
        if using_mysql():
            write_document(_DATA_FILE, self._config)
            return
        _temp = _DATA_FILE + ".tmp"
        try:
            with open(_temp, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            if document_exists(_DATA_FILE):
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
    def config(self) -> dict[Any, Any]:
        """取得完整設定字典"""
        return self._config

    def get_guild_config(self, guild_id: str) -> dict[Any, Any]:
        """取得伺服器設定"""
        result_value = self._config.get(guild_id, {})
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def update_guild_config(self, guild_id: str, data: dict[Any, Any]) -> None:
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

    def get_tracked_repos(self, guild_id: str) -> dict[Any, Any]:
        """取得伺服器所有追蹤倉庫"""
        result_value = self._config.get(guild_id, {}).get("tracked_repos", {})
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    # ─────────────── 歡迎訊息 ───────────────

    def get_welcome_config(self, guild_id: str) -> dict[Any, Any]:
        """取得歡迎訊息設定"""
        result_value = self._config.get(guild_id, {}).get("welcome", {})
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def set_welcome_config(self, guild_id: str, config: dict[Any, Any]) -> None:
        """設定歡迎訊息"""
        self._config.setdefault(guild_id, {})["welcome"] = config
        self.save()

    # ─────────────── HTTP Session ───────────────

    async def get_session(self) -> aiohttp.ClientSession:
        """取得或建立 HTTP Session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            headers = {
                "User-Agent": "Discord-Bot/1.0",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    async def close_session(self) -> None:
        """關閉 HTTP Session"""
        if self._session and not self._session.closed:
            await self._session.close()

    # ─────────────── GitHub 輪詢 ───────────────

    async def _fetch_github_list(self, url: str) -> list[Any]:
        """Share polling results across guilds and respect account-wide cooldowns."""
        async with self._github_lock:
            now = time.time()
            cached = self._github_cache.get(url)
            if cached and now - cached[0] < 300:
                return cached[1]
            if now < max(self._github_retry_at, self._github_failed_until.get(url, 0)):
                return []
            headers = {"If-None-Match": cached[2]} if cached and cached[2] else {}
            session = await self.get_session()
            async with session.get(
                url, params={"per_page": 1}, headers=headers
            ) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                reset = resp.headers.get("X-RateLimit-Reset")
                if remaining == "0":
                    self._github_retry_at = max(
                        now + 60, float(reset or now + 3600) + 1
                    )
                if resp.status == 304 and cached:
                    self._github_cache[url] = (now, cached[1], cached[2])
                    return cached[1]
                if resp.status == 200:
                    data = await resp.json()
                    if not isinstance(data, list):
                        raise ValueError("GitHub response must be a list")
                    self._github_cache[url] = (now, data, resp.headers.get("ETag"))
                    self._github_backoff = 60.0
                    return data
                if resp.status in (403, 429):
                    # 403 can also mean missing repository permissions.
                    body = (await resp.text()).lower()
                    retry_after = resp.headers.get("Retry-After")
                    limited = (
                        resp.status == 429
                        or remaining == "0"
                        or retry_after
                        or "rate limit" in body
                        or "abuse" in body
                    )
                    if limited:
                        delay = max(self._github_backoff, float(retry_after or 0))
                        self._github_retry_at = max(self._github_retry_at, now + delay)
                        self._github_backoff = min(self._github_backoff * 2, 3600)
                        log.warning(
                            "GitHub API 限流，暫停倉庫追蹤至 %.0f",
                            self._github_retry_at,
                        )
                        return []
                self._github_failed_until[url] = now + 300
                log.warning("GitHub 倉庫查詢失敗 (HTTP %s)", resp.status)
                return []

    async def check_repo_updates(
        self, guild_id: str, repo_key: str, repo_data: dict[Any, Any]
    ) -> list[dict[Any, Any]]:
        """
        檢查單一倉庫的 Commit/PR 更新。

        回傳事件列表，每筆含 type ('commit'|'pr')、embed_data、channel_id。
        """
        owner = repo_data["owner"]
        repo = repo_data["repo"]
        events: list[dict[Any, Any]] = []
        has_changes = False

        try:
            # 檢查最新 Commit
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits = await self._fetch_github_list(commits_url)
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

            # 檢查最新 PR
            prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            prs = await self._fetch_github_list(prs_url)
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

        except aiohttp.ClientError as e:
            print(f"[錯誤] 網路錯誤 ({repo_key}): {e}")
        except Exception as e:
            print(f"[錯誤] 意外錯誤 ({repo_key}): {e}")

        if has_changes:
            self.save()

        return events

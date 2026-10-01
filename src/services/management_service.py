"""伺服器管理業務邏輯服務 (倉庫追蹤 / 歡迎訊息 / GitHub 輪詢)"""

import asyncio
import copy
from datetime import datetime
import logging
import os
import shutil
import threading
import time
from typing import Any, Optional

import aiohttp

from src.utils.document_store import read_document
from src.utils.document_store import using_mysql
from src.utils.document_store import write_document
from src.utils.storage_worker import run_storage
from src.utils.time_utils import format_datetime as _format_time

log = logging.getLogger(__name__)

_DATA_FILE = "data/storage/management.json"


class ManagementService:
    """伺服器管理資料存取與 GitHub 輪詢邏輯"""

    def __init__(self) -> None:
        os.makedirs("data/storage", exist_ok=True)
        self._config_lock = threading.RLock()
        self._config: dict[Any, Any] = self._load()
        self._session: Optional[aiohttp.ClientSession] = None
        self._github_lock = asyncio.Lock()
        self._github_retry_at = 0.0
        self._github_backoff = 60.0
        self._github_cache: dict[str, tuple[float, list[Any], str | None]] = {}
        self._github_failed_until: dict[str, float] = {}

    # ─────────────── 資料存取 ───────────────

    def _load(self) -> dict[Any, Any]:
        try:
            data = read_document(_DATA_FILE)
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise TypeError("Configuration must be an object")
        return data

    def save(self, config=None) -> None:
        """Persist a snapshot; failures propagate without publishing changes."""
        proposed = self._config if config is None else config
        if not using_mysql() and os.path.exists(_DATA_FILE):
            shutil.copy2(_DATA_FILE, f"{_DATA_FILE}.backup")
        write_document(_DATA_FILE, proposed)

    def _mutate(self, update):
        with self._config_lock:
            proposed = copy.deepcopy(self._config)
            result = update(proposed)
            if result is False or result is None:
                return result
            self.save(proposed)
            self._config = proposed
            return result

    @property
    def config(self) -> dict[Any, Any]:
        """Read-only snapshot retained for compatibility with existing readers."""
        with self._config_lock:
            return copy.deepcopy(self._config)

    def get_all_configs(self):
        return self.config

    def get_guild_config(self, guild_id: str) -> dict[Any, Any]:
        """Return a detached guild snapshot."""
        with self._config_lock:
            return copy.deepcopy(self._config.get(str(guild_id), {}))

    def update_guild_config(self, guild_id: str, data: dict[Any, Any]) -> None:
        """Merge guild fields without replacing unrelated configuration."""

        def update(config):
            config.setdefault(str(guild_id), {}).update(copy.deepcopy(data))
            return True

        self._mutate(update)

    def add_tracked_repo(
        self, guild_id: str, owner: str, repo: str, channel_id: int
    ) -> None:
        """Add or reset a repository subscription."""

        def update(config):
            config.setdefault(str(guild_id), {}).setdefault("tracked_repos", {})[
                f"{owner}/{repo}"
            ] = {
                "owner": owner,
                "repo": repo,
                "channel_id": channel_id,
                "last_commit": None,
                "last_pr": None,
            }
            return True

        self._mutate(update)

    def remove_tracked_repo(self, guild_id: str, repo_key: str) -> bool:
        def update(config):
            repos = config.get(str(guild_id), {}).get("tracked_repos", {})
            if repo_key not in repos:
                return False
            del repos[repo_key]
            return True

        return self._mutate(update)

    def get_tracked_repos(self, guild_id: str) -> dict[Any, Any]:
        return self.get_guild_config(guild_id).get("tracked_repos", {})

    def _apply_repo_progress(self, guild_id, repo_key, expected, updates):
        """Reject results for a subscription changed or removed during HTTP I/O."""

        def update(config):
            current = (
                config.get(str(guild_id), {}).get("tracked_repos", {}).get(repo_key)
            )
            if current != expected:
                return False
            current.update(updates)
            return True

        return self._mutate(update)

    def get_welcome_config(self, guild_id: str) -> dict[Any, Any]:
        return self.get_guild_config(guild_id).get("welcome", {})

    def set_welcome_config(self, guild_id: str, config: dict[Any, Any]) -> None:
        self.update_guild_config(guild_id, {"welcome": config})

    def update_welcome_config(self, guild_id, updates):
        def update(config):
            config.setdefault(str(guild_id), {}).setdefault("welcome", {}).update(
                copy.deepcopy(updates)
            )
            return True

        self._mutate(update)

    def clear_welcome_config(self, guild_id: str) -> bool:
        def update(config):
            guild = config.get(str(guild_id), {})
            if "welcome" not in guild:
                return False
            del guild["welcome"]
            return True

        return self._mutate(update)

    def get_auto_roles(self, guild_id: str) -> list:
        return self.get_guild_config(guild_id).get("auto_roles", [])

    def add_auto_role(self, guild_id: str, rule: dict) -> None:
        def update(config):
            config.setdefault(str(guild_id), {}).setdefault("auto_roles", []).append(
                copy.deepcopy(rule)
            )
            return True

        self._mutate(update)

    def remove_auto_role(self, guild_id: str, rule_index: int):
        """Remove a one-based rule index, or return None if it is invalid."""

        def update(config):
            rules = config.get(str(guild_id), {}).get("auto_roles", [])
            if not 1 <= rule_index <= len(rules):
                return None
            return rules.pop(rule_index - 1)

        return self._mutate(update)

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
        updates = {}
        expected = copy.deepcopy(repo_data)

        try:
            # 檢查最新 Commit
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits = await self._fetch_github_list(commits_url)
            if commits and commits[0]["sha"] != repo_data.get("last_commit"):
                latest = commits[0]
                updates["last_commit"] = latest["sha"]
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
                updates["last_pr"] = latest["number"]
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

        if updates and not await run_storage(
            self._apply_repo_progress, guild_id, repo_key, expected, updates
        ):
            return []

        return events

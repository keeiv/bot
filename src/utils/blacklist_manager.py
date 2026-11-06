import asyncio
import copy
from datetime import datetime
import json
import os
import time
from typing import Any, Dict, Optional

import aiohttp

from src.utils.document_store import document_exists
from src.utils.document_store import open_document
from src.utils.storage_worker import run_storage
from src.utils.time_utils import TZ_OFFSET

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "storage",
)
LOCAL_BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
# Remote blacklists, checked after the local one in this order.
MORI = "mori"  # Mori.black, the owner's shared blacklist
CATHOME = "cathome"
MORI_DEFAULT_URL = "https://botweb.shizune.life/api/mori/v1"
APPEALS_FILE = os.path.join(DATA_DIR, "appeals.json")


def _load_json(path: str) -> Dict[Any, Any]:
    """讀取 JSON 檔案"""
    if document_exists(path):
        try:
            with open_document(path, "r", encoding="utf-8") as f:
                result_value = json.load(f)
                if not isinstance(result_value, dict):
                    raise TypeError("Unexpected stored or API value: expected dict")
                return result_value
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: str, data: Dict[Any, Any]) -> None:
    """寫入 JSON 檔案"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open_document(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class BlacklistManager:
    """黑名單管理器 (本地 + Mori.black + CatHome API 三軌)"""

    _LOCAL_CACHE_TTL: float = 30.0
    # Every message is checked, so the API must never hold one up for long.
    API_TIMEOUT = aiohttp.ClientTimeout(total=3)
    API_CACHE_SECONDS = 10.0  # an answer (blocked or not) is reused this long
    API_FAILURE_SECONDS = 30.0  # after a failure the API is left alone this long
    API_CACHE_LIMIT = 5000  # users kept; older entries are dropped
    # Mori.black allows each token 120 requests a minute, too few to ask about every
    # member who speaks: the bot keeps a copy of the whole list instead, read again
    # at most this often (a page holds up to MORI_PAGE entries).
    MORI_SYNC_SECONDS = 60.0
    MORI_PAGE = 500

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        mori_token: str | None = None,
        mori_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_base = api_base
        self.mori_token = mori_token
        self.mori_url = (mori_url or MORI_DEFAULT_URL).rstrip("/")
        # (source, member) -> the answer and when it came
        self._api_cache: Dict[tuple[str, int], Optional[Dict[Any, Any]]] = {}
        self._api_cache_time: Dict[tuple[str, int], float] = {}
        # (source, member) -> the lookup in progress, so messages sent together share one
        self._api_pending: Dict[tuple[str, int], asyncio.Future[Any]] = {}
        self._api_down_until: Dict[str, float] = {}
        # (source, member) -> bumped when their entries are revoked: a lookup that
        # started before then must not publish what it read
        self._api_generation: Dict[tuple[str, int], int] = {}
        # Mori.black copy: user id -> their active entries
        self._mori: Dict[str, list[Dict[Any, Any]]] = {}
        self._mori_synced_at: float | None = None
        self._mori_sync: asyncio.Future[Any] | None = None
        # entry id -> when it was revoked here; a sync that started before then
        # must not bring it back
        self._mori_revoked: Dict[str, float] = {}
        self.session: aiohttp.ClientSession | None = None
        self._local_cache: dict[Any, Any] | None = None
        self._local_cache_time: float = 0.0

    async def setup(self) -> None:
        """初始化 HTTP session"""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.API_TIMEOUT)

    async def close(self) -> None:
        """關閉 HTTP session"""
        if self.session:
            await self.session.close()

    # ==================== 本地黑名單 ====================

    def _load_local(self) -> dict[Any, Any]:
        """讀取本地黑名單 (帶 TTL cache)"""
        now = time.monotonic()
        if (
            self._local_cache is not None
            and (now - self._local_cache_time) < self._LOCAL_CACHE_TTL
        ):
            return copy.deepcopy(self._local_cache)
        self._local_cache = _load_json(LOCAL_BLACKLIST_FILE)
        self._local_cache_time = now
        return copy.deepcopy(self._local_cache)

    def _update_local_cache(self, data: dict[Any, Any]) -> None:
        """儲存後同步更新快取"""
        self._local_cache = copy.deepcopy(data)
        self._local_cache_time = time.monotonic()

    def local_check(self, user_id: int) -> Optional[Dict[Any, Any]]:
        """檢查本地黑名單 (同步, 零延遲)"""
        data = self._load_local()
        users = data.get("users", {})
        entry = users.get(str(user_id))
        if not entry:
            return None
        # 檢查是否過期
        expires_at = entry.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.now(TZ_OFFSET) >= exp_dt:
                    self.local_remove(user_id)
                    return None
            except ValueError:
                pass
        result_value = entry
        if result_value is None:
            return None
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    def local_add(
        self,
        user_id: int,
        reason: str,
        mode: str = "block",
        added_by: int | None = None,
        expires_at: str | None = None,
        note: str | None = None,
    ) -> bool:
        """新增本地黑名單"""
        data = self._load_local()
        data.setdefault("users", {})
        user_id_str = str(user_id)

        data["users"][user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "mode": mode,
            "added_by": added_by,
            "added_at": datetime.now(TZ_OFFSET).isoformat(),
            "expires_at": expires_at,
            "note": note,
        }

        _save_json(LOCAL_BLACKLIST_FILE, data)
        self._update_local_cache(data)
        return True

    def local_remove(self, user_id: int) -> bool:
        """移除本地黑名單"""
        data = self._load_local()
        users = data.get("users", {})
        user_id_str = str(user_id)

        if user_id_str not in users:
            return False

        del users[user_id_str]
        _save_json(LOCAL_BLACKLIST_FILE, data)
        self._update_local_cache(data)
        return True

    def local_list(self) -> Dict[str, Dict[Any, Any]]:
        """取得所有本地黑名單"""
        result_value = self._load_local().get("users", {})
        if not isinstance(result_value, dict):
            raise TypeError("Unexpected stored or API value: expected dict")
        return result_value

    # ==================== CatHome API ====================

    async def api_check(self, user_id: int) -> Optional[Dict[Any, Any]]:
        """檢查 CatHome API 黑名單 (非同步)"""
        return await self._remote(CATHOME, user_id)

    async def mori_check(self, user_id: int) -> Optional[Dict[Any, Any]]:
        """檢查 Mori.black 共享黑名單 (查本機的整份副本，過期才重新同步)"""
        if not self._configured(MORI):
            return None
        await self._mori_fresh()
        entries = self._mori.get(str(user_id), [])
        mode = (
            "global_ban"
            if any(e.get("mode") == "global_ban" for e in entries)
            else ("block" if entries else None)
        )
        return self._parse(MORI, user_id, {"mode": mode, "entries": entries})

    async def _mori_fresh(self) -> None:
        """Sync the Mori.black copy when it is stale and the service is not backed off."""
        if not self.session:
            await self.setup()
        loop = asyncio.get_running_loop()
        stale = (
            self._mori_synced_at is None
            or loop.time() - self._mori_synced_at >= self.MORI_SYNC_SECONDS
        )
        if stale and loop.time() >= self._api_down_until.get(MORI, 0.0):
            if self._mori_sync is None or self._mori_sync.done():
                self._mori_sync = asyncio.ensure_future(self._mori_refresh())
            await asyncio.shield(self._mori_sync)

    async def global_ban_targets(self) -> Optional[Dict[int, str]]:
        """Everyone to ban in every server: {user_id: "local" | "mori" | "local,mori"}.

        None while a configured Mori.black copy has never loaded, so a gap at
        start-up is never read as "their entries are gone".
        """
        targets: Dict[int, str] = {}
        if self._configured(MORI):
            await self._mori_fresh()
            if self._mori_synced_at is None:
                return None
            for user, entries in self._mori.items():
                if user.isdigit() and any(
                    e.get("mode") == "global_ban" for e in entries
                ):
                    targets[int(user)] = MORI
        now = datetime.now(TZ_OFFSET)
        for user, entry in self.local_list().items():
            if not user.isdigit() or entry.get("mode") != "global_ban":
                continue
            expires_at = entry.get("expires_at")
            try:
                if expires_at and datetime.fromisoformat(expires_at) <= now:
                    continue
            except ValueError:
                pass
            targets[int(user)] = "local,mori" if int(user) in targets else "local"
        return targets

    async def _mori_refresh(self) -> None:
        """Read the whole Mori.black list; on failure keep the last copy and back off."""
        if self.session is None:
            return
        loop = asyncio.get_running_loop()
        started = loop.time()
        headers = {"Authorization": f"Bearer {self.mori_token}"}
        copy_: Dict[str, list[Dict[Any, Any]]] = {}
        cursor = None
        try:
            while True:
                url = f"{self.mori_url}/entries?limit={self.MORI_PAGE}"
                if cursor:
                    url += f"&cursor={cursor}"
                async with self.session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"Mori.black answered {resp.status}")
                    data = await resp.json(content_type=None)
                for entry in data.get("entries") or []:
                    if isinstance(entry, dict) and entry.get("user_id"):
                        copy_.setdefault(str(entry["user_id"]), []).append(entry)
                cursor = data.get("next_cursor")
                if not cursor:
                    break
        except Exception:
            self._api_down_until[MORI] = loop.time() + self.API_FAILURE_SECONDS
            return
        gone = {entry for entry, at in self._mori_revoked.items() if at >= started}
        if gone:
            copy_ = {
                user: kept
                for user, entries in copy_.items()
                if (kept := [e for e in entries if str(e.get("id")) not in gone])
            }
        self._mori = copy_
        self._mori_synced_at = loop.time()
        self._mori_revoked = {
            entry: at for entry, at in self._mori_revoked.items() if at >= started
        }

    def _configured(self, source: str) -> bool:
        if source == MORI:
            return bool(self.mori_token and self.mori_url)
        return bool(self.api_key and self.api_base)

    async def _remote(self, source: str, user_id: int) -> Optional[Dict[Any, Any]]:
        """One remote blacklist, never holding a message up for long (see API_*)."""
        if not self._configured(source):
            return None
        if not self.session:
            await self.setup()
        if self.session is None:
            return None

        key = (source, user_id)
        now = asyncio.get_running_loop().time()
        if (
            key in self._api_cache
            and now - self._api_cache_time.get(key, 0) < self.API_CACHE_SECONDS
        ):
            return self._api_cache[key]
        if now < self._api_down_until.get(source, 0.0):
            return None  # failed a moment ago: do not wait on it for every message
        pending = self._api_pending.get(key)
        if pending is None:
            pending = asyncio.ensure_future(self._api_lookup(source, user_id))
            self._api_pending[key] = pending
            pending.add_done_callback(lambda done: self._forget_pending(key, done))
        return await asyncio.shield(pending)

    def _forget_pending(self, key: tuple[str, int], done: asyncio.Future[Any]) -> None:
        # Only its own: after a revoke a newer lookup may hold the key.
        if self._api_pending.get(key) is done:
            del self._api_pending[key]

    def _request(self, source: str, user_id: int) -> tuple[str, dict[str, str]]:
        return f"{self.api_base}/{user_id}", {
            "X-API-Key": self.api_key or "",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _parse(source: str, user_id: int, data: Any) -> Optional[Dict[Any, Any]]:
        if not isinstance(data, dict):
            return None
        if source == MORI:
            # {"mode": "global_ban" | "block" | null, "entries": [...]}: the most
            # severe mode, with the reason of an entry in that mode
            mode = data.get("mode")
            entries = [e for e in data.get("entries") or [] if isinstance(e, dict)]
            if mode not in ("global_ban", "block") or not entries:
                return None
            chosen = next((e for e in entries if e.get("mode") == mode), entries[0])
            return {
                "user_id": str(user_id),
                "mode": mode,
                "reason": chosen.get("reason"),
                "entry_ids": [str(e.get("id")) for e in entries if e.get("id")],
                "reported_by": chosen.get("source"),
            }
        item = data.get("item")
        if not isinstance(item, dict):
            return None
        item.setdefault("user_id", str(user_id))
        return item

    async def _api_lookup(self, source: str, user_id: int) -> Optional[Dict[Any, Any]]:
        if self.session is None:
            return None
        url, headers = self._request(source, user_id)
        key = (source, user_id)
        generation = self._api_generation.get(key, 0)
        loop = asyncio.get_running_loop()
        data: Any = {}
        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    data = {}
                elif resp.status != 200:
                    self._api_down_until[source] = (
                        loop.time() + self.API_FAILURE_SECONDS
                    )
                    return None
                else:
                    data = await resp.json(content_type=None)
        except Exception:
            # Timeouts and network errors: back off instead of retrying per message.
            self._api_down_until[source] = loop.time() + self.API_FAILURE_SECONDS
            return None

        result = self._parse(source, user_id, data)
        if self._api_generation.get(key, 0) != generation:
            return None  # revoked while this was reading: what it read is gone
        if len(self._api_cache) >= self.API_CACHE_LIMIT:
            oldest = sorted(self._api_cache_time, key=self._api_cache_time.get)
            for stale in oldest[: self.API_CACHE_LIMIT // 2]:
                self._api_cache.pop(stale, None)
                self._api_cache_time.pop(stale, None)
        self._api_cache[(source, user_id)] = result
        self._api_cache_time[(source, user_id)] = loop.time()
        return result

    async def mori_revoke(self, user_id: int, entry_ids: list[str]) -> int:
        """Revoke the Mori.black entries an accepted appeal was about; returns how many.

        Only those: an entry added after the appeal was filed was not reviewed.
        BOT.'s token is the owner's app, so it may revoke entries other apps added.
        """
        if not self._configured(MORI):
            raise RuntimeError("MORI_BLACK_TOKEN is not set")
        if not self.session:
            await self.setup()
        assert self.session is not None
        headers = {"Authorization": f"Bearer {self.mori_token}"}
        ids = [str(entry) for entry in entry_ids if str(entry).isdigit()]
        revoked = 0
        try:
            for entry in ids:
                async with self.session.delete(
                    f"{self.mori_url}/entries/{entry}", headers=headers
                ) as resp:
                    if resp.status == 200:
                        revoked += 1
                    elif resp.status != 404:  # 404: someone revoked it already
                        resp.raise_for_status()
        finally:
            # Even when some failed: the accepted entries stop counting in this copy,
            # and a sync already reading cannot put them back.
            now = asyncio.get_running_loop().time()
            for entry in ids:
                self._mori_revoked[entry] = now
            kept = [
                e
                for e in self._mori.get(str(user_id), [])
                if str(e.get("id")) not in ids
            ]
            if kept:
                self._mori[str(user_id)] = kept
            else:
                self._mori.pop(str(user_id), None)
        return revoked

    async def check(self, user_id: int) -> Optional[Dict[Any, Any]]:
        """三軌檢查: 本地優先, 再查 Mori.black, 最後 CatHome

        回傳 dict 含 "source" 鍵標記來源 ("local" / "mori" / "api")
        """
        # Keep the worker serialized while allowing the command's short lookup
        # deadline to expire without waiting for a slow database socket to close.
        lookup = asyncio.create_task(run_storage(self.local_check, user_id))
        lookup.add_done_callback(
            lambda task: None if task.cancelled() else task.exception()
        )
        local_entry = await asyncio.shield(lookup)
        if local_entry:
            local_entry["source"] = "local"
            return local_entry

        # Both at once, and the first block found is used at once: a slow source
        # must not use up the caller's deadline and hide the other's answer.
        # Mori.black wins when both have answered. A lookup still running goes on
        # and fills the cache for the next message.
        lookups = {
            asyncio.ensure_future(self.mori_check(user_id)): "mori",
            asyncio.ensure_future(self._remote(CATHOME, user_id)): "api",
        }
        found: Dict[str, Dict[Any, Any]] = {}
        waiting = set(lookups)
        while waiting:
            done, waiting = await asyncio.wait(
                waiting, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                if task.result():
                    found[lookups[task]] = task.result()
            if found:
                break
        for label in ("mori", "api"):
            if label in found:
                return {**found[label], "source": label}
        return None

    # ==================== 申訴系統 ====================

    def load_appeals(self) -> Dict[Any, Any]:
        """讀取申訴資料"""
        return _load_json(APPEALS_FILE)

    def save_appeals(self, appeals: Dict[Any, Any]) -> None:
        """儲存申訴資料"""
        _save_json(APPEALS_FILE, appeals)

    def add_appeal(
        self,
        user_id: int,
        reason: str,
        source: str = "local",
        entry_ids: Optional[list[str]] = None,
    ) -> bool:
        """提交申訴"""
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str in appeals and appeals[user_id_str].get("status") == "待處理":
            return False

        appeals[user_id_str] = {
            "user_id": user_id,
            "reason": reason,
            "source": source,
            # the remote entries this appeal is about (Mori.black); accepting it
            # revokes only these
            "entry_ids": list(entry_ids or []),
            "status": "待處理",
            "created_at": datetime.now(TZ_OFFSET).isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "review_reason": None,
        }

        self.save_appeals(appeals)
        return True

    def get_appeal(self, user_id: int) -> Optional[Dict[Any, Any]]:
        """查詢申訴"""
        appeals = self.load_appeals()
        return appeals.get(str(user_id))

    def update_appeal(
        self,
        user_id: int,
        status: str,
        reviewer_id: int | None = None,
        review_reason: str | None = None,
    ) -> bool:
        """更新申訴狀態"""
        appeals = self.load_appeals()
        user_id_str = str(user_id)

        if user_id_str not in appeals:
            return False

        appeals[user_id_str]["status"] = status
        appeals[user_id_str]["reviewed_at"] = datetime.now(TZ_OFFSET).isoformat()
        appeals[user_id_str]["reviewed_by"] = reviewer_id
        appeals[user_id_str]["review_reason"] = review_reason

        self.save_appeals(appeals)
        return True

    def get_pending_appeals(self) -> list[Any]:
        """取得所有待處理申訴"""
        appeals = self.load_appeals()
        return [
            appeal for appeal in appeals.values() if appeal.get("status") == "待處理"
        ]

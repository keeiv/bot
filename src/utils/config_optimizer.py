import asyncio
import hashlib
from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, Optional


class ConfigFileWatcher:
    def __init__(self, file_path: str, callback: Callable[..., Any]) -> None:
        self.file_path = Path(file_path)
        self.callback = callback
        self.last_mtime = 0.0
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def start_watching(self) -> None:
        if self._running:
            return

        self._running = True
        self.last_mtime = (
            self.file_path.stat().st_mtime if self.file_path.exists() else 0
        )

        async def watch_loop() -> None:
            while self._running:
                try:
                    if self.file_path.exists():
                        current_mtime = self.file_path.stat().st_mtime
                        if current_mtime > self.last_mtime:
                            self.last_mtime = current_mtime
                            await self.callback()

                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[Config Watcher] Error watching {self.file_path}: {e}")
                    await asyncio.sleep(5)

        self._task = asyncio.create_task(watch_loop())

    def stop_watching(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


class ConfigCache:
    def __init__(self, ttl: int = 300) -> None:
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._ttl = ttl
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return data
                else:
                    del self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = (value, time.time())

    def clear(self, pattern: str | None = None) -> None:
        with self._lock:
            if pattern:
                keys_to_remove = [k for k in self._cache.keys() if pattern in k]
                for k in keys_to_remove:
                    del self._cache[k]
            else:
                self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)


class OptimizedConfigManager:
    def __init__(self, base_path: str = "data/storage") -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self._file_locks: Dict[str, threading.Lock] = {}
        self._cache = ConfigCache()
        self._watchers: Dict[str, ConfigFileWatcher] = {}
        self._write_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._batch_size = 10
        self._batch_timeout = 5.0

        self._closed = False
        self._write_errors: list[str] = []
        self._writer_task = asyncio.create_task(self._start_batch_writer())

    def _get_file_lock(self, file_path: str) -> threading.Lock:
        if file_path not in self._file_locks:
            self._file_locks[file_path] = threading.Lock()
        return self._file_locks[file_path]

    def _get_file_hash(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return ""

    def _get_cache_key(self, file_path: str) -> str:
        return f"config:{file_path}"

    async def load_config(self, file_name: str, default: Dict[Any, Any] | None = None) -> Dict[str, Any]:
        file_path = self.base_path / file_name
        cache_key = self._get_cache_key(str(file_path))

        cached_data = self._cache.get(cache_key)
        if cached_data is not None:
            result_value = cached_data
            if not isinstance(result_value, dict):
                raise TypeError("Unexpected stored or API value: expected dict")
            return result_value

        lock = self._get_file_lock(str(file_path))

        with lock:
            if not file_path.exists():
                data = default or {}
                if not self._write_config_locked(file_name, data):
                    raise OSError(f"Cannot create config {file_name}")
                return data

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._cache.set(cache_key, data)
                result_value = data
                if not isinstance(result_value, dict):
                    raise TypeError("Unexpected stored or API value: expected dict")
                return result_value
            except json.JSONDecodeError as e:
                print(f"[Config] JSON decode error in {file_name}: {e}")
                backup_path = file_path.with_suffix(f".{int(time.time())}.backup")
                file_path.rename(backup_path)
                return default or {}
            except Exception as e:
                print(f"[Config] Error loading {file_name}: {e}")
                return default or {}

    async def save_config(self, file_name: str, data: Dict[str, Any]) -> bool:
        if self._closed:
            raise RuntimeError("Config manager is closed")
        try:
            snapshot = deepcopy(data)
            await self._write_queue.put(
                {"file_name": file_name, "data": snapshot, "timestamp": time.time()}
            )
            self._cache.set(self._get_cache_key(str(self.base_path / file_name)), snapshot)
            return True
        except Exception as e:
            print(f"[Config] Error queueing save for {file_name}: {e}")
            return False

    async def _write_config_immediate(
        self, file_name: str, data: Dict[str, Any]
    ) -> bool:
        file_path = self.base_path / file_name
        lock = self._get_file_lock(str(file_path))

        with lock:
            return self._write_config_locked(file_name, data)

    def _write_config_locked(self, file_name: str, data: Dict[str, Any]) -> bool:
        """呼叫者持有檔案鎖；此函式不 await，也不重新取得鎖。"""
        file_path = self.base_path / file_name
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = file_path.with_name(file_path.name + ".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_path.replace(file_path)
            self._cache.set(self._get_cache_key(str(file_path)), deepcopy(data))
            return True
        except OSError as e:
            print(f"[Config] Error writing {file_name}: {e}")
            return False

    async def _start_batch_writer(self) -> None:
        while True:
            item = await self._write_queue.get()
            try:
                if item is None:
                    return
                await self._process_write_batch([item])
            finally:
                self._write_queue.task_done()

    async def _process_write_batch(self, batch: list[Any]) -> None:
        for item in batch:
            try:
                if not await self._write_config_immediate(item["file_name"], item["data"]):
                    self._write_errors.append(item["file_name"])
            except Exception as e:
                self._write_errors.append(item["file_name"])
                print(f"[Config] Batch write error: {e}")

    async def close(self) -> None:
        """停止監看並等待已接受的寫入完成；寫入失敗不能靜默略過。"""
        if not self._closed:
            self._closed = True
            watcher_tasks = [w._task for w in self._watchers.values() if w._task]
            self.stop_watching()
            if watcher_tasks:
                await asyncio.gather(*watcher_tasks, return_exceptions=True)
            await self._write_queue.put(None)
        await self._writer_task
        if self._write_errors:
            raise OSError(f"Failed config writes: {', '.join(self._write_errors)}")

    async def update_config(
        self, file_name: str, updates: Dict[str, Any], merge: bool = True
    ) -> bool:
        current_data = await self.load_config(file_name)

        if merge:
            self._deep_merge(current_data, updates)
        else:
            current_data = updates

        return await self.save_config(file_name, current_data)

    def _deep_merge(self, base: Dict[Any, Any], updates: Dict[Any, Any]) -> None:
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    async def get_config_value(
        self, file_name: str, key_path: str, default: Any = None
    ) -> Any:
        data = await self.load_config(file_name)

        keys = key_path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    async def set_config_value(self, file_name: str, key_path: str, value: Any) -> bool:
        data = await self.load_config(file_name)

        keys = key_path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        return await self.save_config(file_name, data)

    def watch_config(self, file_name: str, callback: Callable[..., Any]) -> None:
        file_path = self.base_path / file_name

        if str(file_path) in self._watchers:
            self._watchers[str(file_path)].stop_watching()

        async def on_file_change() -> None:
            cache_key = self._get_cache_key(str(file_path))
            self._cache.clear(cache_key)
            await callback()

        watcher = ConfigFileWatcher(str(file_path), on_file_change)
        watcher.start_watching()

        self._watchers[str(file_path)] = watcher

    def stop_watching(self, file_name: str | None = None) -> None:
        if file_name:
            file_path = str(self.base_path / file_name)
            if file_path in self._watchers:
                self._watchers[file_path].stop_watching()
                del self._watchers[file_path]
        else:
            for watcher in self._watchers.values():
                watcher.stop_watching()
            self._watchers.clear()

    async def backup_config(self, file_name: str, backup_suffix: str | None = None) -> str:
        file_path = self.base_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"Config file {file_name} not found")

        if backup_suffix is None:
            backup_suffix = str(int(time.time()))

        backup_path = file_path.with_name(f"{file_path.name}.{backup_suffix}.backup")

        lock = self._get_file_lock(str(file_path))
        with lock:
            import shutil

            shutil.copy2(file_path, backup_path)

        return str(backup_path)

    async def restore_config(self, file_name: str, backup_suffix: str) -> bool:
        backup_path = self.base_path / f"{file_name}.{backup_suffix}.backup"
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file {backup_path} not found")

        file_path = self.base_path / file_name

        lock = self._get_file_lock(str(file_path))
        with lock:
            import shutil

            shutil.copy2(backup_path, file_path)

        cache_key = self._get_cache_key(str(file_path))
        self._cache.clear(cache_key)

        return True

    def get_cache_stats(self) -> Dict[str, int]:
        return {
            "cache_size": self._cache.size(),
            "file_locks": len(self._file_locks),
            "active_watchers": len(self._watchers),
        }


config_manager: OptimizedConfigManager | None = None


def init_config_manager(base_path: str = "data/storage") -> None:
    global config_manager
    if config_manager is None or config_manager._closed:
        config_manager = OptimizedConfigManager(base_path)


def get_config_manager() -> OptimizedConfigManager | None:
    return config_manager

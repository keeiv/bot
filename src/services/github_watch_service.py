"""GitHub subscription configuration and persisted polling progress."""

import copy
import threading

from src.utils.document_store import read_document
from src.utils.document_store import write_document

_DATA_FILE = "data/storage/github_watch.json"


class GithubWatchService:
    def __init__(self):
        self._lock = threading.RLock()
        try:
            self._config = read_document(_DATA_FILE)
        except FileNotFoundError:
            self._config = {}
        if not isinstance(self._config, dict):
            raise TypeError("GitHub configuration must be an object")

    def get_all_configs(self):
        with self._lock:
            return copy.deepcopy(self._config)

    def get_config(self, guild_id):
        return self.get_all_configs().get(str(guild_id), {})

    def update_config(self, guild_id, updates):
        with self._lock:
            proposed = copy.deepcopy(self._config)
            config = proposed.setdefault(str(guild_id), {})
            incoming = copy.deepcopy(updates)
            if any(
                key in incoming and incoming[key] != config.get(key)
                for key in ("owner", "repo")
            ):
                config["last_sha"] = None
            config.update(incoming)
            write_document(_DATA_FILE, proposed)
            self._config = proposed

    def record_commit(self, guild_id, expected, sha):
        """Ignore stale polling results for changed or removed subscriptions."""
        with self._lock:
            if self._config.get(str(guild_id)) != expected:
                return False
            self.update_config(guild_id, {"last_sha": sha})
            return True

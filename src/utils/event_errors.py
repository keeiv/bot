"""Quiet handling of storage outages raised inside event listeners.

When MySQL is unreachable every incoming message, member update and voice
event fails the same way. A full traceback per event buries the log, so an
outage is reported as one warning per window with a count of what was skipped.
"""

import logging
import time
from typing import Callable, Optional

from src.utils.document_store import StorageError

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60.0


class StorageOutageLog:
    """Rate-limited warnings for listener failures caused by storage."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        window: float = WINDOW_SECONDS,
    ) -> None:
        self._clock = clock
        self._window = window
        self._last_warning: Optional[float] = None
        self._skipped = 0

    def report(self, event_name: str, error: Optional[BaseException]) -> bool:
        """Log a storage outage briefly; return False for any other error."""
        if not isinstance(error, StorageError):
            return False
        now = self._clock()
        if self._last_warning is not None and now - self._last_warning < self._window:
            self._skipped += 1
            return True
        if self._skipped:
            logger.warning(
                "Storage unavailable in %s: %s (%d more listener failures since the last warning)",
                event_name,
                error,
                self._skipped,
            )
        else:
            logger.warning("Storage unavailable in %s: %s", event_name, error)
        self._last_warning = now
        self._skipped = 0
        return True

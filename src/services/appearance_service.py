"""Business logic for bot appearance requests."""

from typing import Any, Optional


class AppearanceService:
    """Holds appearance change requests until they are reviewed."""

    def __init__(self) -> None:
        self._pending: dict[str, dict[Any, Any]] = {}

    def add_request(self, request_id: str, data: dict[Any, Any]) -> None:
        """Add a request awaiting review."""
        self._pending[request_id] = data

    def get_request(self, request_id: str) -> Optional[dict[Any, Any]]:
        """Get a request."""
        return self._pending.get(request_id)

    def remove_request(self, request_id: str) -> Optional[dict[Any, Any]]:
        """Remove a request and return it."""
        return self._pending.pop(request_id, None)

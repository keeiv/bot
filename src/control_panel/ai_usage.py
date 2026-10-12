"""AI usage shown beside Nova on the panel.

There is no AI model behind the bot yet, so the only source is
:class:`NoUsageSource`, which reports nothing. This module is the place to plug
one in later: write a class with a ``read()`` method that returns an
:class:`AiUsage`, and pass it to ``ControlPanel(ai_source=...)``. The panel
reads it once a tick, so ``read()`` must be quick and must not raise.
"""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class AiUsage:
    model: Optional[str] = None  # a hosted model, by name
    local_model: Optional[str] = None  # a model running on this machine
    used: Optional[float] = None  # how much of the allowance is spent
    limit: Optional[float] = None  # the allowance; None when there is none
    unit: str = ""  # what ``used`` and ``limit`` count, e.g. "tokens"

    @property
    def connected(self) -> bool:
        return bool(self.model or self.local_model)

    @property
    def fraction(self) -> Optional[float]:
        """Share of the allowance used, or None when it cannot be measured."""
        if self.used is None or not self.limit or self.limit <= 0:
            return None
        return min(max(self.used / self.limit, 0.0), 1.0)


NO_USAGE = AiUsage()


class UsageSource(Protocol):
    def read(self) -> AiUsage: ...


class NoUsageSource:
    """No model is connected: always "no model, no local model"."""

    def read(self) -> AiUsage:
        return NO_USAGE

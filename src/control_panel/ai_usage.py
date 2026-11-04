"""AI usage shown beside Nova on the panel.

The bot asks Claude and GPT through their command-line tools and writes what
each did today to ``data/ai_usage.json`` (``src.services.ai_cli.UsageLog``).
:class:`BotUsageSource` reads that file for the panel; with no file (the bot
has never used a model, or the tools are not installed) Nova keeps resting.

Neither tool reports how much of the subscription is left, so the bar only
fills when ``BOT_AI_DAILY_TOKENS`` sets a daily budget of tokens to compare
against; otherwise the panel shows today's token count.

The panel reads a source once a tick, so ``read()`` must be quick and must not
raise. :class:`NoUsageSource` is the "nothing connected" source.
"""

from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Optional, Protocol

from dotenv import dotenv_values

USAGE_FILE = Path("data") / "ai_usage.json"
NAMES = (("claude", "Claude"), ("gpt", "GPT"))


@dataclass(frozen=True)
class AiUsage:
    model: Optional[str] = None  # a hosted model, by name
    local_model: Optional[str] = None  # a model running on this machine
    used: Optional[float] = None  # how much of the allowance is spent
    limit: Optional[float] = None  # the allowance; None when there is none
    unit: str = ""  # what ``used`` and ``limit`` count, e.g. "tokens"
    note: str = ""  # the status line when there is no fraction to show

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


def short_count(value: float) -> str:
    """12345 -> "12.3k", 279600 -> "280k", 2500000 -> "2.5M": at most 5 cells."""
    if value >= 999_500:
        return f"{value / 1_000_000:.1f}M"
    if value >= 99_950:
        return f"{value / 1_000:.0f}k"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(int(value))


class BotUsageSource:
    """Today's Claude and GPT use, from the file the bot writes."""

    def __init__(
        self,
        root: Path,
        *,
        today: Callable[[], date] = date.today,
        now: Callable[[], float] = time.time,
        environ: Optional[dict[str, str]] = None,
    ) -> None:
        self.path = Path(root) / USAGE_FILE
        self._today = today
        self._now = now
        self._environ = os.environ if environ is None else environ
        self._seen: Optional[tuple[float, int]] = None
        self._data: Any = None
        # The budget the way the bot sees settings: real environment, then .env.
        budget = self._environ.get("BOT_AI_DAILY_TOKENS")
        if budget is None and environ is None:
            budget = dotenv_values(Path(root) / ".env").get("BOT_AI_DAILY_TOKENS")
        self._budget = budget or ""

    def _read_file(self) -> Any:
        try:
            stat = self.path.stat()
        except OSError:
            return None
        stamp = (stat.st_mtime, stat.st_size)
        if stamp != self._seen:  # only re-read when the bot wrote something new
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._data = None
            self._seen = stamp
        return self._data

    def _limit(self) -> Optional[float]:
        try:
            value = float(self._budget)
        except ValueError:
            return None
        return value if value > 0 else None

    def read(self) -> AiUsage:
        data = self._read_file()
        providers = data.get("providers") if isinstance(data, dict) else None
        if not isinstance(providers, dict):
            return NO_USAGE
        today = data.get("date") == self._today().isoformat()
        present, resting, tokens = [], [], 0
        for key, name in NAMES:
            entry = providers.get(key)
            if not isinstance(entry, dict) or entry.get("installed") is not True:
                continue
            present.append(name)
            down = entry.get("down_until")
            if isinstance(down, (int, float)) and down > self._now():
                resting.append(name)
            count = entry.get("tokens")
            if today and type(count) is int and count > 0:
                tokens += count
        if not present:
            return NO_USAGE
        # The status line is 10 cells wide: "Claude維護" just fits.
        if resting:
            note = "維護中" if len(resting) == len(present) else f"{resting[0]}維護"
        else:
            note = f"今日 {short_count(tokens)}"
        return AiUsage(
            model="·".join(present),
            used=tokens,
            limit=self._limit(),
            unit="tokens",
            note=note,
        )

"""Bot-wide language support: which language to use, and the message catalogue.

Two languages are supported: English ("en", the default for new servers and the
fallback) and Traditional Chinese ("zh"). Messages live in ``src/locales`` as
``{key: {"en": ..., "zh": ...}}`` tables and are looked up with :func:`t`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, Optional

import discord

from src.locales import MESSAGES

Lang = Literal["en", "zh"]
LANGS: tuple[Lang, ...] = ("en", "zh")
DEFAULT_LANG: Lang = "en"

# Service helpers also run in asyncio.to_thread, which copies this context.
# The legacy default keeps direct service calls and Chinese web APIs compatible.
_language: ContextVar[Lang] = ContextVar("bot_reply_language", default="zh")


def current_lang() -> Lang:
    """Return the language of this command, notification or component callback."""
    return _language.get()


@contextmanager
def language_scope(lang: Lang) -> Iterator[None]:
    """Keep a language local to the current task, including cancellation paths."""
    if not is_lang(lang):
        raise ValueError(f"Unsupported language: {lang}")
    token = _language.set(lang)
    try:
        yield
    finally:
        _language.reset(token)


# Shown in pickers in their own language, so a reader can always find theirs.
LANG_NAMES: dict[Lang, str] = {"en": "English", "zh": "中文"}

_ZH_LOCALES = {discord.Locale.taiwan_chinese, discord.Locale.chinese}


def from_locale(locale: Optional[discord.Locale]) -> Lang:
    """Map a Discord client locale to a supported language."""
    return "zh" if locale in _ZH_LOCALES else "en"


def is_lang(value: object) -> bool:
    return value in LANGS


def t(lang: Lang, key: str, /, **values: object) -> str:
    """Return the message ``key`` in ``lang``, falling back to English.

    A missing key is a programming error and raises ``KeyError``; the catalogue
    test checks that every key has both languages and the same placeholders.
    """
    entry = MESSAGES[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**values) if values else text


def text(key: str, /, **values: object) -> str:
    """Translate bot-owned copy in the current language scope."""
    return t(current_lang(), key, **values)

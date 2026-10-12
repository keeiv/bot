"""Translate declared component labels; never translate user-provided values."""

from typing import ClassVar

import discord

from src.utils.i18n import current_lang
from src.utils.i18n import t


class ComponentTranslations:
    i18n: ClassVar[dict[str, str]] = {}

    def localize_components(self) -> None:
        self.lang = current_lang()
        for path, key in self.i18n.items():
            target = self
            parts = path.split(".")
            for name in parts[:-1]:
                target = getattr(target, name)
            setattr(target, parts[-1], t(self.lang, key))


class LocalizedView(ComponentTranslations, discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.localize_components()


class LocalizedModal(ComponentTranslations, discord.ui.Modal):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.localize_components()

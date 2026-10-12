"""Discord localizations for command descriptions, options and context menus.

discord.py calls :meth:`translate` for every string while syncing the command
tree and sends the results as ``*_localizations``. Discord then shows them to
members whose client language is Chinese; everyone else sees the English
defaults written in the cogs.
"""

from typing import Optional

import discord
from discord import app_commands

from src.locales.commands import CONTEXT_MENU_NAMES
from src.locales.commands import TEXT

_ZH = {discord.Locale.taiwan_chinese, discord.Locale.chinese}
_Location = app_commands.TranslationContextLocation


class CommandTranslator(app_commands.Translator):
    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContextTypes,
    ) -> Optional[str]:
        if locale not in _ZH:
            return None
        message = string.message
        if context.location in (_Location.command_name, _Location.group_name):
            # Slash command names stay English; context menus are labels.
            data = context.data
            is_menu = isinstance(data, app_commands.ContextMenu)
            return CONTEXT_MENU_NAMES.get(message) if is_menu else None
        if context.location is _Location.parameter_name:
            return None
        return TEXT.get(message)

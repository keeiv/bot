"""Message catalogue, merged from one module per area of the bot.

Each module defines ``MESSAGES = {key: {"en": ..., "zh": ...}}``. Keys are
namespaced by area (``guide.*``, ``language.*``) so modules cannot collide; the
merge below refuses duplicates instead of silently overwriting.

Catalogues that are present on disk but not listed here (features kept only on
one machine and left out of the repository) are found and merged as well.
"""

import importlib
import pkgutil

from src.locales import achievements_messages
from src.locales import admin_messages
from src.locales import age_guard_messages
from src.locales import anti_spam_messages
from src.locales import audit_log_messages
from src.locales import blacklist_messages
from src.locales import blacklist_service_messages
from src.locales import bot_appearance_messages
from src.locales import core
from src.locales import dashboard_api_messages
from src.locales import dashboard_checks_messages
from src.locales import dashboard_service_messages
from src.locales import deep_sea_oxygen_messages
from src.locales import developer_messages
from src.locales import domain
from src.locales import error_handler_messages
from src.locales import file_tools_messages
from src.locales import genshin_cog_messages
from src.locales import genshin_service_messages
from src.locales import github_watch_messages
from src.locales import giveaway_messages
from src.locales import help as help_messages
from src.locales import info
from src.locales import management_messages
from src.locales import management_service_messages
from src.locales import message_log_service_messages
from src.locales import message_logger_messages
from src.locales import novagrid_messages
from src.locales import osu_info_messages
from src.locales import osu_service_messages
from src.locales import report_messages
from src.locales import report_service_messages
from src.locales import russian_roulette_messages
from src.locales import settings_messages
from src.locales import temp_voice_messages
from src.locales import ticket_messages
from src.locales import ticket_service_messages
from src.locales import tool_card_messages
from src.locales import tool_protocol_messages
from src.locales import tool_quota_messages
from src.locales import tool_remote_messages
from src.locales import tool_routes_messages
from src.locales import tool_worker_messages

_MODULES = [
    core,
    help_messages,
    info,
    domain,
    achievements_messages,
    admin_messages,
    age_guard_messages,
    anti_spam_messages,
    audit_log_messages,
    blacklist_messages,
    blacklist_service_messages,
    bot_appearance_messages,
    dashboard_api_messages,
    dashboard_checks_messages,
    dashboard_service_messages,
    deep_sea_oxygen_messages,
    developer_messages,
    error_handler_messages,
    file_tools_messages,
    genshin_cog_messages,
    genshin_service_messages,
    github_watch_messages,
    giveaway_messages,
    management_messages,
    management_service_messages,
    message_log_service_messages,
    message_logger_messages,
    novagrid_messages,
    osu_info_messages,
    osu_service_messages,
    report_messages,
    report_service_messages,
    russian_roulette_messages,
    settings_messages,
    temp_voice_messages,
    ticket_messages,
    ticket_service_messages,
    tool_card_messages,
    tool_protocol_messages,
    tool_quota_messages,
    tool_remote_messages,
    tool_routes_messages,
    tool_worker_messages,
]
_LISTED = {_module.__name__ for _module in _MODULES}
for _found in sorted(pkgutil.iter_modules(__path__), key=lambda found: found.name):
    _name = f"{__name__}.{_found.name}"
    if _found.name.endswith("_messages") and _name not in _LISTED:
        _MODULES.append(importlib.import_module(_name))

MESSAGES: dict[str, dict[str, str]] = {}
for _module in _MODULES:
    for _key, _value in _module.MESSAGES.items():
        if _key in MESSAGES:
            raise ValueError(f"Duplicate message key: {_key}")
        MESSAGES[_key] = _value

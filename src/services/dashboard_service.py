"""Dashboard adapter: write the running cogs' real stores, one section at a time."""

import hashlib
import json
import re
from string import Formatter
from typing import Any

import discord

from src.utils.i18n import text as tx

MAPPINGS = {
    "welcome": (
        "Management",
        "data/storage/management.json",
        {
            "channel": ("channel_id", ""),
            "message": ("message", "歡迎 {user} 加入 {server}！"),
            "sendDm": ("send_dm", False),
            "autoRole": ("auto_role_id", ""),
        },
    ),
    "antispam": (
        "AntiSpam",
        "data/storage/anti_spam_settings.json",
        {
            "enabled": ("enabled", True),
            "floodMessages": ("flood_messages", 10),
            "floodWindow": ("flood_window", 10),
            "action": ("flood_action", "mute"),
            "mentionLimit": ("mention_limit", 8),
            "inviteAutoDelete": ("invite_auto_delete", True),
            "raidEnabled": ("raid_enabled", True),
        },
    ),
    "ageguard": (
        "AgeGuard",
        "data/storage/age_guard.json",
        {
            "enabled": ("enabled", False),
            "adultRole": ("adult_role_id", ""),
            "punishRole": ("punishment_role_id", ""),
        },
    ),
    "tempvoice": (
        "TempVoice",
        "data/storage/temp_voice.json",
        {
            "triggerChannel": ("trigger_channel_id", ""),
            "nameTemplate": ("name_template", "{username} 的頻道"),
        },
    ),
    "ticket": (
        "Ticket",
        "data/storage/tickets.json",
        {
            "channel": ("channel_id", ""),
            "staffRole": ("role_id", ""),
        },
    ),
    "github": (
        "GithubWatch",
        "data/storage/github_watch.json",
        {
            "enabled": ("enabled", False),
            "owner": ("owner", ""),
            "repo": ("repo", ""),
            "channel": ("channel_id", ""),
            "intervalMinutes": ("interval_minutes", 2),
        },
    ),
    "audit": (
        "AuditLog",
        "data/storage/log_channels.json",
        {"channel": ("channel_id", "")},
    ),
}
ID_FIELDS = {
    "channel",
    "autoRole",
    "adultRole",
    "punishRole",
    "triggerChannel",
    "staffRole",
}


def revision(settings: dict) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


class DashboardService:
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    def _cog(self, section):
        cog = self.bot.get_cog(MAPPINGS[section][0])
        if cog is None:
            raise RuntimeError(
                tx("dashboard_checks.the_module_is_not_loaded", v0=(section))
            )
        return cog

    def get_section_config(self, section, guild_id):
        """Read public service snapshots instead of accessing cog caches."""
        cog = self._cog(section)
        if section == "welcome":
            return cog.service.get_welcome_config(str(guild_id))
        if section == "antispam":
            return cog.manager.get_settings(guild_id)
        if section == "audit":
            channel_id = cog.service.get_channel_id(guild_id)
            return {"channel_id": channel_id} if channel_id else {}
        if section in ("tempvoice", "ticket"):
            return cog.service.get_guild_config(guild_id) or {}
        return cog.service.get_config(guild_id)

    def read(self, guild_id: int) -> dict:
        result = {}
        for section, (_, _, fields) in MAPPINGS.items():
            raw = self.get_section_config(section, guild_id)
            values = {
                k: raw.get(native, default) for k, (native, default) in fields.items()
            }
            for field in ID_FIELDS & values.keys():
                values[field] = str(values[field]) if values[field] else ""
            values.setdefault("enabled", bool(raw) and raw.get("enabled", True))
            result[section] = values
        return result

    def set_ticket_panel(self, guild_id, message_id, expected):
        self._cog("ticket").service.set_panel_message(guild_id, message_id, expected)

    def validate(self, guild: Any, section: str, values: Any) -> dict:
        if (
            not isinstance(section, str)
            or section not in MAPPINGS
            or not isinstance(values, dict)
        ):
            raise ValueError(tx("dashboard_service.unknown_settings_section"))
        fields = MAPPINGS[section][2]
        if set(values) != set(fields) | {"enabled"}:
            raise ValueError(tx("dashboard_service.missing_or_unknown_settings_fields"))
        for key, value in values.items():
            default = fields.get(key, ("", False))[1]
            if type(value) is not type(default):
                raise ValueError(tx("dashboard_service.invalid_format", v0=(key)))
            if isinstance(value, str) and len(value) > 1800:
                raise ValueError(tx("dashboard_service.is_too_long", v0=(key)))
            if key in ID_FIELDS and value:
                if not re.fullmatch(r"[0-9]{17,20}", value):
                    raise ValueError(
                        tx("dashboard_service.must_be_a_discord_id", v0=(key))
                    )
                if "Role" in key:
                    role = guild.get_role(int(value))
                    if role is None or role.is_default():
                        raise ValueError(
                            tx(
                                "dashboard_service.the_role_does_not_belong_to",
                                v0=(key),
                            )
                        )
                    if key != "staffRole" and (
                        not guild.me.guild_permissions.manage_roles
                        or role.managed
                        or role >= guild.me.top_role
                        or role.permissions.administrator
                    ):
                        raise ValueError(
                            tx(
                                "dashboard_service.the_role_must_be_manageable_by",
                                v0=(key),
                            )
                        )
                else:
                    channel = guild.get_channel(int(value))
                    expected = (
                        discord.VoiceChannel
                        if key == "triggerChannel"
                        else discord.TextChannel
                    )
                    if not isinstance(channel, expected):
                        raise ValueError(
                            tx(
                                "dashboard_service.the_channel_has_the_wrong_type",
                                v0=(key),
                            )
                        )
                    perms = channel.permissions_for(guild.me)
                    required = (
                        ("view_channel", "connect", "manage_channels", "move_members")
                        if key == "triggerChannel"
                        else ("view_channel", "send_messages", "embed_links")
                    )
                    if section == "ticket":
                        required += (
                            "create_private_threads",
                            "send_messages_in_threads",
                            "manage_threads",
                        )
                    if not all(getattr(perms, p) for p in required):
                        raise ValueError(
                            tx(
                                "dashboard_service.the_bot_lacks_required_permissions_in",
                                v0=(key),
                            )
                        )
        for key, bounds in {
            "floodMessages": (1, 50),
            "floodWindow": (1, 60),
            "mentionLimit": (1, 20),
            "intervalMinutes": (2, 60),
        }.items():
            if key in values and not bounds[0] <= values[key] <= bounds[1]:
                raise ValueError(
                    tx(
                        "dashboard_service.must_be_between_and",
                        v0=(key),
                        v1=(bounds[0]),
                        v2=(bounds[1]),
                    )
                )
        if section == "antispam" and values["action"] not in (
            "warn",
            "delete",
            "mute",
            "kick",
            "ban",
        ):
            raise ValueError(tx("dashboard_service.invalid_spam_protection_action"))
        required = {
            "welcome": ["channel", "message"],
            "tempvoice": ["triggerChannel", "nameTemplate"],
            "ticket": ["channel", "staffRole"],
            "github": ["owner", "repo", "channel"],
            "ageguard": ["adultRole", "punishRole"],
            "audit": ["channel"],
        }
        if values["enabled"] and any(
            not values[k].strip() for k in required.get(section, [])
        ):
            raise ValueError(
                tx("dashboard_service.complete_all_required_fields_before_enabling")
            )
        if section == "welcome":
            for _, field, spec, conversion in Formatter().parse(values["message"]):
                if field is not None and (
                    field not in {"user", "username", "server", "count", "created_at"}
                    or spec
                    or conversion
                ):
                    raise ValueError(
                        tx(
                            "dashboard_service.the_welcome_message_contains_unsupported_variables"
                        )
                    )
        if section == "tempvoice" and len(values["nameTemplate"]) > 100:
            raise ValueError(
                tx("dashboard_service.voice_channel_names_must_not_exceed")
            )
        if section == "github" and values["enabled"]:
            if not re.fullmatch(
                r"[A-Za-z0-9-]{1,39}", values["owner"]
            ) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", values["repo"]):
                raise ValueError(
                    tx("dashboard_service.invalid_github_owner_or_repository_name")
                )
        return values

    def write(self, guild: Any, section: str, values: dict) -> None:
        values = self.validate(guild, section, values)
        cog = self._cog(section)
        fields = MAPPINGS[section][2]
        mapped = {
            native: (
                (int(values[k]) if values[k] else None) if k in ID_FIELDS else values[k]
            )
            for k, (native, _) in fields.items()
        }
        if section == "welcome":
            if values["enabled"]:
                cog.service.update_welcome_config(str(guild.id), mapped)
            else:
                cog.service.clear_welcome_config(str(guild.id))
        elif section == "antispam":
            cog.manager.update_settings(guild.id, mapped)
        elif section == "audit":
            cog.service.set_channel_id(
                guild.id, mapped["channel_id"] if values["enabled"] else None
            )
            logger = self.bot.get_cog("MessageLogger")
            if logger:
                logger.service.invalidate_log_channels()
        elif section == "tempvoice":
            if not values["enabled"]:
                cog.service.remove_guild_config(guild.id)
            else:
                existing = cog.service.get_guild_config(guild.id) or {}
                if "category_id" not in existing:
                    mapped["category_id"] = guild.get_channel(
                        int(values["triggerChannel"])
                    ).category_id
                cog.service.update_guild_config(guild.id, {**mapped, "enabled": True})
        elif section == "ticket":
            cog.service.update_guild_config(
                guild.id, {**mapped, "enabled": values["enabled"]}
            )
        else:
            cog.service.update_config(guild.id, mapped)
            if section == "github":
                cog.reset_poll(guild.id)

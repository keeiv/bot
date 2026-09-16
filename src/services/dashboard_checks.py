"""Read-only diagnostics using the same validators as settings writes."""

import discord

from src.services.dashboard_service import MAPPINGS


def resources(guild):
    return {
        "channels": [
            {
                "id": str(channel.id),
                "name": channel.name,
                "kind": (
                    "voice" if isinstance(channel, discord.VoiceChannel) else "text"
                ),
            }
            for channel in guild.channels
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel))
        ],
        "roles": [
            {
                "id": str(role.id),
                "name": role.name,
                "assignable": bool(
                    not role.managed
                    and role < guild.me.top_role
                    and not role.permissions.administrator
                    and guild.me.guild_permissions.manage_roles
                ),
            }
            for role in guild.roles
            if not role.is_default()
        ],
        "memberCount": guild.member_count or 0,
    }


def inspect_settings(service, guild, settings):
    if not isinstance(settings, dict) or set(settings) != set(MAPPINGS):
        raise ValueError("Invalid settings document")
    checks = []
    for section, values in settings.items():
        if service.bot.get_cog(MAPPINGS[section][0]) is None:
            checks.append(
                {
                    "section": section,
                    "ok": False,
                    "code": "invalid_settings",
                    "detail": f"{section} 模組未載入",
                }
            )
            continue
        try:
            service.validate(guild, section, values)
            checks.append({"section": section, "ok": True, "code": "settings_valid"})
        except ValueError as error:
            checks.append(
                {
                    "section": section,
                    "ok": False,
                    "code": "invalid_settings",
                    "detail": str(error),
                }
            )
            continue
        if not values["enabled"]:
            continue
        permissions = []
        if section == "antispam":
            action = values["action"]
            permissions = {
                "delete": ["manage_messages"],
                "mute": ["moderate_members"],
                "kick": ["kick_members"],
                "ban": ["ban_members"],
            }.get(action, [])
            if values["inviteAutoDelete"]:
                permissions.append("manage_messages")
            if values["raidEnabled"]:
                permissions.append("manage_channels")
        for permission in sorted(set(permissions)):
            checks.append(
                {
                    "section": section,
                    "ok": bool(getattr(guild.me.guild_permissions, permission)),
                    "code": "permission",
                    "detail": permission,
                }
            )
        intents = {
            "welcome": ["members"],
            "antispam": ["message_content"],
            "ageguard": ["message_content"],
            "audit": ["message_content"],
        }.get(section, [])
        if section == "antispam" and values["raidEnabled"]:
            intents.append("members")
        for intent in intents:
            checks.append(
                {
                    "section": section,
                    "ok": bool(getattr(service.bot.intents, intent)),
                    "code": "intent",
                    "detail": intent,
                }
            )
    return {"checks": checks}

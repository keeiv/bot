"""Global command sync that keeps the activity's Entry Point command.

Turning on Activities gives the app a PRIMARY_ENTRY_POINT command (type 4), the
"Launch" entry Discord shows in the app launcher. discord.py does not know that
type, and its ``CommandTree.sync`` overwrites the whole global list, which would
drop the Entry Point or have the update refused. This sync sends the same payload
as discord.py plus whatever Entry Point Discord already holds, unchanged.
"""

from typing import Any

from discord import HTTPException
from discord.app_commands import AppCommand
from discord.app_commands import CommandSyncFailure
from discord.app_commands import CommandTree
from discord.app_commands import MissingApplicationID

ENTRY_POINT = 4
# The fields a bulk overwrite accepts for an existing command; read-only ones such
# as application_id and version are left out.
KEEP = (
    "id",
    "name",
    "name_localizations",
    "description",
    "description_localizations",
    "type",
    "handler",
    "integration_types",
    "contexts",
    "nsfw",
)


def entry_points(existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The registered Entry Point commands, reduced to what can be sent back."""
    return [
        {key: command[key] for key in KEEP if command.get(key) is not None}
        for command in existing
        if command.get("type") == ENTRY_POINT
    ]


async def sync_global(tree: CommandTree) -> list[AppCommand]:
    """Sync global commands like ``tree.sync()``, carrying the Entry Point along."""
    client = tree.client
    if client.application_id is None:
        raise MissingApplicationID
    # discord.py has no public hook for extra payload entries, so this follows
    # CommandTree.sync step by step.
    commands = tree._get_all_commands(guild=None)
    translator = tree.translator
    if translator:
        payload = [
            await command.get_translated_payload(tree, translator)
            for command in commands
        ]
    else:
        payload = [command.to_dict(tree) for command in commands]
    existing = await client.http.get_global_commands(client.application_id)
    payload += entry_points([dict(command) for command in existing])
    try:
        data = await client.http.bulk_upsert_global_commands(
            client.application_id, payload=payload
        )
    except HTTPException as error:
        if error.status == 400 and error.code == 50035:
            raise CommandSyncFailure(error, commands) from None
        raise
    return [
        AppCommand(data=item, state=tree._state)
        for item in data
        if item.get("type") != ENTRY_POINT
    ]

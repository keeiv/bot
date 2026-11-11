"""Arknights: Endfield: public business cards and showcased operators through Enka.Network."""

from datetime import datetime
from datetime import timezone
import logging
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.services.endfield_service import Account
from src.services.endfield_service import EndfieldError
from src.services.endfield_service import EndfieldService
from src.services.endfield_service import Operator
from src.services.endfield_service import Profile
from src.services.endfield_service import UID_RE
from src.utils.i18n import current_lang
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedModal
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

COLOR = discord.Color.from_rgb(255, 196, 0)  # Endfield's warning yellow
ENKA_PAGE = "https://enka.network/ef/{uid}"
TOKEN_PAGE = "https://web-api.skport.com/cookie_store/account_token"
SKPORT_SITE = "https://www.skport.com"
ROSTER_LIMIT = 4000  # characters of operators on one reply; any others are counted


def _stars(rarity: int) -> str:
    return "★" * max(0, min(rarity, 6))


def operator_line(op: Operator) -> str:
    return tx(
        "endfield.operator_line",
        v0=(op.name),
        v1=(_stars(op.rarity)),
        v2=(op.level),
        v3=(op.potential),
        v4=(op.element),
        v5=(op.profession),
    )


def profile_embed(profile: Profile) -> discord.Embed:
    embed = discord.Embed(
        title=tx("endfield.profile_title", v0=(profile.name or profile.uid)),
        description=profile.signature or None,
        url=ENKA_PAGE.format(uid=profile.uid),
        color=COLOR,
        timestamp=datetime.fromtimestamp(profile.read_at, timezone.utc),
    )
    embed.add_field(name="UID", value=profile.uid, inline=True)
    embed.add_field(
        name=tx("endfield.region"), value=profile.region or "?", inline=True
    )
    embed.add_field(
        name=tx("endfield.authority_level"),
        value=str(profile.adventure_level),
        inline=True,
    )
    embed.add_field(
        name=tx("endfield.world_level"), value=str(profile.world_level), inline=True
    )
    embed.add_field(
        name=tx("endfield.owned"),
        value=tx(
            "endfield.owned_value",
            v0=(profile.operators_owned),
            v1=(profile.weapons_owned),
        ),
        inline=True,
    )
    showcase = "\n".join(operator_line(op) for op in profile.showcase)
    embed.add_field(
        name=tx("endfield.showcase", v0=(len(profile.showcase))),
        value=showcase or tx("endfield.showcase_empty"),
        inline=False,
    )
    embed.set_footer(text=tx("endfield.footer"))
    return embed


def operator_embed(name: str, uid: str, read_at: float, op: Operator) -> discord.Embed:
    embed = discord.Embed(
        title=f"{op.name} {_stars(op.rarity)}",
        description=tx(
            "endfield.operator_kind",
            v0=(op.element),
            v1=(op.profession),
            v2=(op.weapon_type),
        ),
        color=COLOR,
        timestamp=datetime.fromtimestamp(read_at, timezone.utc),
    )
    embed.add_field(name=tx("endfield.level"), value=str(op.level), inline=True)
    embed.add_field(name=tx("endfield.potential"), value=str(op.potential), inline=True)
    if op.weapon:
        embed.add_field(
            name=tx("endfield.weapon"),
            value=tx(
                "endfield.weapon_value",
                v0=(op.weapon.name),
                v1=(_stars(op.weapon.rarity)),
                v2=(op.weapon.level),
                v3=(op.weapon.potential),
            ),
            inline=False,
        )
    if op.sets:
        embed.add_field(
            name=tx("endfield.gear_sets"),
            value="\n".join(f"{name} ×{count}" for name, count in op.sets),
            inline=False,
        )
    if op.skills:
        embed.add_field(
            name=tx("endfield.skills"),
            value="\n".join(f"{kind} Lv{level}" for kind, level in op.skills),
            inline=False,
        )
    embed.set_footer(text=tx("endfield.operator_footer", v0=(name), v1=(uid)))
    return embed


def find_operator(operators: list[Operator], name: str) -> Optional[Operator]:
    wanted = name.strip().casefold()
    for op in operators:
        if op.name.casefold() == wanted:
            return op
    return next((op for op in operators if wanted in op.name.casefold()), None)


def roster_embed(account: Account) -> discord.Embed:
    lines: list[str] = []
    size = 0
    for op in account.operators:
        line = operator_line(op)
        size += len(line) + 1
        if size > ROSTER_LIMIT:
            break
        lines.append(line)
    embed = discord.Embed(
        title=tx("endfield.roster_title", v0=(account.name or account.uid)),
        description="\n".join(lines) or tx("endfield.nobody"),
        color=COLOR,
        timestamp=datetime.fromtimestamp(account.read_at, timezone.utc),
    )
    embed.add_field(
        name=tx("endfield.owned"),
        value=tx("endfield.operators_owned", v0=(len(account.operators))),
        inline=True,
    )
    if account.stamina is not None:
        embed.add_field(
            name=tx("endfield.stamina"),
            value=f"{account.stamina}/{account.stamina_max}",
            inline=True,
        )
    hidden = len(account.operators) - len(lines)
    embed.set_footer(
        text=(
            tx("endfield.roster_more", v0=(hidden))
            if hidden > 0
            else tx("endfield.roster_footer")
        )
    )
    return embed


class TokenModal(LocalizedModal):
    """The account token is entered only in this private window, never as a command argument."""

    def __init__(self, cog: "EndfieldCog") -> None:
        super().__init__(title=tx("endfield.link_title"))
        self.cog = cog
        self.token = discord.ui.TextInput[Any](
            label=tx("endfield.link_label"),
            style=discord.TextStyle.paragraph,
            placeholder=tx("endfield.link_placeholder"),
            required=True,
            max_length=4000,
        )
        self.add_item(self.token)

    @localized("interaction")
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.cog.link_token(interaction, self.token.value)


class EndfieldCog(commands.Cog):
    """Arknights: Endfield: link a UID or an account, look up cards and operators."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = EndfieldService()

    async def cog_unload(self) -> None:
        await self.service.close()

    endfield = app_commands.Group(
        name="endfield", description="Arknights: Endfield profiles and operators"
    )

    async def _uid(
        self, interaction: discord.Interaction, uid: Optional[str]
    ) -> Optional[str]:
        """The UID asked for, or the member's own; None after explaining why not."""
        if uid:
            uid = uid.strip()
            if UID_RE.match(uid):
                return uid
            await interaction.followup.send(
                tx("endfield.error_bad_uid"), ephemeral=True
            )
            return None
        own = await run_storage(self.service.bound_uid, interaction.user.id)
        if own is None:
            await interaction.followup.send(tx("endfield.not_bound"), ephemeral=True)
        return own

    async def _profile(
        self, interaction: discord.Interaction, uid: str
    ) -> Optional[Profile]:
        try:
            return await self.service.profile(uid, current_lang())
        except EndfieldError as error:
            await interaction.followup.send(
                tx(f"endfield.error_{error.code}"), ephemeral=True
            )
        except Exception:
            logger.exception("Endfield profile %s failed", uid)
            await interaction.followup.send(
                tx("endfield.error_unavailable"), ephemeral=True
            )
        return None

    @endfield.command(name="bind", description="Link your Arknights: Endfield UID")
    @app_commands.describe(uid="The UID in the game's profile menu")
    @localized("interaction")
    async def bind(self, interaction: discord.Interaction, uid: str) -> None:
        await interaction.response.defer(ephemeral=True)
        uid = uid.strip()
        if not UID_RE.match(uid):
            await interaction.followup.send(
                tx("endfield.error_bad_uid"), ephemeral=True
            )
            return
        profile = None
        try:
            profile = await self.service.profile(uid, current_lang())
        except EndfieldError as error:
            if error.code in ("bad_uid", "not_found"):
                await interaction.followup.send(
                    tx(f"endfield.error_{error.code}"), ephemeral=True
                )
                return
            # Enka is busy or the game is down: the UID may well be right
        await run_storage(self.service.bind, interaction.user.id, uid)
        # The AI characters read the new link at once (see ai_chat).
        interaction.client.dispatch("endfield_bound", interaction.user.id)
        if profile is None:
            await interaction.followup.send(
                tx("endfield.bound_unchecked", v0=(uid)), ephemeral=True
            )
            return
        await interaction.followup.send(
            tx("endfield.bound", v0=(profile.name or uid)),
            embed=profile_embed(profile),
            ephemeral=True,
        )

    async def link_token(self, interaction: discord.Interaction, pasted: str) -> None:
        try:
            account = await self.service.link_account(
                interaction.user.id, pasted, current_lang()
            )
        except EndfieldError as error:
            await interaction.followup.send(
                tx(f"endfield.error_{error.code}"), ephemeral=True
            )
            return
        except Exception:
            logger.exception("Endfield account link failed for %s", interaction.user.id)
            await interaction.followup.send(
                tx("endfield.error_unavailable"), ephemeral=True
            )
            return
        interaction.client.dispatch("endfield_bound", interaction.user.id)
        await interaction.followup.send(
            tx("endfield.linked", v0=(len(account.operators))),
            embed=roster_embed(account),
            ephemeral=True,
        )

    @endfield.command(
        name="link",
        description="Link your SKPORT account to see every operator you own",
    )
    @localized("interaction")
    async def link(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(TokenModal(self))

    @endfield.command(
        name="tutorial", description="How to get your SKPORT account token"
    )
    @localized("interaction")
    async def tutorial(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title=tx("endfield.tutorial_title"),
                description=tx(
                    "endfield.tutorial_body", v0=(SKPORT_SITE), v1=(TOKEN_PAGE)
                ),
                color=COLOR,
            ),
            ephemeral=True,
        )

    @endfield.command(
        name="roster",
        description="List every Endfield operator you own (needs /endfield link)",
    )
    @localized("interaction")
    async def roster(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        account = await self._account(interaction)
        if account is None:
            if not await run_storage(self.service.has_account, interaction.user.id):
                await interaction.followup.send(
                    tx("endfield.not_linked"), ephemeral=True
                )
            return
        await interaction.followup.send(embed=roster_embed(account), ephemeral=True)

    async def _account(self, interaction: discord.Interaction) -> Optional[Account]:
        """The member's own card; None after explaining a failure, or with no link."""
        try:
            return await self.service.account(interaction.user.id, current_lang())
        except EndfieldError as error:
            await interaction.followup.send(
                tx(f"endfield.error_{error.code}"), ephemeral=True
            )
        except Exception:
            logger.exception("Endfield account read failed")
            await interaction.followup.send(
                tx("endfield.error_unavailable"), ephemeral=True
            )
        return None

    @endfield.command(name="unbind", description="Remove your Arknights: Endfield link")
    @localized("interaction")
    async def unbind(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        removed = await run_storage(self.service.unbind, interaction.user.id)
        if removed:
            interaction.client.dispatch("endfield_unbound", interaction.user.id)
        await interaction.followup.send(
            tx("endfield.unbound") if removed else tx("endfield.not_bound"),
            ephemeral=True,
        )

    @endfield.command(
        name="profile",
        description="Show an Arknights: Endfield business card and showcase",
    )
    @app_commands.describe(uid="Another UID (leave empty for your own)")
    @localized("interaction")
    async def profile(
        self, interaction: discord.Interaction, uid: Optional[str] = None
    ) -> None:
        await interaction.response.defer()
        target = await self._uid(interaction, uid)
        if target is None:
            return
        found = await self._profile(interaction, target)
        if found is not None:
            await interaction.followup.send(embed=profile_embed(found))

    @endfield.command(
        name="operator", description="Show one operator from an Endfield showcase"
    )
    @app_commands.describe(
        name="The operator's name", uid="Another UID (leave empty for your own)"
    )
    @localized("interaction")
    async def operator(
        self, interaction: discord.Interaction, name: str, uid: Optional[str] = None
    ) -> None:
        await interaction.response.defer()
        if not uid and await run_storage(self.service.has_account, interaction.user.id):
            account = await self._account(interaction)
            if account is None:
                return
            mine = find_operator(account.operators, name)
            if mine is not None:
                await interaction.followup.send(
                    embed=operator_embed(
                        account.name, account.uid, account.read_at, mine
                    )
                )
            else:
                await interaction.followup.send(
                    tx("endfield.operator_not_owned", v0=(name[:40])), ephemeral=True
                )
            return
        target = await self._uid(interaction, uid)
        if target is None:
            return
        found = await self._profile(interaction, target)
        if found is None:
            return
        op = find_operator(found.showcase, name)
        if op is None:
            shown = ", ".join(o.name for o in found.showcase) or tx("endfield.nobody")
            await interaction.followup.send(
                tx("endfield.operator_not_shown", v0=(name[:40]), v1=(shown)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=operator_embed(found.name, found.uid, found.read_at, op)
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EndfieldCog(bot))

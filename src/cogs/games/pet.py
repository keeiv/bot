"""夥伴：一人一隻、跨伺服器共用的養成與遠征"""

import asyncio
import logging
from typing import Any, Optional

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.services import pet_rules as rules
from src.services.pet_card import form_name
from src.services.pet_card import status_card
from src.services.pet_service import PetError
from src.services.pet_service import PetService
from src.utils.document_store import StorageError
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_storage

log = logging.getLogger(__name__)

COLORS = {
    "fable": discord.Color.from_rgb(233, 161, 77),
    "ark": discord.Color.from_rgb(66, 169, 164),
    "nova": discord.Color.from_rgb(255, 212, 79),
}
QUIET = discord.AllowedMentions.none()


async def call(function: Any, *args: Any) -> Any:
    """Run one storage step; a storage failure reads like any other refusal."""
    try:
        return await run_storage(function, *args)
    except StorageError:
        log.exception("Companion storage failed")
        raise PetError("storage") from None


def items_text(items: dict[str, int]) -> str:
    return ", ".join(
        tx("pet.item", name=tx(f"pet.material.{material}"), amount=items[material])
        for material in rules.MATERIALS
        if items.get(material)
    )


def refusal(error: PetError) -> str:
    values = dict(error.values)
    if error.code == "short":
        values = {"need": items_text(values["short"])}
    return tx(f"pet.error.{error.code}", **values)


def growth_lines(result: dict[str, Any], view: dict[str, Any]) -> list[str]:
    """What a step taught: levels, a new form, the cap, the keeper's level."""
    pet, lines = view["pet"], []
    if result.get("levels"):
        lines.append(tx("pet.level_up", name=pet["name"], level=pet["level"]))
    if result.get("evolved"):
        form = form_name(pet["species"], view["stage"], pet["mutated"])
        lines.append(tx("pet.evolved", name=pet["name"], form=form))
    if result.get("capped") and view["at_cap"]:
        lines.append(tx("pet.hit_cap"))
    if result.get("owner_levels"):
        lines.append(tx("pet.keeper_up", level=view["owner"]["level"]))
    return lines


def status_line(view: dict[str, Any]) -> str:
    pet, trip = view["pet"], view["trip"]
    if view["away"]:
        return tx("pet.panel.away")
    if trip:
        zone = tx(f"pet.zone.{trip['zone']}")
        if view["now"] >= trip["ends"]:
            return tx("pet.panel.trip_done", zone=zone)
        return tx("pet.panel.trip", zone=zone, until=int(trip["ends"]))
    if pet.get("nap"):
        return tx("pet.panel.napping", until=int(pet["nap"]))
    if (pet["satiety"] + pet["mood"]) / 2 < rules.SULK_BELOW:
        return tx("pet.panel.sulking")
    return tx("pet.panel.home")


def next_line(view: dict[str, Any]) -> str:
    pet, step = view["pet"], view["next_break"]
    if view["xp_needed"]:
        return tx(
            "pet.panel.next_level",
            left=view["xp_needed"] - pet["xp"],
            level=pet["level"] + 1,
        )
    if step is None:
        return tx("pet.panel.next_none")
    return tx(
        "pet.panel.next_break", at=step.at, owner=step.owner, cost=items_text(step.cost)
    )


async def panel(
    view: dict[str, Any], lines: Optional[list[str]] = None
) -> tuple[discord.Embed, discord.File]:
    pet, owner = view["pet"], view["owner"]
    embed = discord.Embed(
        title=pet["name"],
        description="\n".join(lines) if lines else None,
        color=COLORS[pet["species"]],
    )
    embed.add_field(name=tx("pet.panel.status"), value=status_line(view), inline=False)
    embed.add_field(
        name=tx("pet.panel.keeper"),
        value=tx(
            "pet.panel.keeper_value" if owner["needed"] else "pet.panel.keeper_max",
            level=owner["level"],
            into=owner["into"],
            needed=owner["needed"],
            coins=view["coins"],
        ),
        inline=True,
    )
    embed.add_field(name=tx("pet.panel.next"), value=next_line(view), inline=True)
    embed.set_image(url="attachment://pet.png")
    embed.set_footer(text=tx("pet.panel.footer"))
    card = await asyncio.to_thread(status_card, view)
    return embed, discord.File(card, filename="pet.png")


class PanelView(LocalizedView):
    """The buttons under a companion's card; only its keeper may press them."""

    i18n = {
        "feed.label": "pet.button.feed",
        "play.label": "pet.button.play",
        "nap.label": "pet.button.nap",
        "collect.label": "pet.button.collect",
        "refresh.label": "pet.button.refresh",
        "recall.label": "pet.button.recall",
    }

    def __init__(self, cog: "Pet", owner_id: int, view: dict[str, Any]) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.owner_id = owner_id
        if view["away"]:
            for button in (self.feed, self.play, self.nap, self.collect):
                self.remove_item(button)
        else:
            self.remove_item(self.recall)
            self.collect.disabled = not view["trip"]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await self._not_yours(interaction)
        return False

    @localized("interaction")
    async def _not_yours(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(tx("pet.not_yours"), ephemeral=True)

    async def _act(
        self, interaction: discord.Interaction, action: Any, message: Optional[str]
    ) -> None:
        await interaction.response.defer()
        try:
            result = await call(action, self.owner_id)
        except PetError as error:
            await interaction.followup.send(refusal(error), ephemeral=True)
            return
        view = result.get("view", result)
        lines = [tx(message, name=view["pet"]["name"])] if message else []
        if "loot" in result:
            lines = self.cog.collected_lines(result)
        lines += growth_lines(result, view)
        embed, card = await panel(view, lines)
        await interaction.edit_original_response(
            embed=embed,
            attachments=[card],
            view=PanelView(self.cog, self.owner_id, view),
        )

    @ui.button(label="Feed", style=discord.ButtonStyle.primary)
    @localized("interaction")
    async def feed(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._act(interaction, self.cog.service.feed, "pet.fed")

    @ui.button(label="Play", style=discord.ButtonStyle.primary)
    @localized("interaction")
    async def play(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._act(interaction, self.cog.service.play, "pet.played")

    @ui.button(label="Rest", style=discord.ButtonStyle.secondary)
    @localized("interaction")
    async def nap(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._act(interaction, self.cog.service.nap, "pet.napped")

    @ui.button(label="Collect", style=discord.ButtonStyle.success)
    @localized("interaction")
    async def collect(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        await self._act(interaction, self.cog.service.collect, None)

    @ui.button(label="Call it home", style=discord.ButtonStyle.success)
    @localized("interaction")
    async def recall(self, interaction: discord.Interaction, button: ui.Button) -> None:
        await self._act(interaction, self.cog.service.recall, "pet.recalled")

    @ui.button(label="Refresh", style=discord.ButtonStyle.secondary)
    @localized("interaction")
    async def refresh(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        await self._act(interaction, self.cog.service.view, None)


SPECIES_CHOICES = [
    app_commands.Choice(name="Fable", value="fable"),
    app_commands.Choice(name="Ark", value="ark"),
    app_commands.Choice(name="Nova", value="nova"),
]
ZONE_CHOICES = [
    app_commands.Choice(name="Breeze Meadow", value="breeze_meadow"),
    app_commands.Choice(name="Mistveil Mine", value="mistveil_mine"),
    app_commands.Choice(name="Frostvein Cavern", value="frostvein_cavern"),
    app_commands.Choice(name="Corona Ruins", value="corona_ruins"),
    app_commands.Choice(name="Streamsilver Abyss", value="streamsilver_abyss"),
]
TRIP_CHOICES = [
    app_commands.Choice(name="30 minutes", value="0.5"),
    app_commands.Choice(name="2 hours", value="2"),
    app_commands.Choice(name="8 hours", value="8"),
]
STAT_CHOICES = [
    app_commands.Choice(name="HP", value="hp"),
    app_commands.Choice(name="Attack", value="atk"),
    app_commands.Choice(name="Defence", value="def"),
    app_commands.Choice(name="Speed", value="spd"),
]
NATURE_CHOICES = [
    app_commands.Choice(name="Brave", value="brave"),
    app_commands.Choice(name="Fierce", value="fierce"),
    app_commands.Choice(name="Bold", value="bold"),
    app_commands.Choice(name="Steady", value="steady"),
    app_commands.Choice(name="Patient", value="patient"),
    app_commands.Choice(name="Guarded", value="guarded"),
    app_commands.Choice(name="Lively", value="lively"),
    app_commands.Choice(name="Nimble", value="nimble"),
    app_commands.Choice(name="Restless", value="restless"),
    app_commands.Choice(name="Hardy", value="hardy"),
    app_commands.Choice(name="Calm", value="calm"),
    app_commands.Choice(name="Gentle", value="gentle"),
]
SHOP_CHOICES = [
    app_commands.Choice(name="Stardust Sand", value=rules.SAND),
    app_commands.Choice(name="Aether Iron Ore", value=rules.IRON),
]


class Pet(commands.Cog):
    """夥伴養成"""

    # A personal companion: also usable in DMs and servers without the bot.
    pet = app_commands.Group(
        name="pet",
        description="Raise a companion and send it on expeditions",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        ),
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = PetService()

    # ── shared replies ────────────────────────────────────────────
    async def _refuse(self, interaction: discord.Interaction, error: PetError) -> None:
        await interaction.followup.send(refusal(error), ephemeral=True)

    async def _show(
        self,
        interaction: discord.Interaction,
        view: dict[str, Any],
        lines: Optional[list[str]] = None,
    ) -> None:
        embed, card = await panel(view, lines)
        await interaction.followup.send(
            embed=embed,
            file=card,
            view=PanelView(self, interaction.user.id, view),
            allowed_mentions=QUIET,
        )

    def collected_lines(self, result: dict[str, Any]) -> list[str]:
        view = result["view"]
        loot = items_text(result["loot"]) or tx("pet.found_nothing")
        return [
            tx(
                "pet.collected",
                name=view["pet"]["name"],
                zone=tx(f"pet.zone.{result['zone']}"),
            ),
            tx("pet.found_value", coins=result["coins"], loot=loot),
        ]

    async def _achieve(
        self, interaction: discord.Interaction, achievement: str
    ) -> None:
        """Achievements belong to servers; a step taken in a DM earns none."""
        cog = self.bot.get_cog("Achievements")
        if cog is None or interaction.guild_id is None:
            return
        try:
            await run_storage(
                cog.service.unlock,
                interaction.user.id,
                interaction.guild_id,
                achievement,
            )
        except Exception:
            log.exception("Could not record the %s achievement", achievement)

    async def _milestones(
        self, interaction: discord.Interaction, view: dict[str, Any]
    ) -> None:
        if view["stage"] == 3:
            await self._achieve(interaction, "pet_final_form")
        if view["pet"]["level"] >= rules.PET_MAX_LEVEL:
            await self._achieve(interaction, "pet_max_level")

    # ── beginning ─────────────────────────────────────────────────
    @pet.command(name="adopt", description="Adopt your companion: Fable, Ark or Nova")
    @app_commands.describe(
        species="Which companion to adopt",
        name="Its name, 1 to 12 characters (defaults to the species name)",
    )
    @app_commands.choices(species=SPECIES_CHOICES)
    @localized("interaction")
    async def adopt(
        self, interaction: discord.Interaction, species: str, name: Optional[str] = None
    ) -> None:
        await interaction.response.defer()
        try:
            view = await call(
                self.service.adopt,
                interaction.user.id,
                species,
                name or tx(f"pet.species.{species}"),
            )
        except PetError as error:
            await self._refuse(interaction, error)
            return
        pet = view["pet"]
        await self._achieve(interaction, "pet_adopt")
        await self._show(
            interaction,
            view,
            [
                tx(
                    "pet.adopted",
                    name=pet["name"],
                    species=tx(f"pet.species.{species}"),
                    nature=tx(f"pet.nature.{pet['nature']}"),
                ),
                tx(f"pet.about.{species}"),
            ],
        )

    @pet.command(name="panel", description="Show your companion and care for it")
    @localized("interaction")
    async def panel_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            view = await call(self.service.view, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        await self._show(interaction, view)

    @pet.command(name="recall", description="Call home a companion that wandered off")
    @localized("interaction")
    async def recall(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            view = await call(self.service.recall, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        await self._show(
            interaction, view, [tx("pet.recalled", name=view["pet"]["name"])]
        )

    @pet.command(name="rename", description="Rename your companion (100 coins)")
    @app_commands.describe(name="The new name, 1 to 12 characters")
    @localized("interaction")
    async def rename(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            view = await call(self.service.rename, interaction.user.id, name)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        await interaction.followup.send(
            tx("pet.renamed", name=view["pet"]["name"]), ephemeral=True
        )

    @pet.command(name="daily", description="Check in for coins once a day")
    @localized("interaction")
    async def daily(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            result = await call(self.service.daily, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        lines = [tx("pet.daily", streak=result["streak"], coins=result["coins"])]
        if result["loot"]:
            lines.append(items_text(result["loot"]))
        lines += growth_lines(result, result["view"])
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    # ── expeditions ───────────────────────────────────────────────
    @pet.command(name="expedition", description="Send your companion on an expedition")
    @app_commands.describe(
        zone="Where to go (new zones open with your keeper level)",
        duration="How long it stays out",
    )
    @app_commands.choices(zone=ZONE_CHOICES, duration=TRIP_CHOICES)
    @localized("interaction")
    async def expedition(
        self, interaction: discord.Interaction, zone: str, duration: str
    ) -> None:
        await interaction.response.defer()
        try:
            view = await call(
                self.service.depart, interaction.user.id, zone, float(duration)
            )
        except PetError as error:
            await self._refuse(interaction, error)
            return
        await self._show(
            interaction,
            view,
            [
                tx(
                    "pet.departed",
                    name=view["pet"]["name"],
                    zone=tx(f"pet.zone.{zone}"),
                    until=int(view["trip"]["ends"]),
                )
            ],
        )

    @pet.command(name="collect", description="Collect what an expedition found")
    @localized("interaction")
    async def collect(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.collect, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view = result["view"]
        await self._milestones(interaction, view)
        await self._show(
            interaction, view, self.collected_lines(result) + growth_lines(result, view)
        )

    @pet.command(name="boss", description="Fight a zone's guardian, once a day each")
    @app_commands.describe(zone="Whose guardian to fight")
    @app_commands.choices(zone=ZONE_CHOICES)
    @localized("interaction")
    async def boss(self, interaction: discord.Interaction, zone: str) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.challenge, interaction.user.id, zone)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view, name = result["view"], result["view"]["pet"]["name"]
        zone_name = tx(f"pet.zone.{zone}")
        if not result["won"]:
            await self._show(
                interaction, view, [tx("pet.boss_lost", name=name, zone=zone_name)]
            )
            return
        loot = items_text(result["loot"]) or tx("pet.found_nothing")
        lines = [
            tx(
                "pet.boss_won",
                name=name,
                zone=zone_name,
                rounds=result["fight"]["rounds"],
            ),
            tx("pet.found_value", coins=result["coins"], loot=loot),
        ]
        await self._milestones(interaction, view)
        await self._show(interaction, view, lines + growth_lines(result, view))

    # ── pack and shop ─────────────────────────────────────────────
    @pet.command(name="bag", description="Show your coins and materials")
    @localized("interaction")
    async def bag(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            view = await call(self.service.view, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        embed = discord.Embed(
            title=tx("pet.bag_title", name=view["pet"]["name"]),
            color=COLORS[view["pet"]["species"]],
        )
        embed.add_field(
            name=tx("pet.bag_coins"), value=str(view["coins"]), inline=False
        )
        held = [
            tx(
                "pet.item",
                name=tx(f"pet.material.{material}"),
                amount=view["bag"].get(material, 0),
            )
            for material in rules.MATERIALS
            if view["bag"].get(material)
        ]
        embed.add_field(
            name=tx("pet.bag_materials"),
            value="\n".join(held) or tx("pet.bag_empty"),
            inline=False,
        )
        sold = ", ".join(tx(f"pet.material.{material}") for material in rules.SHOP)
        embed.set_footer(text=tx("pet.bag_shop", items=sold))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @pet.command(name="shop", description="Buy common materials with coins")
    @app_commands.describe(item="What to buy", amount="How many, 1 to 99")
    @app_commands.choices(item=SHOP_CHOICES)
    @localized("interaction")
    async def shop(
        self,
        interaction: discord.Interaction,
        item: str,
        amount: app_commands.Range[int, 1, 99] = 1,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            result = await call(self.service.buy, interaction.user.id, item, amount)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        await interaction.followup.send(
            tx(
                "pet.bought",
                item=items_text({item: amount}),
                price=result["price"],
            ),
            ephemeral=True,
        )

    # ── raising ───────────────────────────────────────────────────
    @pet.command(
        name="breakthrough",
        description="Raise the level cap; past Lv 90, gain 2 levels",
    )
    @localized("interaction")
    async def breakthrough(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.breakthrough, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view, pet = result["view"], result["view"]["pet"]
        line = (
            tx("pet.broke_through_late", name=pet["name"], level=pet["level"])
            if result["late"]
            else tx("pet.broke_through", name=pet["name"], cap=result["cap"])
        )
        await self._milestones(interaction, view)
        await self._show(interaction, view, [line])

    @pet.command(
        name="train", description="Raise one aptitude by a point with materials"
    )
    @app_commands.describe(stat="Which aptitude to raise")
    @app_commands.choices(stat=STAT_CHOICES)
    @localized("interaction")
    async def train(self, interaction: discord.Interaction, stat: str) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.train, interaction.user.id, stat)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view = result["view"]
        await self._show(
            interaction,
            view,
            [
                tx(
                    "pet.trained",
                    name=view["pet"]["name"],
                    stat=tx(f"pet.stat.{stat}"),
                    value=result["value"],
                    cap=result["cap"],
                )
            ],
        )

    @pet.command(
        name="nature", description="Change your companion's nature, once in 7 days"
    )
    @app_commands.describe(
        target="Choose the nature (2 Streamsilver more); leave empty for a random one"
    )
    @app_commands.choices(target=NATURE_CHOICES)
    @localized("interaction")
    async def nature(
        self, interaction: discord.Interaction, target: Optional[str] = None
    ) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.change_nature, interaction.user.id, target)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view, pet = result["view"], result["view"]["pet"]
        await self._show(
            interaction,
            view,
            [
                tx(
                    "pet.nature_changed",
                    name=pet["name"],
                    before=tx(f"pet.nature.{result['before']}"),
                    after=tx(f"pet.nature.{pet['nature']}"),
                )
            ],
        )

    @pet.command(
        name="mutate", description="Mutate at Lv 70 with Streamsilver and Corona Gold"
    )
    @localized("interaction")
    async def mutate(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.mutate, interaction.user.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        view, pet = result["view"], result["view"]["pet"]
        await self._achieve(interaction, "pet_mutation")
        await self._show(
            interaction,
            view,
            [
                tx(
                    "pet.mutated",
                    name=pet["name"],
                    form=form_name(pet["species"], view["stage"], True),
                )
            ],
        )

    # ── with other members ────────────────────────────────────────
    @pet.command(
        name="duel", description="A friendly match against a member's companion"
    )
    @app_commands.describe(member="Whose companion to face")
    @localized("interaction")
    async def duel(
        self, interaction: discord.Interaction, member: discord.User
    ) -> None:
        await interaction.response.defer()
        try:
            result = await call(self.service.duel, interaction.user.id, member.id)
        except PetError as error:
            await self._refuse(interaction, error)
            return
        sides = (result["mine"], result["theirs"])
        winner = sides[0 if result["won"] else 1]
        embed = discord.Embed(
            title=tx(
                "pet.duel_title",
                mine=sides[0]["pet"]["name"],
                theirs=sides[1]["pet"]["name"],
            ),
            description=tx(
                "pet.duel_won",
                winner=winner["pet"]["name"],
                rounds=result["fight"]["rounds"],
                left=result["fight"]["left"][0 if result["won"] else 1],
            ),
            color=COLORS[winner["pet"]["species"]],
        )
        for side, owner in zip(sides, (interaction.user, member)):
            pet = side["pet"]
            embed.add_field(
                name=f"{pet['name']} ({owner.display_name})",
                value=tx(
                    "pet.duel_side",
                    level=pet["level"],
                    form=form_name(pet["species"], side["stage"], pet["mutated"]),
                    power=side["power"],
                ),
                inline=True,
            )
        embed.set_footer(text=tx("pet.duel_note", owner=member.display_name))
        lines = growth_lines(result, result["mine"])
        await interaction.followup.send(
            content="\n".join(lines) or None, embed=embed, allowed_mentions=QUIET
        )

    @pet.command(name="rank", description="The strongest companions in this server")
    @localized("interaction")
    async def rank(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None or self.bot.get_guild(guild.id) is None:
            await interaction.response.send_message(
                tx("pet.rank_server_only"), ephemeral=True
            )
            return
        await interaction.response.defer()
        try:
            rows = await call(
                self.service.ranking, [member.id for member in guild.members]
            )
        except PetError as error:
            await self._refuse(interaction, error)
            return
        lines = []
        for place, row in enumerate(rows, 1):
            member = guild.get_member(row["user_id"])
            lines.append(
                tx(
                    "pet.rank_row",
                    place=place,
                    name=row["name"],
                    level=row["level"],
                    form=form_name(
                        row["species"], rules.stage_of(row["level"]), row["mutated"]
                    ),
                    power=row["power"],
                    owner=member.display_name if member else row["user_id"],
                )
            )
        embed = discord.Embed(
            title=tx("pet.rank_title"),
            description="\n".join(lines) or tx("pet.rank_empty"),
            color=COLORS["nova"],
        )
        await interaction.followup.send(embed=embed, allowed_mentions=QUIET)

    @pet.command(name="guide", description="How companions work")
    @localized("interaction")
    async def guide(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=tx("pet.guide.title"),
            description=tx("pet.guide.start"),
            color=COLORS["fable"],
        )
        for section in ("needs", "trips", "growth", "nature", "fair"):
            embed.add_field(
                name=tx(f"pet.guide.{section}_name"),
                value=tx(f"pet.guide.{section}"),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Pet(bot))

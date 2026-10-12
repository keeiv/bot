"""File tools, usage cards, reset inventory and developer quota administration."""

import asyncio
from datetime import datetime
import logging
import os
import shlex

import discord
from discord import app_commands
from discord.ext import commands

from src.config.constants import DEVELOPER_IDS
from src.services.file_tools import FileTools
from src.services.tool_card import usage_card
from src.services.tool_quota import FORMATS
from src.services.tool_quota import TAIPEI
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.localized_ui import LocalizedView
from src.utils.storage_worker import run_blocking

log = logging.getLogger(__name__)


class PrivateView(LocalizedView):
    def __init__(self, owner):
        super().__init__(timeout=300)
        self.owner = owner

    @localized("interaction")
    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner:
            return True
        await interaction.response.send_message(
            tx("file_tools.this_action_is_restricted_to_the"), ephemeral=True
        )
        return False


class RedeemView(PrivateView):
    i18n = {"use.label": "file_tools.confirm_voucher_use"}

    def __init__(self, owner, engine, coupon):
        super().__init__(owner)
        self.engine = engine
        self.coupon = coupon

    @discord.ui.button(label="Confirm voucher use", style=discord.ButtonStyle.primary)
    @localized("interaction")
    async def use(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        try:
            await run_blocking(self.engine.quota.redeem, self.owner, self.coupon)
            await interaction.edit_original_response(
                content=tx("file_tools.weekly_and_three_hour_usage_reset"),
                view=None,
            )
            self.stop()
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)


class CouponView(PrivateView):
    i18n = {
        "unused.label": "file_tools.unused",
        "history.label": "file_tools.usage_history",
        "previous.label": "file_tools.previous",
        "next.label": "file_tools.next",
    }

    def __init__(self, owner, engine, inventory, used=False):
        super().__init__(owner)
        self.engine = engine
        self.page = inventory["page"]
        self.used = used
        self.unused.style = (
            discord.ButtonStyle.secondary if used else discord.ButtonStyle.primary
        )
        self.history.style = (
            discord.ButtonStyle.primary if used else discord.ButtonStyle.secondary
        )
        self.previous.disabled = self.page == 0
        self.next.disabled = (self.page + 1) * 10 >= inventory["total"]
        if not used and inventory["items"]:
            select = discord.ui.Select(
                placeholder=tx("file_tools.choose_a_reset_voucher"),
                options=[
                    discord.SelectOption(
                        label=tx(
                            "file_tools.reset_voucher_40a182",
                            v0=(datetime.fromtimestamp(item["issuedAt"], TAIPEI)),
                        ),
                        value=item["id"],
                        description=tx("file_tools.serial", v0=(item["id"][-12:])),
                    )
                    for item in inventory["items"]
                ],
            )

            @localized("interaction")
            async def choose(interaction):
                await interaction.response.send_message(
                    tx("file_tools.this_voucher_resets_weekly_and_three"),
                    view=RedeemView(self.owner, engine, select.values[0]),
                    ephemeral=True,
                )

            select.callback = choose
            self.add_item(select)

    @staticmethod
    def embed(inventory, used):
        embed = discord.Embed(
            title=tx("file_tools.reset_vouchers")
            + (tx("file_tools.usage_history") if used else tx("file_tools.unused")),
            color=0x38BDF8,
        )
        for item in inventory["items"]:
            stamp = int(item["usedAt"] if used else item["issuedAt"])
            embed.add_field(
                name=tx("file_tools.reset_voucher", v0=(item["id"][-12:])),
                value=tx(
                    "file_tools.at_t_f",
                    v0=(tx("file_tools.used") if used else tx("file_tools.issued")),
                    v1=(stamp),
                ),
                inline=False,
            )
        if not inventory["items"]:
            embed.description = tx("file_tools.no_records")
        embed.set_footer(
            text=tx(
                "file_tools.page_vouchers_vouchers_do_not_change",
                v0=(inventory["page"] + 1),
                v1=(inventory["total"]),
            )
        )
        return embed

    @localized("interaction")
    async def refresh(self, interaction, used, page):
        await interaction.response.defer()
        data = await run_blocking(self.engine.quota.inventory, self.owner, used, page)
        await interaction.edit_original_response(
            embed=self.embed(data, used),
            view=CouponView(self.owner, self.engine, data, used),
        )
        self.stop()

    @discord.ui.button(label="Unused")
    @localized("interaction")
    async def unused(self, interaction, button):
        await self.refresh(interaction, False, 0)

    @discord.ui.button(label="Usage history")
    @localized("interaction")
    async def history(self, interaction, button):
        await self.refresh(interaction, True, 0)

    @discord.ui.button(label="Previous", row=1)
    @localized("interaction")
    async def previous(self, interaction, button):
        await self.refresh(interaction, self.used, self.page - 1)

    @discord.ui.button(label="Next", row=1)
    @localized("interaction")
    async def next(self, interaction, button):
        await self.refresh(interaction, self.used, self.page + 1)


class ConvertView(PrivateView):
    i18n = {"confirm.label": "file_tools.confirm_processing"}

    def __init__(self, owner, engine, attachments, operation, quality, edge):
        super().__init__(owner)
        self.engine = engine
        self.attachments = attachments
        self.operation = operation
        self.quality = quality
        self.edge = edge
        self.started = False

    @discord.ui.button(label="Confirm processing", style=discord.ButtonStyle.primary)
    @localized("interaction")
    async def confirm(self, interaction, button):
        if self.started:
            await interaction.response.send_message(
                tx("file_tools.job_already_submitted"), ephemeral=True
            )
            return
        self.started = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            async with self.engine.uploads:
                files = []
                for attachment in self.attachments:
                    data = await asyncio.wait_for(attachment.read(), timeout=30)
                    if len(data) != attachment.size:
                        raise ValueError(tx("file_tools.attachment_size_mismatch"))
                    files.append((attachment.filename, data))
                job = await self.engine.submit(
                    self.owner,
                    files,
                    self.operation,
                    self.quality,
                    self.edge,
                    str(interaction.id),
                )
            task = self.engine.tasks.get(job)
            if task:
                await asyncio.shield(task)
            result = self.engine.result(self.owner, job)
            if result["state"] != "done":
                raise ValueError(
                    result.get("error", tx("file_tools.file_processing_failed"))
                )
            path, name = self.engine.download(self.owner, job)
            description = tx(
                "file_tools.completed_points_charged_seconds",
                v0=(result["points"]),
                v1=(result["seconds"]),
            )
            limit = (
                interaction.guild.filesize_limit
                if interaction.guild
                else 10 * 1024 * 1024
            )
            if path.stat().st_size <= limit:
                await interaction.followup.send(
                    description, file=discord.File(path, filename=name), ephemeral=True
                )
            else:
                token = self.engine.tokens.issue(self.owner, "download", jobId=job)
                base = os.getenv(
                    "TOOL_PUBLIC_URL", "https://botapi.shizune.life"
                ).rstrip("/")
                await interaction.followup.send(
                    description
                    + tx(
                        "file_tools.download_result_valid_for_15_minutes",
                        v0=(base),
                        v1=(token),
                    ),
                    ephemeral=True,
                )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception("Discord file tool delivery failed")
            await interaction.followup.send(
                tx("file_tools.the_file_job_response_was_not"), ephemeral=True
            )
        finally:
            self.stop()


class FileToolsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.engine = FileTools()

    async def cog_load(self):
        await self.engine.start()

    async def cog_unload(self):
        await self.engine.close()

    @commands.Cog.listener()
    @localized("interaction")
    async def on_interaction(self, interaction):
        if (
            interaction.type == discord.InteractionType.application_command
            and not interaction.user.bot
        ):
            try:
                await run_blocking(self.engine.quota.register, interaction.user.id)
            except Exception:
                log.exception("Unable to record tool tenure")

    @commands.Cog.listener()
    @localized("ctx")
    async def on_command_completion(self, ctx):
        await run_blocking(self.engine.quota.register, ctx.author.id)

    @app_commands.command(
        name="usage", description="Show your tier, weekly use and last three hours"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @localized("interaction")
    async def usage(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await run_blocking(self.engine.quota.snapshot, interaction.user.id)
        image = await run_blocking(usage_card, data)
        await interaction.followup.send(
            file=discord.File(image, filename="usage.png"), ephemeral=True
        )

    @app_commands.command(
        name="ir", description="Show your reset vouchers and their history"
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @localized("interaction")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await run_blocking(self.engine.quota.inventory, interaction.user.id)
        await interaction.followup.send(
            embed=CouponView.embed(data, False),
            view=CouponView(interaction.user.id, self.engine, data),
            ephemeral=True,
        )

    @localized("interaction")
    async def prepare(self, interaction, attachments, operation, quality, edge):
        await interaction.response.defer(ephemeral=True)
        try:
            quote = await run_blocking(
                self.engine.quota.quote,
                interaction.user.id,
                [a.size for a in attachments],
                operation,
            )
            embed = discord.Embed(
                title=tx("file_tools.file_processing_estimate"),
                description=tx(
                    "file_tools.files_input_mib_maximum_reservation_points",
                    v0=(len(attachments)),
                    v1=(quote["inputBytes"] / 1048576),
                    v2=(quote["maximumPoints"]),
                    v3=(operation),
                ),
                color=0x38BDF8,
            )
            embed.set_footer(text=tx("file_tools.results_are_stored_for_20_minutes"))
            await interaction.followup.send(
                embed=embed,
                view=ConvertView(
                    interaction.user.id,
                    self.engine,
                    attachments,
                    operation,
                    quality,
                    edge,
                ),
                ephemeral=True,
            )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)

    @app_commands.command(
        name="convert",
        description="Convert files: still images, images to PDF, CSV/TSV/JSON",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name=f.upper(), value=f)
            for f in FORMATS
            if f != "compress"
        ]
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @localized("interaction")
    async def convert(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        format: str,
        file2: discord.Attachment | None = None,
        file3: discord.Attachment | None = None,
        file4: discord.Attachment | None = None,
    ):
        await self.prepare(
            interaction, [a for a in (file, file2, file3, file4) if a], format, 85, 4096
        )

    @app_commands.command(
        name="compress",
        description="Compress images; no points charged if the file does not shrink",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @localized("interaction")
    async def compress(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        quality: app_commands.Range[int, 40, 95] = 78,
        max_edge: app_commands.Range[int, 256, 8192] = 4096,
        file2: discord.Attachment | None = None,
        file3: discord.Attachment | None = None,
        file4: discord.Attachment | None = None,
    ):
        await self.prepare(
            interaction,
            [a for a in (file, file2, file3, file4) if a],
            "compress",
            quality,
            max_edge,
        )

    @commands.command(name="convert")
    @localized("ctx")
    async def batch_convert(self, ctx, format: str = "compress"):
        attachments = ctx.message.attachments
        if not attachments:
            await ctx.reply(tx("file_tools.attach_files_and_use_convert_png"))
            return
        try:
            quote = await run_blocking(
                self.engine.quota.quote,
                ctx.author.id,
                [a.size for a in attachments],
                format,
            )
            await ctx.reply(
                tx(
                    "file_tools.file_processing_files_up_to_points",
                    v0=(len(attachments)),
                    v1=(quote["maximumPoints"]),
                ),
                view=ConvertView(
                    ctx.author.id, self.engine, attachments, format, 78, 4096
                ),
            )
        except ValueError as exc:
            await ctx.reply(str(exc))

    @commands.Cog.listener()
    @localized("message")
    async def on_message(self, message):
        if message.author.bot or not message.content.strip().startswith(">>>"):
            return
        try:
            tail = message.content.strip()[3:]
            if not tail or tail[0].isspace():
                return
            parts = shlex.split(tail)
        except ValueError:
            return
        if not parts or parts[0] not in {
            "reset",
            "ureset",
            "sreset",
            "ireset",
            "nova",
            "unova",
        }:
            return
        if message.author.id not in DEVELOPER_IDS:
            await message.reply(
                tx("file_tools.developers_only"),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return
        try:
            command = parts[0]
            if len(parts) != (
                2 if command in {"ureset", "sreset", "nova", "unova"} else 1
            ):
                raise ValueError(
                    tx("file_tools.syntax_reset_ureset_userid_sreset_serverid")
                )
            if command in {"nova", "unova"}:
                data = await run_blocking(
                    self.engine.quota.set_nova,
                    message.author.id,
                    parts[1],
                    command == "nova",
                    str(message.id),
                )
                await message.reply(
                    tx(
                        "file_tools.tier_updated_account_tenure_usage_and",
                        v0=(data["userId"]),
                        v1=(data["tier"]["name"]),
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return
            ids = None
            target = "all"
            if command == "ureset":
                ids, target = [parts[1]], parts[1]
            elif command == "sreset":
                guild = self.bot.get_guild(int(parts[1]))
                if guild is None:
                    raise ValueError(tx("file_tools.the_bot_has_not_joined_this"))
                members = await guild.chunk(cache=True)
                ids = [str(member.id) for member in members if not member.bot]
                target = str(guild.id)
            elif command == "ireset":
                ids = set(await run_blocking(self.engine.quota.registered_ids))
                for guild in self.bot.guilds:
                    members = await guild.chunk(cache=True)
                    ids.update(str(member.id) for member in members if not member.bot)
            count = await run_blocking(
                self.engine.quota.admin,
                message.author.id,
                "issue" if command == "ireset" else "reset",
                str(message.id),
                ids,
                target,
            )
            await message.reply(
                tx(
                    "file_tools.completed_accounts_account_tenure_is_preserved",
                    v0=(
                        tx("file_tools.voucher_distribution")
                        if command == "ireset"
                        else tx("file_tools.usage_reset")
                    ),
                    v1=(count),
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (ValueError, PermissionError) as exc:
            await message.reply(str(exc))
        except Exception:
            log.exception("Tool quota administration failed")
            await message.reply(
                tx("file_tools.operation_incomplete_the_same_message_event")
            )


async def setup(bot):
    await bot.add_cog(FileToolsCog(bot))

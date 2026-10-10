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
from src.utils.storage_worker import run_blocking

log = logging.getLogger(__name__)


class PrivateView(discord.ui.View):
    def __init__(self, owner):
        super().__init__(timeout=300)
        self.owner = owner

    async def interaction_check(self, interaction):
        if interaction.user.id == self.owner:
            return True
        await interaction.response.send_message("此操作僅限原請求帳號", ephemeral=True)
        return False


class RedeemView(PrivateView):
    def __init__(self, owner, engine, coupon):
        super().__init__(owner)
        self.engine = engine
        self.coupon = coupon

    @discord.ui.button(label="確認使用重置券", style=discord.ButtonStyle.primary)
    async def use(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        try:
            await run_blocking(self.engine.quota.redeem, self.owner, self.coupon)
            await interaction.edit_original_response(
                content="本週與近三小時已用額度已重置。處理中的工作仍於完成後計點。",
                view=None,
            )
            self.stop()
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)


class CouponView(PrivateView):
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
                placeholder="選擇重置券",
                options=[
                    discord.SelectOption(
                        label=f"重置券 · {datetime.fromtimestamp(item['issuedAt'], TAIPEI):%Y/%m/%d %H:%M}",
                        value=item["id"],
                        description=f"序號 {item['id'][-12:]}",
                    )
                    for item in inventory["items"]
                ],
            )

            async def choose(interaction):
                await interaction.response.send_message(
                    "使用後將重置本週與近三小時已用額度，使用紀錄永久保留。",
                    view=RedeemView(self.owner, engine, select.values[0]),
                    ephemeral=True,
                )

            select.callback = choose
            self.add_item(select)

    @staticmethod
    def embed(inventory, used):
        embed = discord.Embed(
            title="重置券背包 · " + ("歷史使用" if used else "尚未使用"), color=0x38BDF8
        )
        for item in inventory["items"]:
            stamp = int(item["usedAt"] if used else item["issuedAt"])
            embed.add_field(
                name=f"重置券 · {item['id'][-12:]}",
                value=f"{'使用' if used else '發放'}時間：<t:{stamp}:f>",
                inline=False,
            )
        if not inventory["items"]:
            embed.description = "目前無紀錄"
        embed.set_footer(
            text=f"第 {inventory['page'] + 1} 頁 · 共 {inventory['total']} 張 · 重置券不改變使用年資"
        )
        return embed

    async def refresh(self, interaction, used, page):
        await interaction.response.defer()
        data = await run_blocking(self.engine.quota.inventory, self.owner, used, page)
        await interaction.edit_original_response(
            embed=self.embed(data, used),
            view=CouponView(self.owner, self.engine, data, used),
        )
        self.stop()

    @discord.ui.button(label="尚未使用")
    async def unused(self, interaction, button):
        await self.refresh(interaction, False, 0)

    @discord.ui.button(label="歷史使用")
    async def history(self, interaction, button):
        await self.refresh(interaction, True, 0)

    @discord.ui.button(label="上一頁", row=1)
    async def previous(self, interaction, button):
        await self.refresh(interaction, self.used, self.page - 1)

    @discord.ui.button(label="下一頁", row=1)
    async def next(self, interaction, button):
        await self.refresh(interaction, self.used, self.page + 1)


class ConvertView(PrivateView):
    def __init__(self, owner, engine, attachments, operation, quality, edge):
        super().__init__(owner)
        self.engine = engine
        self.attachments = attachments
        self.operation = operation
        self.quality = quality
        self.edge = edge
        self.started = False

    @discord.ui.button(label="確認處理", style=discord.ButtonStyle.primary)
    async def confirm(self, interaction, button):
        if self.started:
            await interaction.response.send_message("工作已提交", ephemeral=True)
            return
        self.started = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            async with self.engine.uploads:
                files = []
                for attachment in self.attachments:
                    data = await asyncio.wait_for(attachment.read(), timeout=30)
                    if len(data) != attachment.size:
                        raise ValueError("附件大小不符")
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
                raise ValueError(result.get("error", "檔案處理失敗"))
            path, name = self.engine.download(self.owner, job)
            description = f"處理完成 · 扣除 {result['points']} 點 · 處理 {result['seconds']:.2f} 秒"
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
                    + f"\n[下載結果（15 分鐘內有效）]({base}/tools/download?ticket={token})",
                    ephemeral=True,
                )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            log.exception("Discord file tool delivery failed")
            await interaction.followup.send(
                "檔案工作未完成回覆。處理結果可於網站工作紀錄查詢。", ephemeral=True
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
    async def on_command_completion(self, ctx):
        await run_blocking(self.engine.quota.register, ctx.author.id)

    @app_commands.command(
        name="usage", description="查看使用等級、週用量與近三小時用量"
    )
    async def usage(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await run_blocking(self.engine.quota.snapshot, interaction.user.id)
        image = await run_blocking(usage_card, data)
        await interaction.followup.send(
            file=discord.File(image, filename="usage.png"), ephemeral=True
        )

    @app_commands.command(name="ir", description="查看重置券背包與歷史使用紀錄")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        data = await run_blocking(self.engine.quota.inventory, interaction.user.id)
        await interaction.followup.send(
            embed=CouponView.embed(data, False),
            view=CouponView(interaction.user.id, self.engine, data),
            ephemeral=True,
        )

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
                title="檔案處理預估",
                description=f"檔案：{len(attachments)} 件\n輸入：{quote['inputBytes'] / 1048576:.2f} MiB\n最多預留：{quote['maximumPoints']} 點\n輸出：{operation}\n\n依實際檔案大小與處理時間計點。失敗或壓縮未縮小不扣點。",
                color=0x38BDF8,
            )
            embed.set_footer(text="結果暫存 20 分鐘")
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
        name="convert", description="檔案轉換：靜態圖片、圖片轉 PDF、CSV／TSV／JSON"
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name=f.upper(), value=f)
            for f in FORMATS
            if f != "compress"
        ]
    )
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
        name="compress", description="圖片壓縮：未縮小不扣點，支援品質與最大尺寸設定"
    )
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
    async def batch_convert(self, ctx, format: str = "compress"):
        attachments = ctx.message.attachments
        if not attachments:
            await ctx.reply(
                "附加檔案後使用 !convert png／jpg／webp／pdf／csv／tsv／json／compress。"
            )
            return
        try:
            quote = await run_blocking(
                self.engine.quota.quote,
                ctx.author.id,
                [a.size for a in attachments],
                format,
            )
            await ctx.reply(
                f"檔案處理 · {len(attachments)} 件 · 最多預留 {quote['maximumPoints']} 點\n實際扣點依檔案大小與處理時間計算。",
                view=ConvertView(
                    ctx.author.id, self.engine, attachments, format, 78, 4096
                ),
            )
        except ValueError as exc:
            await ctx.reply(str(exc))

    @commands.Cog.listener()
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
                "僅限開發者使用", allowed_mentions=discord.AllowedMentions.none()
            )
            return
        try:
            command = parts[0]
            if len(parts) != (
                2 if command in {"ureset", "sreset", "nova", "unova"} else 1
            ):
                raise ValueError(
                    "格式：>>>reset／>>>ureset [userid]／>>>sreset [serverid]／>>>ireset／>>>nova [userid]／>>>unova [userid]"
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
                    f"等級授權已更新 · {data['userId']} · {data['tier']['name']}。年資、用量與重置券保留。",
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
                    raise ValueError("機器人未加入此伺服器")
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
                f"{'重置券發放' if command == 'ireset' else '用量重置'}完成 · {count} 個帳號。使用年資保留。",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (ValueError, PermissionError) as exc:
            await message.reply(str(exc))
        except Exception:
            log.exception("Tool quota administration failed")
            await message.reply("操作未完成，未確認的結果可使用相同訊息事件重新核對。")


async def setup(bot):
    await bot.add_cog(FileToolsCog(bot))

import asyncio
import io
import logging
from pathlib import Path
import re
from typing import Any, Awaitable, Callable, Optional, Union

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from src.config.constants import DEVELOPER_IDS
from src.services.ai_chat_service import AiChatService
from src.services.ai_chat_service import CATALOG
from src.services.ai_chat_service import ChatBusy
from src.services.ai_chat_service import COST_DRAW
from src.services.ai_chat_service import MAX_CHAT_COST
from src.services.ai_chat_service import MAX_MESSAGE
from src.services.ai_chat_service import model_label
from src.services.ai_chat_service import Reply
from src.services.ai_cli import AiCliError
from src.services.ai_cli import CLAUDE
from src.services.ai_cli import GPT
from src.services.ai_game_profile import GameProfiles
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_blocking
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

# 分身：名稱與頭像（頭像由專案擁有者自行繪製）
ASSETS = Path(__file__).resolve().parents[3] / "assets" / "ai"
NAMES = {CLAUDE: "Sonnet", GPT: "Dawn"}
AVATARS = {CLAUDE: ASSETS / "sonnet.png", GPT: ASSETS / "dawn.png"}
# Sonnet in her amber orange, Dawn in her lavender
COLORS = {
    CLAUDE: discord.Color.from_rgb(224, 122, 62),
    GPT: discord.Color.from_rgb(150, 130, 230),
}
NO_MENTIONS = discord.AllowedMentions.none()
# ">>>claude ..." and ">>>codex ...": the developers' model switch.
DEV_COMMAND = re.compile(r"^>>>(claude|codex)(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)
DEV_PROVIDER = {"claude": CLAUDE, "codex": GPT}

Hookable = Union[discord.TextChannel, discord.VoiceChannel, discord.ForumChannel]
Deliver = Callable[[Reply], Awaitable[None]]


def fit_image(data: bytes, limit: int) -> tuple[bytes, str]:
    """The drawing as a PNG if it fits ``limit`` bytes, else a JPEG shrunk until it does."""
    if len(data) <= limit:
        return data, "drawing.png"
    with Image.open(io.BytesIO(data)) as opened:
        picture = opened.convert("RGB")
    quality = 90
    while True:
        out = io.BytesIO()
        picture.save(out, format="JPEG", quality=quality, optimize=True)
        if out.tell() <= limit or min(picture.size) <= 256:
            return out.getvalue(), "drawing.jpg"
        if quality > 70:
            quality -= 10
        else:
            picture = picture.resize(
                (int(picture.width * 0.8), int(picture.height * 0.8)),
                Image.Resampling.LANCZOS,
            )


class AiChat(commands.Cog):
    """AI 聊天：Sonnet (Claude) 或 Dawn (GPT)，每人選一位"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AiChatService()
        # (channel id, provider) -> the character's webhook in that channel
        self.webhooks: dict[tuple[int, str], discord.Webhook] = {}
        # What an @BOT. answer may know of the member's /genshin links.
        self.profiles = GameProfiles(
            lambda: getattr(self.bot.get_cog("GenshinCog"), "service", None)
        )
        # Let the control panel show which models are installed right away.
        self.service.cli.report_installed()

    ai_group = app_commands.Group(name="ai", description="Chat with an AI character")

    @ai_group.command(
        name="choose",
        description="Pick who answers you: Sonnet (Claude) or Dawn (GPT)",
    )
    @app_commands.describe(character="Who should answer you")
    @app_commands.choices(
        character=[
            app_commands.Choice(name="Sonnet (Claude)", value="claude"),
            app_commands.Choice(name="Dawn (GPT)", value="gpt"),
        ]
    )
    @localized("interaction")
    async def choose(
        self,
        interaction: discord.Interaction,
        character: app_commands.Choice[str],
    ) -> None:
        """選擇回應自己的角色"""
        provider = character.value
        await interaction.response.defer(ephemeral=True)
        try:
            await run_storage(self.service.choose, interaction.user.id, provider)
        except Exception:
            logger.exception("Could not save the AI chat choice")
            await interaction.followup.send(tx("ai_chat.maintenance"), ephemeral=True)
            return
        embed = discord.Embed(
            title=tx("ai_chat.chosen", v0=(tx(f"ai_chat.name_{provider}"))),
            description=tx(f"ai_chat.intro_{provider}"),
            color=COLORS[provider],
        )
        embed.set_footer(text=tx("ai_chat.how_to_talk"))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ai_group.command(name="chat", description="Talk to the AI character you picked")
    @app_commands.describe(message="What you want to say")
    @localized("interaction")
    async def chat(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, MAX_MESSAGE],
    ) -> None:
        """和選擇的角色聊天（回覆包在 embed 裡）"""
        await interaction.response.defer(thinking=True)

        async def deliver(reply: Reply) -> None:
            await interaction.followup.send(**(await self.boxed(reply, interaction)))

        notice = await self.ask(interaction.user.id, message, deliver)
        if notice:  # busy, unavailable, no allowance or no character
            await interaction.followup.send(notice)

    @ai_group.command(name="image", description="Ask Dawn to draw a picture")
    @app_commands.describe(prompt="What to draw")
    @localized("interaction")
    async def image(
        self,
        interaction: discord.Interaction,
        prompt: app_commands.Range[str, 1, MAX_MESSAGE],
    ) -> None:
        """請 Dawn 畫圖（只有 GPT 能畫，與選擇的角色無關）"""
        await interaction.response.defer(thinking=True)

        async def deliver(reply: Reply) -> None:
            await interaction.followup.send(**(await self.boxed(reply, interaction)))

        notice = await self.ask_drawing(interaction.user.id, prompt, deliver)
        if notice:
            await interaction.followup.send(notice)

    async def boxed(self, reply: Reply, interaction: Any = None) -> dict[str, Any]:
        """A reply as an embed: the character's name and avatar, the text, the model line."""
        files = [discord.File(AVATARS[reply.provider], filename="avatar.png")]
        embed = discord.Embed(
            description=f"{reply.text}\n{reply.signature}".strip(),
            color=COLORS[reply.provider],
        )
        embed.set_author(name=NAMES[reply.provider], icon_url="attachment://avatar.png")
        if reply.drawings:
            # Within what this interaction may upload (Discord's own limit, with room
            # for the avatar), so a paid-for drawing is never refused at the door.
            limit = int(getattr(interaction, "filesize_limit", 0) or 10 * 1024 * 1024)
            # Decoding and re-encoding a large image is slow: never on the event loop.
            data, name = await run_blocking(
                fit_image, reply.drawings[0], limit - 512 * 1024
            )
            files.append(discord.File(io.BytesIO(data), filename=name))
            embed.set_image(url=f"attachment://{name}")
        return {"embed": embed, "files": files, "allowed_mentions": NO_MENTIONS}

    @ai_group.command(
        name="forget", description="Clear what the AI remembers of your conversation"
    )
    @localized("interaction")
    async def forget(self, interaction: discord.Interaction) -> None:
        """清除對話記憶"""
        self.service.forget(interaction.user.id)
        await interaction.response.send_message(tx("ai_chat.forgotten"), ephemeral=True)

    # ── @BOT. message: the character answers in person ────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """有人 @BOT. 時，由他選擇的角色以分身（webhook）回覆；>>>claude／>>>codex 切換模型"""
        me = self.bot.user
        if me is None or message.author.bot or message.webhook_id is not None:
            return
        command = DEV_COMMAND.match(message.content.strip())
        if command:
            await self.switch_model(
                message, DEV_PROVIDER[command.group(1).lower()], command.group(2) or ""
            )
            return
        if message.guild is None:
            return
        # Only a real @BOT. in the text counts, not the ping of a reply.
        mention = re.compile(rf"<@!?{me.id}>")
        if not mention.search(message.content):
            return
        text = mention.sub("", message.content).strip()
        if not text:
            return
        blacklist = getattr(self.bot, "blacklist_manager", None)
        if blacklist is not None and await blacklist.check(message.author.id):
            return
        await self.answer_mention(message, text[:MAX_MESSAGE])

    @localized("message")
    async def answer_mention(self, message: discord.Message, text: str) -> None:
        """回覆一則 @BOT. 訊息：純文字，不包 embed"""

        async def deliver(reply: Reply) -> None:
            content = f"{reply.text}\n{reply.signature}"
            if not await self.send_as(message.channel, reply.provider, content):
                # No webhook allowed here: the bot answers in its own name instead,
                # still in the channel if the member deleted their message meanwhile.
                await message.channel.send(
                    content,
                    reference=message.to_reference(fail_if_not_exists=False),
                    mention_author=False,
                    allowed_mentions=NO_MENTIONS,
                )

        async with message.channel.typing():
            notice = await self.ask(message.author.id, text, deliver, games=True)
        if notice:
            await message.reply(notice, mention_author=False)

    def quota(self) -> Optional[Any]:
        """The file tools' allowance, which AI requests share; None when it is not up."""
        if "quota_service" in self.__dict__:
            return self.__dict__["quota_service"]
        tools = self.bot.get_cog("FileToolsCog")
        engine = getattr(tools, "engine", None)
        return getattr(engine, "quota", None)

    async def charged(
        self,
        user_id: int,
        hold: int,
        work: Callable[[], Awaitable[Reply]],
        deliver: Deliver,
    ) -> Optional[str]:
        """Hold ``hold`` points, run ``work``, deliver it, then charge what it cost.

        A failed model costs nothing. Once the model has answered the work is paid
        for, whatever the member does next (deleting their message, letting the
        interaction expire); only a send that fails on the bot's side (an upload too
        large, Discord's own errors) is refunded. Returns a message to show, or None.
        """
        quota = self.quota()
        if quota is None:
            logger.warning("AI chat has no allowance service")
            return tx("ai_chat.maintenance")
        job = await run_blocking(quota.ai_reserve, user_id, hold)
        if job is None:
            return tx("ai_chat.no_allowance", v0=(hold))
        cost = 0
        try:
            reply = await work()
            cost = reply.cost
            try:
                await deliver(reply)
            except discord.HTTPException as error:
                if error.status == 413 or error.status >= 500:
                    cost = 0
                raise
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
                cost = 0  # the bot could not reach Discord at all
                raise
            return None
        finally:
            await run_blocking(quota.ai_settle, user_id, job, cost)

    async def ask(
        self, user_id: int, text: str, deliver: Deliver, games: bool = False
    ) -> Optional[str]:
        """Send the character's reply through ``deliver``; else the message to show.

        With ``games`` the character also sees the member's linked HoYoLAB games.
        """
        try:
            provider = await run_storage(self.service.choice, user_id)
            if provider is None:
                return tx("ai_chat.choose_first")
            model = await run_storage(self.service.model_for, user_id, provider)
            if games and self.service.busy(user_id):
                raise ChatBusy()  # before reading HoYoLAB for a message that waits
            profile = await self.game_profile(user_id) if games else None
            return await self.charged(
                user_id,
                MAX_CHAT_COST,
                lambda: self.service.reply(user_id, text, provider, model, profile),
                deliver,
            )
        except ChatBusy:
            return tx("ai_chat.busy")
        except AiCliError as error:
            # Signed out, out of quota or timed out: the member only sees this.
            logger.warning("AI chat unavailable: %s", error)
            return tx("ai_chat.maintenance")
        except LookupError:
            return tx("ai_chat.choose_first")
        except Exception:
            # Storage down or anything unexpected: the member sees maintenance, the log the cause.
            logger.exception("AI chat failed")
            return tx("ai_chat.maintenance")

    async def game_profile(self, user_id: int) -> Optional[str]:
        """The member's linked games for the prompt; None (and a log line) on any failure."""
        try:
            return await self.profiles.snapshot(user_id)
        except Exception:
            logger.exception("Could not read the HoYoLAB profile for the AI")
            return None

    async def ask_drawing(
        self, user_id: int, prompt: str, deliver: Deliver
    ) -> Optional[str]:
        """Send Dawn's drawing through ``deliver``; else the message to show."""
        try:
            model = await run_storage(self.service.model_for, user_id, GPT)
            return await self.charged(
                user_id,
                COST_DRAW,
                lambda: self.service.draw(user_id, prompt, model),
                deliver,
            )
        except ChatBusy:
            return tx("ai_chat.busy")
        except AiCliError as error:
            logger.warning("AI drawing unavailable: %s", error)
            return tx("ai_chat.maintenance")
        except Exception:
            logger.exception("AI drawing failed")
            return tx("ai_chat.maintenance")

    # ── developers: >>>claude / >>>codex ──────────────────────────
    @localized("message")
    async def switch_model(
        self, message: discord.Message, provider: str, argument: str
    ) -> None:
        """>>>codex [編號] 1（只改自己）／2（改全部人）、>>>codex reset、>>>codex（清單）"""
        if message.author.id not in DEVELOPER_IDS:
            await message.reply(
                tx("developer.denied_this_command_is_restricted_to"), delete_after=5
            )
            return
        name = "claude" if provider == CLAUDE else "codex"
        parts = argument.split()
        try:
            if not parts:
                text = await self.model_list(provider, name, message.author.id)
            elif parts == ["reset"]:
                await run_storage(self.service.reset_models, provider)
                text = tx(
                    "ai_chat.dev_reset",
                    v0=(name),
                    v1=(model_label(self.service.models[provider])),
                )
            elif len(parts) == 2 and parts[0].isdigit() and parts[1] in ("1", "2"):
                scope = "self" if parts[1] == "1" else "all"
                try:
                    model = await run_storage(
                        self.service.set_model,
                        provider,
                        int(parts[0]),
                        scope,
                        message.author.id,
                    )
                except ValueError:
                    text = tx("ai_chat.dev_bad_number", v0=(name))
                else:
                    key = (
                        "ai_chat.dev_set_self"
                        if scope == "self"
                        else "ai_chat.dev_set_all"
                    )
                    text = tx(key, v0=(name), v1=(model_label(model)))
            else:
                text = tx("ai_chat.dev_usage", v0=(name))
        except Exception:
            logger.exception("Could not switch the AI model")
            text = tx("ai_chat.maintenance")
        await message.reply(text, mention_author=False, allowed_mentions=NO_MENTIONS)

    async def model_list(self, provider: str, name: str, user_id: int) -> str:
        overrides = await run_storage(self.service.overrides, provider)
        mine = overrides["users"].get(str(user_id))
        lines = [tx("ai_chat.dev_list_title", v0=(name))]
        for number, (model, label) in enumerate(CATALOG[provider], start=1):
            marks = []
            if model == self.service.models[provider]:
                marks.append(tx("ai_chat.dev_mark_default"))
            if model == overrides["all"]:
                marks.append(tx("ai_chat.dev_mark_everyone"))
            if model == mine:
                marks.append(tx("ai_chat.dev_mark_you"))
            tail = f"  ← {'、'.join(marks)}" if marks else ""
            lines.append(f"`{number}` {label}{tail}")
        lines.append(tx("ai_chat.dev_usage", v0=(name)))
        return "\n".join(lines)

    async def send_as(self, channel, provider: str, content: str) -> bool:
        """Post ``content`` as the character's webhook; False when that is not possible."""
        thread = channel if isinstance(channel, discord.Thread) else None
        target = channel.parent if thread is not None else channel
        if not isinstance(
            target, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)
        ):
            logger.info("No AI webhook: channel type %s", type(target).__name__)
            return False
        if not target.permissions_for(target.guild.me).manage_webhooks:
            logger.warning(
                "No AI webhook: missing Manage Webhooks in #%s (%s) of %s",
                getattr(target, "name", "?"),
                target.id,
                target.guild.id,
            )
            return False
        for _ in range(2):  # a webhook deleted by someone is made again once
            try:
                webhook = await self.webhook(target, provider)
                if webhook is None:
                    return False
                if thread is not None:
                    await webhook.send(
                        content, allowed_mentions=NO_MENTIONS, thread=thread
                    )
                else:
                    await webhook.send(content, allowed_mentions=NO_MENTIONS)
                return True
            except discord.NotFound:
                self.webhooks.pop((target.id, provider), None)
            except discord.HTTPException:
                logger.warning("Could not post as %s", NAMES[provider], exc_info=True)
                return False
        return False

    async def webhook(
        self, channel: Hookable, provider: str
    ) -> Optional[discord.Webhook]:
        """The character's webhook in ``channel``, made on first use and reused."""
        key = (channel.id, provider)
        if key in self.webhooks:
            return self.webhooks[key]
        me = self.bot.user
        found = None
        for hook in await channel.webhooks():
            if (
                hook.name == NAMES[provider]
                and hook.user is not None
                and me is not None
                and hook.user.id == me.id
                and hook.token
            ):
                found = hook
                break
        if found is None:
            found = await channel.create_webhook(
                name=NAMES[provider],
                avatar=AVATARS[provider].read_bytes(),
                reason="AI chat character",
            )
        self.webhooks[key] = found
        return found


async def setup(bot: commands.Bot) -> None:
    """載入 Cog"""
    await bot.add_cog(AiChat(bot))

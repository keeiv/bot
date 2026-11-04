import logging
from pathlib import Path
import re
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from src.services.ai_chat_service import AiChatService
from src.services.ai_chat_service import ChatBusy
from src.services.ai_chat_service import MAX_MESSAGE
from src.services.ai_chat_service import Reply
from src.services.ai_cli import AiCliError
from src.services.ai_cli import CLAUDE
from src.services.ai_cli import GPT
from src.utils.i18n import text as tx
from src.utils.lang_context import localized

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

Hookable = Union[discord.TextChannel, discord.VoiceChannel, discord.ForumChannel]


class AiChat(commands.Cog):
    """AI 聊天：Sonnet (Claude) 或 Dawn (GPT)，每人選一位"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = AiChatService()
        # (channel id, provider) -> the character's webhook in that channel
        self.webhooks: dict[tuple[int, str], discord.Webhook] = {}
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
        try:
            self.service.choose(interaction.user.id, provider)
        except Exception:
            logger.exception("Could not save the AI chat choice")
            await interaction.response.send_message(
                tx("ai_chat.maintenance"), ephemeral=True
            )
            return
        embed = discord.Embed(
            title=tx("ai_chat.chosen", v0=(tx(f"ai_chat.name_{provider}"))),
            description=tx(f"ai_chat.intro_{provider}"),
            color=COLORS[provider],
        )
        embed.set_footer(text=tx("ai_chat.how_to_talk"))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ai_group.command(name="chat", description="Talk to the AI character you picked")
    @app_commands.describe(message="What you want to say")
    @localized("interaction")
    async def chat(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, MAX_MESSAGE],
    ) -> None:
        """和選擇的角色聊天（回覆包在 embed 裡）"""
        if self.service.choice(interaction.user.id) is None:
            await interaction.response.send_message(
                tx("ai_chat.choose_first"), ephemeral=True
            )
            return
        await interaction.response.defer(thinking=True)
        reply = await self.ask(interaction.user.id, message)
        if isinstance(reply, str):  # busy, unavailable or no character
            await interaction.followup.send(reply)
            return
        avatar = discord.File(AVATARS[reply.provider], filename="avatar.png")
        embed = discord.Embed(
            description=f"{reply.text}\n{reply.signature}",
            color=COLORS[reply.provider],
        )
        embed.set_author(name=NAMES[reply.provider], icon_url="attachment://avatar.png")
        await interaction.followup.send(
            embed=embed, file=avatar, allowed_mentions=NO_MENTIONS
        )

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
        """有人 @BOT. 時，由他選擇的角色以分身（webhook）回覆"""
        me = self.bot.user
        if (
            me is None
            or message.author.bot
            or message.webhook_id is not None
            or message.guild is None
        ):
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
        if self.service.choice(message.author.id) is None:
            await message.reply(tx("ai_chat.choose_first"), mention_author=False)
            return
        async with message.channel.typing():
            reply = await self.ask(message.author.id, text)
        if isinstance(reply, str):
            await message.reply(reply, mention_author=False)
            return
        content = f"{reply.text}\n{reply.signature}"
        if not await self.send_as(message.channel, reply.provider, content):
            # No webhook allowed here: the bot answers in its own name instead.
            await message.reply(
                content, mention_author=False, allowed_mentions=NO_MENTIONS
            )

    async def ask(self, user_id: int, text: str) -> Union[Reply, str]:
        """The character's reply, or the message to show instead."""
        try:
            return await self.service.reply(user_id, text)
        except ChatBusy:
            return tx("ai_chat.busy")
        except AiCliError as error:
            # Signed out, out of quota or timed out: the member only sees this.
            logger.warning("AI chat unavailable: %s", error)
            return tx("ai_chat.maintenance")
        except LookupError:
            return tx("ai_chat.choose_first")

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

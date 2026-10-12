import asyncio
import logging
from typing import Any

# deep_translator has no typing metadata.
from deep_translator import GoogleTranslator  # type: ignore[import-untyped]
import discord
from discord import app_commands
from discord.ext import commands

from src.utils.i18n import Lang
from src.utils.i18n import t
from src.utils.lang_context import interaction_lang

logger = logging.getLogger(__name__)

# 常用語言：Google 語言代碼 → 各介面語言的顯示名稱
LANGUAGES: dict[str, dict[Lang, str]] = {
    "zh-TW": {"en": "Chinese (Traditional)", "zh": "繁體中文"},
    "zh-CN": {"en": "Chinese (Simplified)", "zh": "簡體中文"},
    "en": {"en": "English", "zh": "英文"},
    "ja": {"en": "Japanese", "zh": "日文"},
    "ko": {"en": "Korean", "zh": "韓文"},
    "fr": {"en": "French", "zh": "法文"},
    "de": {"en": "German", "zh": "德文"},
    "es": {"en": "Spanish", "zh": "西班牙文"},
    "ru": {"en": "Russian", "zh": "俄文"},
    "pt": {"en": "Portuguese", "zh": "葡萄牙文"},
    "th": {"en": "Thai", "zh": "泰文"},
    "vi": {"en": "Vietnamese", "zh": "越南文"},
    "id": {"en": "Indonesian", "zh": "印尼文"},
    "ar": {"en": "Arabic", "zh": "阿拉伯文"},
}


class LanguageSelect(discord.ui.Select[Any]):
    """語言選擇下拉選單"""

    def __init__(self, original_text: str, lang: Lang) -> None:
        self.original_text = original_text
        self.lang: Lang = lang
        options = [
            discord.SelectOption(label=names[lang], value=code)
            for code, names in LANGUAGES.items()
        ]
        super().__init__(
            placeholder=t(lang, "translate.placeholder"),
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        target_lang = self.values[0]
        lang = self.lang
        target_name = LANGUAGES.get(target_lang, {}).get(lang, target_lang)

        await interaction.response.defer(ephemeral=True)

        try:
            translator = GoogleTranslator(source="auto", target=target_lang)
            translated = await asyncio.wait_for(
                asyncio.to_thread(translator.translate, self.original_text), timeout=15
            )
        except Exception as e:
            logger.error(f"翻譯失敗: {e}")
            await interaction.followup.send(t(lang, "translate.failed"), ephemeral=True)
            return

        embed = discord.Embed(
            title=t(lang, "translate.title", target=target_name),
            color=discord.Color.from_rgb(66, 133, 244),
        )
        # 截斷避免超出 Embed 限制
        original_display = (
            self.original_text[:1000] + "..."
            if len(self.original_text) > 1000
            else self.original_text
        )
        translated_display = (
            translated[:1000] + "..." if len(translated) > 1000 else translated
        )

        embed.add_field(
            name=t(lang, "translate.original"), value=original_display, inline=False
        )
        embed.add_field(
            name=t(lang, "translate.result"), value=translated_display, inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


class LanguageSelectView(discord.ui.View):
    """包含語言選擇的 View"""

    def __init__(self, original_text: str, lang: Lang) -> None:
        super().__init__(timeout=60)
        self.add_item(LanguageSelect(original_text, lang))


class Translate(commands.Cog):
    """右鍵選單翻譯系統"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.translate_ctx_menu = app_commands.ContextMenu(
            name="Translate message",
            callback=self.translate_message,
            # Personal tool: also usable in DMs and servers without the bot.
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
        )
        self.bot.tree.add_command(self.translate_ctx_menu)

    async def cog_unload(self) -> None:
        """卸載 cog 時移除右鍵選單"""
        self.bot.tree.remove_command(
            self.translate_ctx_menu.name, type=self.translate_ctx_menu.type
        )

    async def translate_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """右鍵選單 - 翻譯訊息"""
        lang = await interaction_lang(interaction)
        content = message.content
        if not content or not content.strip():
            await interaction.response.send_message(
                t(lang, "translate.no_text"), ephemeral=True
            )
            return

        if len(content) > 5000:
            await interaction.response.send_message(
                t(lang, "translate.too_long"), ephemeral=True
            )
            return

        view = LanguageSelectView(content, lang)
        await interaction.response.send_message(
            t(lang, "translate.choose"), view=view, ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    """Load Cog"""
    await bot.add_cog(Translate(bot))

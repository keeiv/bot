import logging

import discord
from deep_translator import GoogleTranslator
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# 常用語言對照表
LANGUAGES = {
    "繁體中文": "zh-TW",
    "簡體中文": "zh-CN",
    "英文": "en",
    "日文": "ja",
    "韓文": "ko",
    "法文": "fr",
    "德文": "de",
    "西班牙文": "es",
    "俄文": "ru",
    "葡萄牙文": "pt",
    "泰文": "th",
    "越南文": "vi",
    "印尼文": "id",
    "阿拉伯文": "ar",
}

LANG_CODE_TO_NAME = {v: k for k, v in LANGUAGES.items()}


class LanguageSelect(discord.ui.Select):
    """語言選擇下拉選單"""

    def __init__(self, original_text: str):
        self.original_text = original_text
        options = [
            discord.SelectOption(label=name, value=code)
            for name, code in LANGUAGES.items()
        ]
        super().__init__(
            placeholder="選擇目標語言...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        target_lang = self.values[0]
        target_name = LANG_CODE_TO_NAME.get(target_lang, target_lang)

        await interaction.response.defer(ephemeral=True)

        try:
            translator = GoogleTranslator(source="auto", target=target_lang)
            translated = translator.translate(self.original_text)
        except Exception as e:
            logger.error(f"翻譯失敗: {e}")
            await interaction.followup.send(
                "[失敗] 翻譯時發生錯誤，請稍後再試。", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"[翻譯] 自動偵測 → {target_name}",
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

        embed.add_field(name="[原文]", value=original_display, inline=False)
        embed.add_field(name="[翻譯結果]", value=translated_display, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


class LanguageSelectView(discord.ui.View):
    """包含語言選擇的 View"""

    def __init__(self, original_text: str):
        super().__init__(timeout=60)
        self.add_item(LanguageSelect(original_text))


class Translate(commands.Cog):
    """右鍵選單翻譯系統"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.translate_ctx_menu = app_commands.ContextMenu(
            name="翻譯訊息",
            callback=self.translate_message,
        )
        self.bot.tree.add_command(self.translate_ctx_menu)

    async def cog_unload(self):
        """卸載 cog 時移除右鍵選單"""
        self.bot.tree.remove_command(
            self.translate_ctx_menu.name, type=self.translate_ctx_menu.type
        )

    async def translate_message(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """右鍵選單 - 翻譯訊息"""
        content = message.content
        if not content or not content.strip():
            await interaction.response.send_message(
                "[失敗] 該訊息沒有文字內容可供翻譯。", ephemeral=True
            )
            return

        if len(content) > 5000:
            await interaction.response.send_message(
                "[失敗] 訊息過長，無法翻譯。", ephemeral=True
            )
            return

        view = LanguageSelectView(content)
        await interaction.response.send_message(
            "[翻譯] 請選擇目標語言:", view=view, ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Load Cog"""
    await bot.add_cog(Translate(bot))

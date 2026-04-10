from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from typing import Sequence

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import ActionRow
from discord.ui import Container
from discord.ui import LayoutView
from discord.ui import Section
from discord.ui import Select
from discord.ui import Separator
from discord.ui import TextDisplay
from discord.ui import Thumbnail


@dataclass(frozen=True)
class HelpBlock:
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class HelpCategory:
    key: str
    label: str
    description: str
    accent_color: discord.Color
    summary: str
    blocks: tuple[HelpBlock, ...]


HELP_CATEGORIES: tuple[HelpCategory, ...] = (
    HelpCategory(
        key="overview",
        label="總覽",
        description="機器人介紹與常用入口",
        accent_color=discord.Color.from_rgb(52, 152, 219),
        summary=(
            "功能完整的 Discord 機器人，包含管理、社群工具、遊戲、osu! 整合與 "
            "GitHub 監控。使用下拉選單可以切換不同分區。"
        ),
        blocks=(
            HelpBlock(
                title="快速入口",
                lines=(
                    "`/help` - 開啟這份互動式說明",
                    "`/achievements` - 查看成就進度",
                    "`/user_info` - 查看用戶資訊",
                    "`/server_info` - 查看伺服器資訊",
                ),
            ),
            HelpBlock(
                title="常用功能",
                lines=(
                    "`/clear` - 清除指定數量的訊息",
                    "`/giveaway start` - 建立抽獎活動",
                    "`/osu bind` - 綁定 osu! 帳號",
                    "`/repo_track status` - 查看 keeiv/bot 追蹤狀態",
                ),
            ),
            HelpBlock(
                title="使用方式",
                lines=(
                    "下方選單可切換到管理、防護、社群工具、遊戲整合與開發指南。",
                    "大部分管理類指令需要對應的伺服器權限才可使用。",
                ),
            ),
        ),
    ),
    HelpCategory(
        key="moderation",
        label="管理與審計",
        description="管理指令、審計、外觀與舉報",
        accent_color=discord.Color.from_rgb(46, 204, 113),
        summary="伺服器日常管理、訊息紀錄、機器人外觀調整與舉報流程。",
        blocks=(
            HelpBlock(
                title="管理指令",
                lines=(
                    "`/編刪紀錄設定` - 設置訊息日誌頻道",
                    "`/clear` - 清除指定數量的訊息",
                    "`/kick` - 踢出成員",
                    "`/ban` - 封禁成員",
                    "`/mute` - 禁言成員",
                    "`/warn` - 警告成員",
                ),
            ),
            HelpBlock(
                title="審計日誌",
                lines=(
                    "自動記錄成員加入/離開、語音頻道異動、角色變更、暱稱變更。",
                    "也會追蹤頻道建立、刪除與修改等管理事件。",
                ),
            ),
            HelpBlock(
                title="機器人外觀",
                lines=(
                    "`/bot_appearance name` - 更改機器人暱稱",
                    "`/bot_appearance avatar` - 更改機器人頭像 (需審核)",
                    "`/bot_appearance banner` - 更改機器人橫幅 (需審核)",
                ),
            ),
            HelpBlock(
                title="舉報系統",
                lines=(
                    "右鍵訊息 > 應用程式 > `舉報訊息` - 舉報可疑訊息",
                    "`/report_channel set` - 設定舉報接收頻道",
                    "`/report_channel status` - 查看舉報頻道設定",
                ),
            ),
        ),
    ),
    HelpCategory(
        key="protection",
        label="防護系統",
        description="防炸群與白名單管理",
        accent_color=discord.Color.from_rgb(231, 76, 60),
        summary="針對洪水、重複訊息、提及轟炸、連結與突襲的保護機制。",
        blocks=(
            HelpBlock(
                title="防炸群功能",
                lines=(
                    "`/anti_spam setup` - 啟用/禁用防炸群",
                    "`/anti_spam flood` - 訊息洪水偵測設定",
                    "`/anti_spam duplicate` - 重複內容偵測",
                    "`/anti_spam mention` - 提及轟炸偵測",
                    "`/anti_spam link` - 連結/邀請偵測",
                    "`/anti_spam raid` - 突襲偵測",
                ),
            ),
            HelpBlock(
                title="進階設定",
                lines=(
                    "`/anti_spam escalation` - 自動升級懲罰",
                    "`/anti_spam whitelist` - 白名單管理",
                    "`/anti_spam lockdown_off` - 解除封鎖",
                    "`/anti_spam status` - 查看完整狀態",
                ),
            ),
        ),
    ),
    HelpCategory(
        key="community",
        label="社群工具",
        description="翻譯、抽獎、工單與資訊指令",
        accent_color=discord.Color.from_rgb(241, 196, 15),
        summary="面向一般成員的常用工具與社群互動功能。",
        blocks=(
            HelpBlock(
                title="翻譯",
                lines=(
                    "右鍵訊息 > 應用程式 > `翻譯訊息` - 翻譯任意訊息",
                    "支援 14 種語言，自動偵測來源語言。",
                ),
            ),
            HelpBlock(
                title="抽獎",
                lines=(
                    "`/giveaway start` - 建立抽獎活動",
                    "`/giveaway end` - 提前結束抽獎",
                    "`/giveaway reroll` - 重新抽取得獎者",
                    "`/giveaway list` - 查看進行中抽獎",
                ),
            ),
            HelpBlock(
                title="工單系統",
                lines=(
                    "`>>>ticket setup #頻道 @身份組` - 設定工單系統",
                    "點擊「開啟工單」按鈕建立私人討論串",
                    "支援一般關閉與附原因關閉工單",
                ),
            ),
            HelpBlock(
                title="其他資訊",
                lines=(
                    "`/achievements` - 查看成就",
                    "`/user_info` - 查看用戶資訊",
                    "`/server_info` - 查看伺服器資訊",
                ),
            ),
        ),
    ),
    HelpCategory(
        key="integrations",
        label="遊戲與整合",
        description="遊戲、osu! 與 GitHub",
        accent_color=discord.Color.from_rgb(155, 89, 182),
        summary="娛樂功能與外部服務整合，包含 osu! 和 GitHub 工作流。",
        blocks=(
            HelpBlock(
                title="遊戲",
                lines=(
                    "`/deep_sea_oxygen` - 深海氧氣瓶遊戲",
                    "`/russian_roulette` - 俄羅斯輪盤",
                ),
            ),
            HelpBlock(
                title="osu! 整合",
                lines=(
                    "`/user_info_osu` - 查詢 osu! 玩家資料",
                    "`/osu bind` - 綁定 osu! 帳號",
                    "`/osu best` - 查詢 BP",
                    "`/osu recent` - 查詢最近遊玩",
                ),
            ),
            HelpBlock(
                title="GitHub 監控",
                lines=(
                    "`/repo_watch set` - 設定倉庫監控",
                    "`/repo_track add` - 追蹤 keeiv/bot 更新",
                    "`/repo_track status` - 查看追蹤狀態",
                ),
            ),
        ),
    ),
    HelpCategory(
        key="contribute",
        label="參與開發",
        description="PR 流程與程式碼規範",
        accent_color=discord.Color.from_rgb(26, 188, 156),
        summary="專案接受社群貢獻。小型更新可直接 PR，大型變更先開 Issue 討論。",
        blocks=(
            HelpBlock(
                title="小型 / 中型更新",
                lines=(
                    "不需要事先討論，直接提交 PR 即可。",
                    "例如：新增獨立指令、修復 Bug、更新文件、程式碼重構。",
                ),
            ),
            HelpBlock(
                title="大型更新",
                lines=(
                    "必須先開 Issue 討論後再開發。",
                    "例如：新增依賴、架構變動、資料結構調整、破壞性變更。",
                ),
            ),
            HelpBlock(
                title="PR 提交流程",
                lines=(
                    "1. Fork 倉庫並建立分支",
                    "2. 完成開發並確保通過 CI 檢查",
                    "3. 使用 Conventional Commits，例如 `feat:`、`fix:`、`docs:`",
                    "4. 提交 PR 並清楚描述變更內容",
                ),
            ),
            HelpBlock(
                title="程式碼規範",
                lines=(
                    "遵循 PEP 8 與現有專案風格。",
                    "使用 Black + isort 格式化，並通過 flake8。",
                    "新功能建議補上對應測試。",
                    "倉庫：github.com/keeiv/bot",
                ),
            ),
        ),
    ),
)

HELP_CATEGORY_MAP = {category.key: category for category in HELP_CATEGORIES}


def _help_markdown(title: str, lines: Sequence[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"### {title}\n{body}"


class HelpCategorySelect(Select):
    def __init__(self, parent_view: "HelpLayoutView"):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(
                label=category.label,
                value=category.key,
                description=category.description,
                default=category.key == parent_view.category_key,
            )
            for category in HELP_CATEGORIES
        ]
        super().__init__(
            placeholder="選擇幫助分區",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.author_id:
            await interaction.response.send_message(
                "[拒絕] 只有發起指令的人可以切換幫助分區", ephemeral=True
            )
            return

        next_view = HelpLayoutView(
            bot=self.parent_view.bot,
            author_id=self.parent_view.author_id,
            category_key=self.values[0],
        )
        next_view.message = interaction.message
        self.parent_view.stop()
        await interaction.response.edit_message(view=next_view)


class HelpLayoutView(LayoutView):
    def __init__(self, bot: commands.Bot, author_id: int, category_key: str):
        super().__init__(timeout=900)
        self.bot = bot
        self.author_id = author_id
        self.category_key = (
            category_key if category_key in HELP_CATEGORY_MAP else "overview"
        )
        self.message: Optional[discord.Message] = None
        self.category_select = HelpCategorySelect(self)
        self._build()

    def _build(self) -> None:
        category = HELP_CATEGORY_MAP[self.category_key]
        container = Container(accent_color=category.accent_color)

        header_lines = (
            f"目前分區：**{category.label}**",
            category.summary,
        )

        if self.bot.user is not None:
            container.add_item(
                Section(
                    TextDisplay("## 幫助中心"),
                    TextDisplay("\n".join(header_lines)),
                    accessory=Thumbnail(
                        self.bot.user.display_avatar.url,
                        description="機器人頭像",
                    ),
                )
            )
        else:
            container.add_item(TextDisplay(_help_markdown("幫助中心", header_lines)))

        for block in category.blocks:
            container.add_item(
                Separator(visible=True, spacing=discord.SeparatorSpacing.small)
            )
            container.add_item(TextDisplay(_help_markdown(block.title, block.lines)))

        action_row = ActionRow()
        action_row.add_item(self.category_select)
        container.add_item(
            Separator(visible=True, spacing=discord.SeparatorSpacing.large)
        )
        container.add_item(action_row)

        self.add_item(container)

    async def on_timeout(self) -> None:
        self.category_select.disabled = True
        if self.message is None:
            return

        try:
            await self.message.edit(view=self)
        except (discord.HTTPException, discord.NotFound):
            pass


class Admin(commands.Cog):
    """管理員命令 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_blacklisted_check(self):
        """黑名單檢查裝飾器"""

        async def predicate(ctx):
            blacklist_manager = getattr(self.bot, "blacklist_manager", None)
            if (
                blacklist_manager is not None
                and blacklist_manager.local_check(ctx.author.id)
            ):
                embed = discord.Embed(
                    title="[拒絕] 存取被拒",
                    description="你已被禁止使用機器人指令，請聯繫管理員。",
                    color=discord.Color.from_rgb(231, 76, 60),
                )
                await ctx.send(embed=embed)
                return False
            return True

        return commands.check(predicate)

    @commands.hybrid_command(name="clear", description="清除指定數量的訊息")
    @app_commands.describe(amount="要刪除的訊息數量 (1-100，預設 10)")
    @commands.has_permissions(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clear(self, ctx, amount: int = 10):
        """清除訊息"""
        if not ctx.author.guild_permissions.manage_messages:
            await ctx.send(
                "[失敗] 你需要「管理訊息」權限", ephemeral=True
            )
            return

        if amount < 1 or amount > 100:
            await ctx.send("[失敗] 數量必須在 1-100 之間", ephemeral=True)
            return

        await ctx.defer()
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.followup.send(
            f"[成功] 已清除 {len(deleted)} 則訊息", ephemeral=True
        )

    @commands.hybrid_command(name="kick", description="踢出成員")
    @app_commands.describe(user="要踢出的成員", reason="踢出原因")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """踢出成員"""
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("[失敗] 你需要「踢出成員」權限", ephemeral=True)
            return

        if user == ctx.author:
            await ctx.send("[失敗] 你不能踢出自己", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[失敗] 你的權限不足以踢出此成員",
                ephemeral=True,
            )
            return

        try:
            await user.kick(reason=reason)
            embed = discord.Embed(
                title="[成功] 成員已被踢出",
                description=f"成員: {user.mention}\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法踢出成員: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="ban", description="封禁成員")
    @app_commands.describe(user="要封禁的成員", reason="封禁原因")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """封禁成員"""
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("[失敗] 你需要「封禁成員」權限", ephemeral=True)
            return

        if user == ctx.author:
            await ctx.send("[失敗] 你不能封禁自己", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[失敗] 你的權限不足以封禁此成員",
                ephemeral=True,
            )
            return

        try:
            await user.ban(reason=reason)
            embed = discord.Embed(
                title="[成功] 成員已被封禁",
                description=f"成員: {user.mention}\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法封禁成員: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="mute", description="禁言成員")
    @app_commands.describe(user="要禁言的成員", duration="禁言時長 (分鐘，預設 60)", reason="禁言原因")
    @commands.has_permissions(moderate_members=True)
    async def mute(
        self,
        ctx,
        user: discord.Member,
        duration: int = 60,
        reason: str = "沒有提供原因",
    ):
        """禁言成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[失敗] 你需要有管理成員的權限", ephemeral=True
            )
            return

        if user == ctx.author:
            await ctx.send("[失敗] 你不能禁言自己", ephemeral=True)
            return

        if user.top_role >= ctx.author.top_role:
            await ctx.send(
                "[失敗] 你的權限不足以禁言此成員", ephemeral=True
            )
            return

        try:
            await user.timeout(timedelta(minutes=duration), reason=reason)
            embed = discord.Embed(
                title="[成功] 成員已被禁言",
                description=f"成員: {user.mention}\n持續時間: {duration} 分鐘\n原因: {reason}",
                color=discord.Color.from_rgb(46, 204, 113),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"[失敗] 無法禁言成員: {str(e)}", ephemeral=True)

    @commands.hybrid_command(name="warn", description="警告成員")
    @app_commands.describe(user="要警告的成員", reason="警告原因")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, user: discord.Member, reason: str = "沒有提供原因"):
        """警告成員"""
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send(
                "[失敗] 你需要有管理成員的權限", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="[警告] 警告成員",
            description=f"{user.mention} 已被警告，原因如下:\n{reason}",
            color=discord.Color.from_rgb(241, 196, 15),
        )

        try:
            await user.send(embed=embed)
            await ctx.send(f"[成功] 已警告 {user.mention}", ephemeral=True)
        except Exception as e:
            await ctx.send(
                f"[警告] 成員已被警告，但無法發送私訊: {str(e)}",
                ephemeral=True,
            )

    @commands.hybrid_command(name="help", description="顯示機器人幫助資訊")
    async def help_command(self, ctx):
        """幫助指令"""
        view = HelpLayoutView(self.bot, ctx.author.id, "overview")
        message = await ctx.send(view=view)
        if isinstance(message, discord.Message):
            view.message = message


async def setup(bot: commands.Bot):
    """載入 Cog"""
    await bot.add_cog(Admin(bot))

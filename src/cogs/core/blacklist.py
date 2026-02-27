from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional

import discord
from discord import app_commands
from discord import ui
from discord.ext import commands

from src.utils.blacklist_manager import blacklist_manager

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

# 開發者ID
DEVELOPER_ID = 241619561760292866


class AppealModal(ui.Modal, title="黑名單申訴"):
    """黑名單申訴表單"""

    reason = ui.TextInput(
        label="申訴原因",
        placeholder="請簡潔地說明您認為應該被移除黑名單的原因...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """提交申訴"""
        user_id = interaction.user.id
        reason = self.reason.value

        # 嘗試添加申訴
        success = blacklist_manager.add_appeal(user_id, reason)

        if success:
            embed = discord.Embed(
                title="[成功] 申訴已提交",
                description="您的申訴已提交給開發者，感謝您的耐心等待。",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            # 通知開發者
            try:
                developer = await interaction.client.fetch_user(DEVELOPER_ID)
                dev_embed = discord.Embed(
                    title="[新申訴] 黑名單申訴待審核",
                    description=f"**申訴用戶:** {interaction.user.mention} ({interaction.user.id})\n\n**申訴原因:**\n{reason}",
                    color=discord.Color.blue(),
                )
                dev_embed.set_footer(
                    text=f"提交時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
                )

                # 傳送給開發者
                view = AppealReviewView(user_id)
                await developer.send(embed=dev_embed, view=view)
            except Exception as e:
                print(f"[錯誤] 無法通知開發者: {e}")
        else:
            # 檢查是否已有待處理的申訴或用戶不在黑名單中
            appeal = blacklist_manager.get_appeal(user_id)
            if appeal and appeal["status"] == "待處理":
                embed = discord.Embed(
                    title="[失敗] 申訴已存在",
                    description="您已提交申訴，請等待開發者審核。",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title="[失敗] 無法提交申訴",
                    description="您不在黑名單中。",
                    color=discord.Color.red(),
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AppealButton(ui.View):
    """申訴按鈕"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="申訴", style=discord.ButtonStyle.primary)
    async def appeal_button(self, interaction: discord.Interaction, button: ui.Button):
        """顯示申訴表單"""
        await interaction.response.send_modal(AppealModal())


class AppealReviewView(ui.View):
    """申訴審核視圖"""

    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @ui.button(label="接受申訴", style=discord.ButtonStyle.success)
    async def accept_appeal(self, interaction: discord.Interaction, button: ui.Button):
        """接受申訴"""
        # 檢查是否為開發者
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 您沒有權限審核申訴。", ephemeral=True
            )
            return

        success = blacklist_manager.update_appeal(
            self.user_id, "接受", interaction.user.id
        )

        if success:
            embed = discord.Embed(
                title="[申訴已接受]",
                description=f"用戶 {self.user_id} 的申訴已被接受，他們已從黑名單中移除。",
                color=discord.Color.green(),
            )
            await interaction.response.edit_message(embed=embed, view=None)

            # 通知被申訴的用戶
            try:
                appeal_user = await interaction.client.fetch_user(self.user_id)
                user_embed = discord.Embed(
                    title="[好消息] 申訴已被接受",
                    description="您的黑名單申訴已被接受！您現在可以使用機器人指令。",
                    color=discord.Color.green(),
                )
                user_embed.set_footer(
                    text=f"審核時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
                )
                await appeal_user.send(embed=user_embed)
            except Exception as e:
                print(f"[警告] 無法通知用戶: {e}")
        else:
            embed = discord.Embed(
                title="[失敗] 無法更新申訴",
                description="申訴記錄可能已被刪除或狀態已更改。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="拒絕申訴", style=discord.ButtonStyle.danger)
    async def reject_appeal(self, interaction: discord.Interaction, button: ui.Button):
        """拒絕申訴"""
        # 檢查是否為開發者
        if interaction.user.id != DEVELOPER_ID:
            await interaction.response.send_message(
                "[拒絕] 您沒有權限審核申訴。", ephemeral=True
            )
            return

        success = blacklist_manager.update_appeal(
            self.user_id, "拒絕", interaction.user.id
        )

        if success:
            embed = discord.Embed(
                title="[申訴已拒絕]",
                description=f"用戶 {self.user_id} 的申訴已被拒絕。",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=None)

            # 通知被申訴的用戶
            try:
                appeal_user = await interaction.client.fetch_user(self.user_id)
                user_embed = discord.Embed(
                    title="[申訴結果] 申訴已被拒絕",
                    description="很遺憾，您的黑名單申訴已被拒絕。如有問題請聯繫開發者。",
                    color=discord.Color.red(),
                )
                user_embed.set_footer(
                    text=f"審核時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
                )
                await appeal_user.send(embed=user_embed)
            except Exception as e:
                print(f"[警告] 無法通知用戶: {e}")
        else:
            embed = discord.Embed(
                title="[失敗] 無法更新申訴",
                description="申訴記錄可能已被刪除或狀態已更改。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class Blacklist(commands.Cog):
    """黑名單管理 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_developer(self) -> bool:
        """開發者檢查"""

        async def predicate(interaction: discord.Interaction) -> bool:
            if interaction.user.id != DEVELOPER_ID:
                await interaction.response.send_message(
                    "[拒絕] 您沒有權限執行此命令。", ephemeral=True
                )
                return False
            return True

        return app_commands.check(predicate)

    blacklist_group = app_commands.Group(name="黑名單", description="黑名單管理命令")

    @blacklist_group.command(name="新增", description="將用戶添加到黑名單")
    @app_commands.describe(user="要添加的用戶", reason="封禁原因")
    async def blacklist_add(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = "未提供原因",
    ):
        """添加用戶到黑名單"""
        # 檢查開發者權限
        if interaction.user.id != DEVELOPER_ID:
            embed = discord.Embed(
                title="[拒絕] 權限不足",
                description="只有開發者可以使用此命令。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 防止自我封禁
        if user.id == interaction.user.id:
            embed = discord.Embed(
                title="[失敗] 無法封禁自己",
                description="您無法將自己添加到黑名單。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 檢查是否已在黑名單中
        if blacklist_manager.is_blacklisted(user.id):
            embed = discord.Embed(
                title="[失敗] 用戶已在黑名單中",
                description=f"用戶 {user.mention} 已在黑名單中。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 添加到黑名單
        blacklist_manager.add_to_blacklist(user.id)

        embed = discord.Embed(
            title="[成功] 用戶已添加到黑名單",
            description=f"**用戶:** {user.mention}\n**用戶 ID:** {user.id}\n**原因:** {reason}",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"執行時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
        )
        await interaction.response.send_message(embed=embed)

        # 私訊被黑名單的用戶
        try:
            user_embed = discord.Embed(
                title="[警告] 您已被添加到黑名單",
                description=f"您因以下原因被添加到黑名單：\n\n>>> {reason}",
                color=discord.Color.orange(),
            )
            user_embed.add_field(
                name="申訴",
                value="如果您認為這是誤會，您可以點擊下方按鈕提交申訴。",
                inline=False,
            )

            view = AppealButton()
            await user.send(embed=user_embed, view=view)
        except Exception as e:
            print(f"[警告] 無法私訊用戶 {user.id}: {e}")

    @blacklist_group.command(name="移除", description="從黑名單中移除用戶")
    @app_commands.describe(user="要移除的用戶")
    async def blacklist_remove(
        self, interaction: discord.Interaction, user: discord.User
    ):
        """從黑名單移除用戶"""
        # 檢查開發者權限
        if interaction.user.id != DEVELOPER_ID:
            embed = discord.Embed(
                title="[拒絕] 權限不足",
                description="只有開發者可以使用此命令。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 檢查是否在黑名單中
        if not blacklist_manager.is_blacklisted(user.id):
            embed = discord.Embed(
                title="[失敗] 用戶不在黑名單中",
                description=f"用戶 {user.mention} 不在黑名單中。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 從黑名單移除
        blacklist_manager.remove_from_blacklist(user.id)

        embed = discord.Embed(
            title="[成功] 用戶已從黑名單移除",
            description=f"**用戶:** {user.mention}\n**用戶 ID:** {user.id}",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"執行時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
        )
        await interaction.response.send_message(embed=embed)

        # 通知用戶
        try:
            user_embed = discord.Embed(
                title="[好消息] 您已從黑名單移除",
                description="您已被從黑名單中移除，現在可以使用機器人指令。",
                color=discord.Color.green(),
            )
            user_embed.set_footer(
                text=f"移除時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
            )
            await user.send(embed=user_embed)
        except Exception as e:
            print(f"[警告] 無法私訊用戶 {user.id}: {e}")

    @blacklist_group.command(name="列表", description="查看黑名單中的所有用戶")
    async def blacklist_list(self, interaction: discord.Interaction):
        """查看黑名單列表"""
        # 檢查開發者權限
        if interaction.user.id != DEVELOPER_ID:
            embed = discord.Embed(
                title="[拒絕] 權限不足",
                description="只有開發者可以使用此命令。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        blacklist = blacklist_manager.load_blacklist()

        if not blacklist:
            embed = discord.Embed(
                title="黑名單",
                description="黑名單中沒有用戶。",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 創建黑名單列表
        user_list = "\n".join([f"• {user_id}" for user_id in sorted(blacklist)])

        embed = discord.Embed(
            title="黑名單",
            description=f"**總計:** {len(blacklist)} 名用戶\n\n```\n{user_list}```",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"查詢時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="申訴", description="申訴黑名單決定")
    async def appeal(self, interaction: discord.Interaction):
        """提交黑名單申訴"""
        # 檢查用戶是否被黑名單
        if not blacklist_manager.is_blacklisted(interaction.user.id):
            embed = discord.Embed(
                title="[失敗] 無法申訴",
                description="您不在黑名單中。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 檢查是否已有待處理的申訴
        appeal = blacklist_manager.get_appeal(interaction.user.id)
        if appeal and appeal["status"] == "待處理":
            embed = discord.Embed(
                title="[失敗] 申訴已存在",
                description="您已提交申訴，請等待開發者審核。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 顯示申訴表單
        await interaction.response.send_modal(AppealModal())

    @app_commands.command(name="申訴狀態", description="查看您的申訴狀態")
    async def appeal_status(self, interaction: discord.Interaction):
        """查看申訴狀態"""
        appeal = blacklist_manager.get_appeal(interaction.user.id)

        if not appeal:
            embed = discord.Embed(
                title="[信息] 沒有申訴記錄",
                description="您沒有提交過申訴。",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 根據狀態設置顏色
        color_map = {
            "待處理": discord.Color.yellow(),
            "接受": discord.Color.green(),
            "拒絕": discord.Color.red(),
        }

        embed = discord.Embed(
            title="申訴狀態",
            description=f"**狀態:** {appeal['status']}\n**原因:** {appeal['reason']}",
            color=color_map.get(appeal["status"], discord.Color.blue()),
        )
        embed.add_field(name="提交時間", value=appeal["created_at"], inline=False)

        if appeal["reviewed_at"]:
            embed.add_field(name="審核時間", value=appeal["reviewed_at"], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @blacklist_group.command(name="待審申訴", description="查看待審核的申訴")
    async def pending_appeals(self, interaction: discord.Interaction):
        """查看待審的申訴列表"""
        # 檢查開發者權限
        if interaction.user.id != DEVELOPER_ID:
            embed = discord.Embed(
                title="[拒絕] 權限不足",
                description="只有開發者可以使用此命令。",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        pending = blacklist_manager.get_pending_appeals()

        if not pending:
            embed = discord.Embed(
                title="待審申訴",
                description="沒有待審核的申訴。",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 創建申訴列表
        appeal_list = ""
        for appeal in pending:
            appeal_list += f"• 用戶 ID: {appeal['user_id']}\n"
            appeal_list += f"  原因: {appeal['reason'][:50]}...\n"
            appeal_list += f"  提交時間: {appeal['created_at']}\n\n"

        embed = discord.Embed(
            title="待審申訴",
            description=f"**總計:** {len(pending)} 份待審申訴\n\n{appeal_list}",
            color=discord.Color.yellow(),
        )
        embed.set_footer(
            text=f"查詢時間: {datetime.now(TZ_OFFSET).strftime('%Y/%m/%d %H:%M:%S')}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """設置 Cog"""
    await bot.add_cog(Blacklist(bot))

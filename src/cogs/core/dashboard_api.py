"""Optional authenticated API for the botweb dashboard (disabled by default)."""

import asyncio
import hmac
import logging
import math
import os
import time

from aiohttp import web
import discord
from discord.ext import commands

from src.services.dashboard_service import atomic_json
from src.services.dashboard_service import DashboardService
from src.services.dashboard_service import MAPPINGS
from src.services.dashboard_service import revision

log = logging.getLogger(__name__)


class DashboardAPI(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = DashboardService(bot)
        self.runner = None
        self.lock = asyncio.Lock()
        self.started_at = time.monotonic()

    async def cog_load(self) -> None:
        if os.getenv("BOT_API_ENABLED", "false").lower() != "true":
            return
        secret = os.getenv("BOT_API_SECRET", "")
        if len(secret) < 32:
            raise RuntimeError("BOT_API_SECRET 至少需要 32 字元")
        app = self.create_app(secret)
        self.runner = web.AppRunner(app, access_log=None)
        try:
            await self.runner.setup()
            await web.TCPSite(
                self.runner,
                os.getenv("BOT_API_HOST", "127.0.0.1"),
                int(os.getenv("BOT_API_PORT", "8080")),
            ).start()
        except Exception:
            await self.runner.cleanup()
            self.runner = None
            raise

    async def cog_unload(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    def create_app(self, secret: str) -> web.Application:
        @web.middleware
        async def guard(request, handler):
            if not hmac.compare_digest(
                request.headers.get("X-Bot-Secret", "").encode(), secret.encode()
            ):
                return web.json_response({"error": "Unauthorized"}, status=401)
            if not self.bot.is_ready():
                return web.json_response({"error": "機器人尚未就緒"}, status=503)
            try:
                response = await handler(request)
            except ValueError as exc:
                response = web.json_response({"error": str(exc)}, status=400)
            except discord.Forbidden:
                response = web.json_response({"error": "機器人權限不足"}, status=403)
            except (OSError, RuntimeError, discord.HTTPException):
                log.exception("Dashboard operation failed")
                response = web.json_response(
                    {"error": "機器人操作失敗，請查看本機日誌"}, status=503
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        app = web.Application(middlewares=[guard], client_max_size=16384)
        app.router.add_get("/guilds", self.guilds)
        app.router.add_get("/status", self.status)
        app.router.add_get("/guilds/{guild_id}/settings", self.get_settings)
        app.router.add_patch("/guilds/{guild_id}/settings", self.save_settings)
        app.router.add_post("/guilds/{guild_id}/panel", self.deploy_panel)
        return app

    async def guilds(self, request):
        return web.json_response({"guildIds": [str(g.id) for g in self.bot.guilds]})

    async def status(self, request):
        latency = self.bot.latency
        latency_ms = (
            round(latency * 1000)
            if isinstance(latency, (int, float)) and math.isfinite(latency)
            else None
        )
        return web.json_response(
            {
                "online": True,
                "latencyMs": latency_ms,
                "uptimeSeconds": max(0, round(time.monotonic() - self.started_at)),
                "guildCount": len(self.bot.guilds),
                "memberCount": sum(g.member_count or 0 for g in self.bot.guilds),
                "shardCount": self.bot.shard_count or 1,
                "region": os.getenv("BOT_REGION", "Taipei, Taiwan"),
                "version": os.getenv("BOT_VERSION", "development"),
            }
        )

    async def authorized_guild(self, request):
        guild_id = request.match_info["guild_id"]
        actor_id = request.headers.get("X-Discord-User", "")
        if not guild_id.isdecimal() or not actor_id.isdecimal():
            raise web.HTTPForbidden()
        guild = self.bot.get_guild(int(guild_id))
        if guild is None:
            raise web.HTTPNotFound()
        try:
            member = await guild.fetch_member(int(actor_id))
        except discord.NotFound:
            raise web.HTTPForbidden() from None
        if not member.guild_permissions.manage_guild:
            raise web.HTTPForbidden()
        return guild

    async def get_settings(self, request):
        guild = await self.authorized_guild(request)
        settings = self.service.read(guild.id)
        return web.json_response({"settings": settings, "revision": revision(settings)})

    async def save_settings(self, request):
        guild = await self.authorized_guild(request)
        body = await request.json()
        if not isinstance(body, dict) or set(body) != {"section", "values", "revision"}:
            raise ValueError("請提供 section、values、revision")
        async with self.lock:
            current = self.service.read(guild.id)
            if body["revision"] != revision(current):
                return web.json_response(
                    {"error": "設定已被其他人修改，請重新載入後再儲存"}, status=409
                )
            self.service.write(guild, body["section"], body["values"])
            settings = self.service.read(guild.id)
        log.info(
            "Dashboard settings saved guild=%s actor=%s section=%s",
            guild.id,
            request.headers.get("X-Discord-User"),
            body["section"],
        )
        return web.json_response({"settings": settings, "revision": revision(settings)})

    async def deploy_panel(self, request):
        from src.cogs.features.ticket import TicketOpenView

        guild = await self.authorized_guild(request)
        async with self.lock:
            cog, data = self.service.store("ticket")
            cfg = data.get("guilds", {}).get(str(guild.id), {})
            if not cfg or not cfg.get("enabled", True):
                raise ValueError("請先儲存並啟用工單設定")
            self.service.validate(
                guild, "ticket", self.service.read(guild.id)["ticket"]
            )
            channel = guild.get_channel(cfg["channel_id"])
            if cfg.get("panel_message_id"):
                try:
                    message = await channel.fetch_message(cfg["panel_message_id"])
                    await message.edit(view=TicketOpenView())
                    return web.json_response({"ok": True})
                except discord.NotFound:
                    pass
            message = await channel.send(
                embed=discord.Embed(
                    title="支援工單", description="點擊下方按鈕建立私人工單。"
                ),
                view=TicketOpenView(),
            )
            import copy

            updated = copy.deepcopy(data)
            updated["guilds"][str(guild.id)]["panel_message_id"] = message.id
            try:
                atomic_json(MAPPINGS["ticket"][1], updated)
            except OSError:
                await message.delete()
                raise
            data.clear()
            data.update(updated)
        return web.json_response({"ok": True})


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DashboardAPI(bot))

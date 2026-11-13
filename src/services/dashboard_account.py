"""Account self-service adapter. Only explicitly public profile fields leave the bot."""

import asyncio
import logging

from src.services.endfield_service import EndfieldError
from src.services.endfield_service import UID_RE
from src.utils.storage_worker import run_storage

logger = logging.getLogger(__name__)

PROFILE_SECONDS = 6  # the page waits no longer than this for the game card


class DashboardAccount:
    def __init__(self, bot):
        self.bot = bot

    async def read_full(self, user_id):
        """What read() gives, plus the linked Endfield player's public card."""
        account = self.read(user_id)
        endfield = account["endfield"]
        endfield["profile"] = None
        cog = self.bot.get_cog("EndfieldCog")
        if cog is None or not endfield["uid"]:
            return account
        try:
            zh, en = await asyncio.wait_for(
                asyncio.gather(
                    cog.service.profile(endfield["uid"], "zh"),
                    cog.service.profile(endfield["uid"], "en"),
                ),
                PROFILE_SECONDS,
            )
        except (EndfieldError, asyncio.TimeoutError) as error:
            logger.info("Endfield card unreadable for the account centre: %s", error)
            return account
        endfield["profile"] = {
            "name": zh.name,
            "region": {"zh": zh.region, "en": en.region},
            "level": zh.adventure_level,
            "worldLevel": zh.world_level,
            "operators": zh.operators_owned,
            "weapons": zh.weapons_owned,
            "showcase": [
                {"zh": z.name, "en": e.name, "level": z.level}
                for z, e in zip(zh.showcase, en.showcase)
            ],
        }
        return account

    def read(self, user_id):
        hoyo = self.bot.get_cog("GenshinCog")
        bound = hoyo.service.get_bound_user(user_id) if hoyo else None
        endfield = self.bot.get_cog("EndfieldCog")
        return {
            # Whether a token is linked, never the token.
            "endfield": {
                "available": bool(endfield),
                "uid": endfield.service.bound_uid(user_id) if endfield else None,
                "account": bool(endfield and endfield.service.has_account(user_id)),
            },
            "hoyolab": {
                "available": bool(hoyo),
                "bound": bool(bound),
                "region": bound.get("region") if bound else None,
                "autoSignIn": bound.get("auto_sign_in", True) if bound else False,
                "accounts": [
                    {
                        key: account.get(key)
                        for key in (
                            "game_biz",
                            "uid",
                            "nickname",
                            "level",
                            "server",
                            "server_name",
                        )
                    }
                    for account in (bound or {}).get("game_accounts", [])
                ],
            },
        }

    async def update(self, user_id, body):
        if not isinstance(body, dict):
            raise ValueError("Invalid account request")
        game, action = body.get("game"), body.get("action")
        if game not in ("hoyolab", "endfield") or action not in (
            "bind",
            "unbind",
        ):
            raise ValueError("Invalid account request")
        if game == "endfield":
            await self._update_endfield(user_id, action, body)
            return await self.read_full(user_id)
        expected = {"game", "action"}
        if action == "bind":
            expected |= {"cookie", "region"}
        if set(body) != expected:
            raise ValueError("Invalid account request")
        cog = self.bot.get_cog("GenshinCog")
        if cog is None:
            raise ValueError("Game integration unavailable")
        service = cog.service
        if action == "unbind":
            await run_storage(service.unbind_account, user_id)
            self.bot.dispatch("mhy_unbound", int(user_id))
        else:
            cookie, region = body["cookie"], body["region"]
            if (
                not isinstance(cookie, str)
                or not 1 <= len(cookie.strip()) <= 8000
                or region not in ("cn", "global")
            ):
                raise ValueError("Invalid HoYoLAB credentials")
            try:
                await asyncio.wait_for(
                    service.bind_account(user_id, cookie, region), timeout=10
                )
            except Exception:
                # Upstream exceptions can contain credentials. Never return or log them.
                raise ValueError("Unable to verify HoYoLAB account") from None
            # The AI characters read the new link at once (see ai_chat).
            self.bot.dispatch("mhy_bound", int(user_id))
        return await self.read_full(user_id)

    async def _update_endfield(self, user_id, action, body):
        """Link a UID or a SKPORT token, or remove the link. Errors name no credential."""
        extra = set(body) - {"game", "action"}
        if extra != (set() if action == "unbind" else extra & {"uid", "token"}) or (
            action == "bind" and len(extra) != 1
        ):
            raise ValueError("Invalid account request")
        cog = self.bot.get_cog("EndfieldCog")
        if cog is None:
            raise ValueError("Game integration unavailable")
        service = cog.service
        if action == "unbind":
            await run_storage(service.unbind, user_id)
            self.bot.dispatch("endfield_unbound", int(user_id))
            return
        if "token" in body:
            token = body["token"]
            if not isinstance(token, str) or not 1 <= len(token.strip()) <= 4000:
                raise ValueError("Invalid SKPORT token")
            try:
                await asyncio.wait_for(service.link_account(int(user_id), token), 15)
            except EndfieldError as error:
                if error.code == "no_key":
                    raise ValueError("Game integration unavailable") from None
                raise ValueError("Unable to verify SKPORT account") from None
            except Exception:
                # Upstream exceptions can contain credentials. Never return or log them.
                raise ValueError("Unable to verify SKPORT account") from None
        else:
            uid = body["uid"]
            if not isinstance(uid, str) or not UID_RE.match(uid.strip()):
                raise ValueError("Invalid Endfield UID")
            try:
                await asyncio.wait_for(service.profile(uid.strip()), 12)
            except EndfieldError as error:
                if error.code in ("bad_uid", "not_found"):
                    raise ValueError("Unable to find Endfield player") from None
                # Enka is busy or the game is down: the UID may well be right
            except asyncio.TimeoutError:
                pass
            await run_storage(service.bind, int(user_id), uid.strip())
        self.bot.dispatch("endfield_bound", int(user_id))

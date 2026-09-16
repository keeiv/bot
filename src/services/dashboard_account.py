"""Account self-service adapter. Only explicitly public profile fields leave the bot."""

import asyncio


class DashboardAccount:
    def __init__(self, bot):
        self.bot = bot

    def read(self, user_id):
        osu = self.bot.get_cog("OsuInfo")
        hoyo = self.bot.get_cog("GenshinCog")
        bound = hoyo.service.get_bound_user(user_id) if hoyo else None
        return {
            "osu": {
                "available": bool(osu and osu.service.api is not None),
                "username": osu.service.get_bound_username(user_id) if osu else None,
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
        if game not in ("osu", "hoyolab") or action not in ("bind", "unbind"):
            raise ValueError("Invalid account request")
        expected = {"game", "action"}
        if action == "bind":
            expected |= {"username"} if game == "osu" else {"cookie", "region"}
        if set(body) != expected:
            raise ValueError("Invalid account request")
        cog = self.bot.get_cog("OsuInfo" if game == "osu" else "GenshinCog")
        if cog is None:
            raise ValueError("Game integration unavailable")
        service = cog.service
        if action == "unbind":
            if game == "osu":
                service.unbind(user_id)
            else:
                service.unbind_account(user_id)
        elif game == "osu":
            username = body["username"]
            if not isinstance(username, str) or not 1 <= len(username.strip()) <= 32:
                raise ValueError("Invalid osu username")
            if service.api is None:
                raise ValueError("Game integration unavailable")
            try:
                user = await asyncio.wait_for(
                    asyncio.to_thread(service.api.user, username.strip()), timeout=8
                )
            except Exception:
                raise ValueError("Unable to verify osu account") from None
            if not user or not isinstance(user.username, str):
                raise ValueError("Unable to verify osu account")
            service.bind(user_id, user.username)
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
        return self.read(user_id)

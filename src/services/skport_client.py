"""The SKPORT calls behind Arknights: Endfield accounts (global servers).

SKPORT has no public API. These are the calls its own site and app make, as
worked out by endfield-py (MIT) and skport-api-docs: a member's account token
becomes a short-lived credential, and signed requests with it read their game
card. The account token signs in to the member's SKPORT account, so it never
reaches a log, an error message or a model.
"""

import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from typing import Any, Callable, Optional
from urllib.parse import urlencode

import aiohttp

GRANT_URL = "https://as.gryphline.com/user/oauth2/v2/grant"
HOST = "https://zonai.skport.com"
CRED_PATH = "/web/v1/user/auth/generate_cred_by_code"
BINDING_PATH = "/api/v1/game/player/binding"
ME_PATH = "/web/v1/wiki/me"
DETAIL_PATH = "/api/v1/game/endfield/card/detail"
APP_CODE = "6eb76d4e13aa36e6"
PLATFORM = "3"
VNAME = "1.0.0"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/149.0.0.0 Mobile Safari/537.36; SKPort/1.3.1"
)
MAX_TOKEN = 4096


class SkportError(Exception):
    """``code``: bad_token, no_role or unavailable. Never carries the token."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Login:
    cred: str
    sign_token: str
    role_id: str
    server_id: str
    user_id: str
    nickname: str


def parse_token(text: str) -> str:
    """The token from what a member pasted: the page's JSON, or the bare value."""
    text = (text or "").strip()
    if not text or len(text) > MAX_TOKEN:
        raise SkportError("bad_token")
    if text.startswith("{"):
        try:
            text = str(json.loads(text)["data"]["content"]).strip()
        except (ValueError, KeyError, TypeError):
            raise SkportError("bad_token") from None
    if not text or any(c.isspace() for c in text):
        raise SkportError("bad_token")
    return text


def sign(sign_token: str, path: str, query: str, timestamp: str) -> str:
    """HMAC-SHA256 of the request with the sign token, then MD5 of its hex."""
    header = json.dumps(
        {"platform": PLATFORM, "timestamp": timestamp, "dId": "", "vName": VNAME},
        separators=(",", ":"),
    )
    digest = hmac.new(
        sign_token.encode(),
        (path + query + timestamp + header).encode(),
        hashlib.sha256,
    ).hexdigest()
    # usedforsecurity=False: SKPORT's scheme; the secret is in the HMAC above
    return hashlib.md5(digest.encode(), usedforsecurity=False).hexdigest()


class SkportClient:
    def __init__(
        self, http: Callable[[], Any], clock: Callable[[], float] = time.time
    ) -> None:
        self.http = http
        self.clock = clock

    async def _json(self, call: Any) -> dict[str, Any]:
        try:
            async with call as response:
                status = response.status
                data = json.loads(await response.text())
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            raise SkportError("unavailable") from None
        # An outage or a rate limit says nothing about the token.
        if not isinstance(data, dict) or status == 429 or status >= 500:
            raise SkportError("unavailable")
        code = data.get("code")
        if isinstance(code, int) and (code == 429 or 500 <= code < 600):
            raise SkportError("unavailable")
        return data

    async def _signed(
        self, login_cred: str, sign_token: str, path: str, params: Optional[dict] = None
    ) -> dict[str, Any]:
        query = urlencode(params or {})
        timestamp = str(int(self.clock()))
        headers = {
            "cred": login_cred,
            "sk-language": "en",
            "timestamp": timestamp,
            "sign": sign(sign_token, path, query, timestamp),
            "vname": VNAME,
            "platform": PLATFORM,
            "user-agent": USER_AGENT,
            "accept": "*/*",
            "content-type": "application/json",
            "origin": "https://game.skport.com",
            "referer": "https://game.skport.com/",
        }
        url = f"{HOST}{path}?{query}" if query else f"{HOST}{path}"
        return await self._json(self.http().get(url, headers=headers))

    async def login(self, token: str) -> Login:
        """Account token -> credential, then the Endfield role it holds."""
        headers = {"user-agent": USER_AGENT, "accept": "*/*"}
        grant = await self._json(
            self.http().post(
                GRANT_URL,
                json={"appCode": APP_CODE, "token": token, "type": 0},
                headers=headers,
            )
        )
        code = (grant.get("data") or {}).get("code")
        if grant.get("status") != 0 or not code:
            raise SkportError("bad_token")
        made = await self._json(
            self.http().post(
                HOST + CRED_PATH, json={"code": code, "kind": 1}, headers=headers
            )
        )
        data = made.get("data") or {}
        cred, sign_token = data.get("cred"), data.get("token")
        if made.get("code") != 0 or not cred or not sign_token:
            raise SkportError("bad_token")

        binding = await self._signed(cred, sign_token, BINDING_PATH)
        if binding.get("code") != 0:
            raise SkportError("bad_token")
        role = None
        for app in (binding.get("data") or {}).get("list") or []:
            if app.get("appCode") == "endfield" and app.get("bindingList"):
                bound = app["bindingList"][0]
                roles = bound.get("roles") or [{}]
                role = bound.get("defaultRole") or roles[0]
                break
        if not role or not role.get("roleId"):
            raise SkportError("no_role")

        me = await self._signed(cred, sign_token, ME_PATH)
        user = (me.get("data") or {}).get("user") or {}
        if me.get("code") != 0 or not user.get("userId"):
            raise SkportError("bad_token")
        return Login(
            cred=cred,
            sign_token=sign_token,
            role_id=str(role["roleId"]),
            server_id=str(role.get("serverId", "")),
            user_id=str(user["userId"]),
            nickname=str(role.get("nickname") or ""),
        )

    async def detail(self, login: Login) -> dict[str, Any]:
        """The game card: every operator owned, stamina and the rest."""
        answer = await self._signed(
            login.cred,
            login.sign_token,
            DETAIL_PATH,
            {
                "roleId": login.role_id,
                "serverId": login.server_id,
                "userId": login.user_id,
            },
        )
        detail = (answer.get("data") or {}).get("detail")
        if answer.get("code") != 0 or not isinstance(detail, dict):
            raise SkportError("bad_token")  # most often the credential expired
        return detail

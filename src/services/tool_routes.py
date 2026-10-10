"""Authenticated metadata routes and scoped direct transfers for large files."""

import asyncio
import os
from urllib.parse import quote

from aiohttp import web

from src.services.tool_quota import MAX_TOTAL_BYTES
from src.services.tool_quota import valid_id
from src.utils.storage_worker import run_blocking


def engine(bot):
    cog = bot.get_cog("FileToolsCog")
    if cog is None or cog.engine.quota is None:
        raise ValueError("檔案服務尚未就緒")
    return cog.engine


def install_routes(app, bot):
    async def metadata(request):
        service = engine(bot)
        uid = valid_id(request.headers.get("X-Discord-User", ""))
        route = request.match_info["operation"]
        if request.method == "GET":
            if route == "usage":
                data = await run_blocking(service.quota.snapshot, uid)
            elif route == "coupons":
                data = await run_blocking(
                    service.quota.inventory,
                    uid,
                    request.query.get("used") == "1",
                    int(request.query.get("page", 0)),
                )
            elif route == "job":
                data = service.result(uid, request.query.get("id", ""))
                if data["state"] == "done":
                    data["downloadToken"] = service.tokens.issue(
                        uid, "download", jobId=data["id"]
                    )
            elif route == "jobs":
                items = await run_blocking(service.quota.jobs, uid)
                for item in items:
                    try:
                        current = service.result(uid, item["id"])
                        item.update(current)
                        if current["state"] == "done":
                            item["downloadToken"] = service.tokens.issue(
                                uid, "download", jobId=item["id"]
                            )
                    except ValueError:
                        item["available"] = False
                data = {"items": items}
            else:
                raise ValueError("未知檔案工具操作")
        else:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError("無效的處理設定")
            if route == "quote":
                sizes = body.get("sizes")
                if not isinstance(sizes, list) or len(sizes) > 16:
                    raise ValueError("無效的檔案清單")
                operation = body.get("format")
                quality = body.get("quality", 78)
                edge = body.get("maxEdge", 4096)
                if (
                    type(quality) is not int
                    or not 40 <= quality <= 95
                    or type(edge) is not int
                    or not 256 <= edge <= 8192
                ):
                    raise ValueError("輸出品質或尺寸不符合要求")
                data = await run_blocking(service.quota.quote, uid, sizes, operation)
                data["ticket"] = service.tokens.issue(
                    uid,
                    "upload",
                    sizes=sizes,
                    operation=operation,
                    quality=quality,
                    maxEdge=edge,
                )
            elif route == "redeem":
                coupon = body.get("couponId")
                if not isinstance(coupon, str) or len(coupon) > 128:
                    raise ValueError("無效的重置券")
                data = await run_blocking(service.quota.redeem, uid, coupon)
            else:
                raise ValueError("未知檔案工具操作")
        return web.json_response(data, headers={"Cache-Control": "no-store"})

    app.router.add_get("/tools/{operation:usage|coupons|job|jobs}", metadata)
    app.router.add_post("/tools/{operation:quote|redeem}", metadata)

    async def transfer(request):
        return await public_transfer(bot, request)

    app.router.add_route("*", "/tools/upload", transfer)
    app.router.add_route("*", "/tools/download", transfer)


async def public_transfer(bot, request):
    allowed = os.getenv("TOOL_WEB_ORIGIN", "https://botweb.shizune.life").rstrip("/")
    origin = request.headers.get("Origin")
    headers = {
        "Cache-Control": "no-store",
        "Vary": "Origin",
        "X-Content-Type-Options": "nosniff",
    }
    if origin:
        if origin != allowed:
            return web.json_response(
                {"error": "來源驗證失敗"}, status=403, headers=headers
            )
        headers.update(
            {
                "Access-Control-Allow-Origin": allowed,
                "Access-Control-Allow-Headers": "X-Tool-Token, Content-Type",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=headers)
    try:
        service = engine(bot)
        download = request.path == "/tools/download"
        if request.method != ("GET" if download else "POST"):
            return web.json_response(
                {"error": "不支援此方法"}, status=405, headers=headers
            )
        ticket = service.tokens.read(
            request.headers.get("X-Tool-Token") or request.query.get("ticket", ""),
            "download" if download else "upload",
        )
        uid = valid_id(ticket["uid"])
        if download:
            path, name = service.download(uid, ticket["jobId"])
            headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(
                name
            )
            headers["Content-Type"] = "application/octet-stream"
            return web.FileResponse(path, headers=headers)
        try:
            await asyncio.wait_for(service.uploads.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            return web.json_response(
                {"error": "上傳佇列已滿"}, status=429, headers=headers
            )
        try:
            files = await asyncio.wait_for(
                read_upload(request, ticket["sizes"]), timeout=90
            )
            job_id = await service.submit(
                uid,
                files,
                ticket["operation"],
                ticket["quality"],
                ticket["maxEdge"],
                ticket["nonce"],
            )
        finally:
            service.uploads.release()
        return web.json_response({"id": job_id}, status=202, headers=headers)
    except (ValueError, KeyError, TypeError, asyncio.TimeoutError):
        return web.json_response(
            {"error": "檔案授權、額度或內容不符合處理要求"}, status=400, headers=headers
        )
    except Exception:
        return web.json_response(
            {"error": "檔案服務暫時無法使用"}, status=503, headers=headers
        )


async def read_upload(request, sizes):
    reader = await request.multipart()
    files = []
    total = 0
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name != "files" or not part.filename or len(files) >= len(sizes):
            raise ValueError("檔案清單不符")
        data = bytearray()
        while True:
            chunk = await part.read_chunk(65536)
            if not chunk:
                break
            data.extend(chunk)
            total += len(chunk)
            if len(data) > sizes[len(files)] or total > MAX_TOTAL_BYTES:
                raise ValueError("檔案過大")
        if len(data) != sizes[len(files)]:
            raise ValueError("檔案大小不符")
        files.append((part.filename, bytes(data)))
    if len(files) != len(sizes):
        raise ValueError("檔案數量不符")
    return files

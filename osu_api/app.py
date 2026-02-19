import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from ossapi import Ossapi

load_dotenv()

API_KEY = os.getenv("API_KEY")
OSU_CLIENT_ID = os.getenv("OSU_CLIENT_ID")
OSU_CLIENT_SECRET = os.getenv("OSU_CLIENT_SECRET")

app = FastAPI(title="osu API")

_cache: dict[str, tuple[float, Any]] = {}


def _require_api_key(request: Request):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY 未設定")

    key = request.headers.get("X-API-Key")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_api() -> Ossapi:
    if not OSU_CLIENT_ID or not OSU_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="OSU_CLIENT_ID 或 OSU_CLIENT_SECRET 未設定")
    return Ossapi(int(OSU_CLIENT_ID), OSU_CLIENT_SECRET)


def _cache_get(cache_key: str):
    item = _cache.get(cache_key)
    if not item:
        return None

    expires_at, value = item
    if time.time() >= expires_at:
        _cache.pop(cache_key, None)
        return None

    return value


def _cache_set(cache_key: str, value: Any, ttl_seconds: int):
    _cache[cache_key] = (time.time() + ttl_seconds, value)


def _serialize_osu_user(user) -> dict:
    stats = getattr(user, "statistics", None)
    grade_counts = getattr(stats, "grade_counts", None) if stats else None

    return {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "is_supporter": getattr(user, "is_supporter", None),
        "avatar_url": getattr(user, "avatar_url", None),
        "cover_url": getattr(user, "cover_url", None),
        "join_date": getattr(user, "join_date", None).isoformat() if getattr(user, "join_date", None) else None,
        "statistics": {
            "global_rank": getattr(stats, "global_rank", None) if stats else None,
            "country_rank": getattr(stats, "country_rank", None) if stats else None,
            "pp": getattr(stats, "pp", None) if stats else None,
            "hit_accuracy": getattr(stats, "hit_accuracy", None) if stats else None,
            "play_time": getattr(stats, "play_time", None) if stats else None,
            "play_count": getattr(stats, "play_count", None) if stats else None,
            "total_score": getattr(stats, "total_score", None) if stats else None,
            "ranked_score": getattr(stats, "ranked_score", None) if stats else None,
            "maximum_combo": getattr(stats, "maximum_combo", None) if stats else None,
            "total_hits": getattr(stats, "total_hits", None) if stats else None,
            "grade_counts": {
                "ss": getattr(grade_counts, "ss", None) if grade_counts else None,
                "ssh": getattr(grade_counts, "ssh", None) if grade_counts else None,
                "s": getattr(grade_counts, "s", None) if grade_counts else None,
                "sh": getattr(grade_counts, "sh", None) if grade_counts else None,
                "a": getattr(grade_counts, "a", None) if grade_counts else None,
            },
        },
        "profile_url": f"https://osu.ppy.sh/users/{getattr(user, 'id', '')}",
    }


def _serialize_score(score) -> dict:
    beatmap = getattr(score, "beatmap", None)
    beatmapset = getattr(score, "beatmapset", None)
    statistics = getattr(score, "statistics", None)

    return {
        "id": getattr(score, "id", None),
        "created_at": getattr(score, "created_at", None).isoformat() if getattr(score, "created_at", None) else None,
        "rank": str(getattr(score, "rank", None)) if getattr(score, "rank", None) else None,
        "pp": getattr(score, "pp", None),
        "accuracy": getattr(score, "accuracy", None),
        "max_combo": getattr(score, "max_combo", None),
        "mods": [str(m) for m in getattr(score, "mods", [])] if getattr(score, "mods", None) else [],
        "statistics": {
            "count_miss": getattr(statistics, "count_miss", None) if statistics else None,
        },
        "beatmap": {
            "id": getattr(beatmap, "id", None) if beatmap else None,
            "version": getattr(beatmap, "version", None) if beatmap else None,
        },
        "beatmapset": {
            "title": getattr(beatmapset, "title", None) if beatmapset else None,
            "artist": getattr(beatmapset, "artist", None) if beatmapset else None,
        },
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/osu/user/{username}")
async def osu_user(username: str, request: Request, ttl: int = 60):
    _require_api_key(request)

    cache_key = f"user:{username.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {"cached": True, "data": cached}

    api = _get_api()
    try:
        user = api.user(username)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = _serialize_osu_user(user)
    _cache_set(cache_key, data, ttl_seconds=max(1, min(3600, ttl)))
    return {"cached": False, "data": data}


@app.get("/osu/best/{username}")
async def osu_best(username: str, request: Request, limit: int = 5, ttl: int = 60):
    _require_api_key(request)

    limit = max(1, min(10, limit))
    cache_key = f"best:{username.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {"cached": True, "data": cached}

    api = _get_api()
    try:
        user = api.user(username)
        scores = api.user_scores(user.id, type="best", limit=limit)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = {
        "user": _serialize_osu_user(user),
        "scores": [_serialize_score(s) for s in (scores or [])],
    }
    _cache_set(cache_key, data, ttl_seconds=max(1, min(3600, ttl)))
    return {"cached": False, "data": data}


@app.get("/osu/recent/{username}")
async def osu_recent(username: str, request: Request, limit: int = 5, ttl: int = 30):
    _require_api_key(request)

    limit = max(1, min(10, limit))
    cache_key = f"recent:{username.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {"cached": True, "data": cached}

    api = _get_api()
    try:
        user = api.user(username)
        scores = api.user_scores(user.id, type="recent", limit=limit)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    data = {
        "user": _serialize_osu_user(user),
        "scores": [_serialize_score(s) for s in (scores or [])],
    }
    _cache_set(cache_key, data, ttl_seconds=max(1, min(3600, ttl)))
    return {"cached": False, "data": data}

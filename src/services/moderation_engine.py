"""The three-stage image review: prepare an image, ask each model, decide."""

import asyncio
import base64
import io
import json
import re
import time

from PIL import Image
from PIL import ImageOps

if __package__:
    from . import moderation_protocol as protocol
    from .moderation_ollama import OllamaError
else:
    # Also support the isolated worker package's flat layout.
    from moderation_ollama import OllamaError
    import moderation_protocol as protocol

Image.MAX_IMAGE_PIXELS = 36_000_000
MAX_EDGE = 1024  # models look at a downscaled image anyway
MAX_FRAMES = 3  # an animated image is judged by up to this many frames


def prepare_image(data):
    """Up to three JPEG frames (base64) of an image, each at most 1024 px wide."""
    frames = []
    with Image.open(io.BytesIO(data)) as opened:
        count = getattr(opened, "n_frames", 1)
        picks = sorted(
            {round(i * (count - 1) / max(MAX_FRAMES - 1, 1)) for i in range(MAX_FRAMES)}
        )
        for number in picks if count > 1 else [0]:
            opened.seek(number)
            frame = ImageOps.exif_transpose(opened.convert("RGBA"))
            flat = Image.new("RGB", frame.size, "white")
            flat.paste(frame, mask=frame.getchannel("A"))
            flat.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            flat.save(out, format="JPEG", quality=88)
            frames.append(base64.b64encode(out.getvalue()).decode("ascii"))
    return frames


def parse_verdict(content):
    """The last JSON object with a ``verdict`` in a model's reply, or ``ValueError``."""
    decoder = json.JSONDecoder()
    found = None
    for match in re.finditer(r"\{", content):
        try:
            value, _ = decoder.raw_decode(content[match.start() :])
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("verdict") in (
            protocol.SAFE,
            protocol.UNSAFE,
            protocol.UNCERTAIN,
        ):
            found = value
    if found is None:
        raise ValueError("模型沒有回覆有效的判定")
    categories = found.get("categories")
    categories = [
        c
        for c in (categories if isinstance(categories, list) else [])
        if c in protocol.CATEGORIES
    ]
    reason = re.sub(r"[\x00-\x1f]+", " ", str(found.get("reason", ""))).strip()[:200]
    return found["verdict"], list(dict.fromkeys(categories)), reason


async def ask(ollama, stage, frames, seconds):
    """One stage's judgement of an image: ``(verdict, categories, reason)``."""
    prompt = (
        "Review this image."
        if len(frames) == 1
        else f"These {len(frames)} frames are from one animated image. Review all of it."
    )
    last = None
    for _ in range(2):  # a model that rambles gets one more try
        reply = await ollama.chat(
            stage["model"],
            protocol.PROMPTS[stage["stage"]],
            prompt,
            frames,
            think=stage["think"],
            seconds=seconds,
            tokens=8192 if stage["think"] else 400,
        )
        try:
            return parse_verdict(reply)
        except ValueError as error:
            last = error
    raise last


def _result(index, verdict, stage, categories, reason, stages):
    return {
        "index": index,
        "verdict": verdict,
        "stage": stage,
        "categories": categories,
        "reason": reason,
        "stages": stages,
    }


async def review_image(ollama, stages, index, data, emit=lambda *_: None):
    """Run ``data`` through every stage; the first unsafe stage ends the review.

    ``emit(kind, **details)`` reports progress for the terminal screen.
    Anything that stops a stage from giving a verdict (Ollama down, a timeout,
    an unreadable image) makes the whole review ``unavailable``: the bot then
    falls back to a human, and no model is ever allowed to guess.
    """
    done = []
    try:
        frames = await asyncio.to_thread(prepare_image, data)
    except Exception:
        return _result(index, protocol.UNAVAILABLE, 0, [], "圖片無法讀取", done)
    for stage in stages:
        number = stage["stage"]
        emit("stage", slot=index, stage=number, state="running")
        began = time.monotonic()
        try:
            verdict, categories, reason = await asyncio.wait_for(
                ask(ollama, stage, frames, protocol.STAGE_SECONDS[number - 1]),
                protocol.STAGE_SECONDS[number - 1] + 5,
            )
        except (OllamaError, asyncio.TimeoutError, ValueError):
            seconds = min(time.monotonic() - began, protocol.REVIEW_SECONDS)
            done.append(
                {"stage": number, "verdict": protocol.ERROR, "seconds": seconds}
            )
            emit("stage", slot=index, stage=number, state=protocol.ERROR)
            return _result(
                index, protocol.UNAVAILABLE, number, [], "模型沒有回覆", done
            )
        seconds = min(time.monotonic() - began, protocol.REVIEW_SECONDS)
        done.append({"stage": number, "verdict": verdict, "seconds": seconds})
        emit("stage", slot=index, stage=number, state=verdict)
        if verdict == protocol.UNSAFE:
            return _result(index, protocol.REJECTED, number, categories, reason, done)
        # The last stage cannot pass the buck: not being sure is not safe.
        if verdict == protocol.UNCERTAIN and number == len(stages):
            return _result(
                index, protocol.REJECTED, number, categories or ["tos"], reason, done
            )
    return _result(index, protocol.APPROVED, len(stages), [], "", done)

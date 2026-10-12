"""Contract between the bot and the image-review worker, and the review policy.

The worker judges an image with three local vision models, one after another:

1. a fast model looks for sexual content, violence and Discord rule violations;
2. a middle model with some reasoning looks again for anything stage 1 missed;
3. a high-reasoning model looks again, strictly, for anything stage 2 missed.

An image is approved only when all three stages call it safe. This module has
no network and no model code, so the bot and the worker package can both
import it; the worker also checks the digest of these files against the bot's.
"""

import hashlib
import math
from pathlib import Path
import re

PROTOCOL = 1
MAX_IMAGES = 2  # images reviewed at the same time
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # the same cap as the appearance commands
STAGE_SECONDS = (90, 180, 300)  # per stage, slowest model last
REVIEW_SECONDS = sum(STAGE_SECONDS) + 60  # one image, all stages
CATEGORIES = ("sexual", "violence", "tos")

# Verdicts of the whole review.
APPROVED, REJECTED, UNAVAILABLE = "approved", "rejected", "unavailable"
# Verdicts of one stage.
SAFE, UNSAFE, UNCERTAIN, ERROR = "safe", "unsafe", "uncertain", "error"

MODEL_PATTERN = re.compile(r"[a-z0-9][a-z0-9._/-]{0,60}:[a-z0-9][a-z0-9._-]{0,60}")

# Every model is a vision model: all three are Qwen3-VL so that one download
# source and one prompt style serve every stage. Sizes are the Ollama download
# sizes of the default (4-bit) builds.
DEFAULT_STAGES = (
    {"stage": 1, "label": "快速", "model": "qwen3-vl:2b-instruct", "think": False},
    {"stage": 2, "label": "中級", "model": "qwen3-vl:4b-thinking", "think": True},
    {"stage": 3, "label": "嚴格", "model": "qwen3-vl:8b-thinking", "think": True},
)

_POLICY = (
    "You review one image that a Discord server administrator wants to use as "
    "a bot's avatar or banner. Decide whether it may be used. Everyone, "
    "including children, can see it.\n"
    "Report UNSAFE content in these categories:\n"
    "- sexual: nudity, pornography, sexually explicit or suggestive content, "
    "sexualised depictions of anyone, and any sexualised minor (drawn or "
    "photographed).\n"
    "- violence: graphic violence, gore, injuries, corpses, cruelty to people "
    "or animals, weapons aimed at people, self-harm.\n"
    "- tos: anything that breaks Discord's Community Guidelines or Terms of "
    "Service: child safety issues, hate symbols or hateful speech, "
    "harassment, extremism, illegal goods or activity, scams or malware, "
    "personal data of others, real-world threats.\n"
    "Ordinary artwork, games, cartoons, logos, text and memes are safe. Do "
    "not flag something only because it is dark, scary or edgy.\n"
    'Reply with one JSON object and nothing else: {"verdict": "safe" | '
    '"unsafe" | "uncertain", "categories": [any of "sexual", "violence", '
    '"tos"], "reason": "one short sentence"}.'
)

PROMPTS = {
    1: _POLICY,
    2: (
        _POLICY + "\nA fast first pass judged this image safe. Do not trust it. Look "
        "again carefully at every part of the image, including the "
        "background, edges, small details, symbols and any text, and report "
        "anything the first pass could have missed."
    ),
    3: (
        _POLICY + "\nTwo earlier passes judged this image safe. You are the last and "
        "strictest reviewer. Inspect every region, every symbol and all "
        "text. If you cannot rule out a violation, answer uncertain."
    ),
}

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"enum": [SAFE, UNSAFE, UNCERTAIN]},
        "categories": {"type": "array", "items": {"enum": list(CATEGORIES)}},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "categories", "reason"],
}


def safe_name(name):
    return (
        re.sub(r"[^\w.() -]", "_", str(name).replace("\\", "/").split("/")[-1])[:100]
        or "image"
    )


def engine_digest():
    """Source digest of the review logic, so both ends run the same policy."""
    digest = hashlib.sha256()
    for name in ("moderation_protocol.py", "moderation_engine.py"):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def stage_config(models=None):
    """The three stages, with models replaced from the worker's configuration."""
    stages = [dict(stage) for stage in DEFAULT_STAGES]
    if models is not None:
        if not isinstance(models, dict) or set(models) - {"1", "2", "3"}:
            raise ValueError("模型設定格式無效")
        for key, model in models.items():
            if not isinstance(model, str) or not MODEL_PATTERN.fullmatch(model):
                raise ValueError("模型名稱無效")
            stages[int(key) - 1]["model"] = model
    return stages


def validate_manifest(data):
    if not isinstance(data, dict) or set(data) != {"jobId", "files", "engineDigest"}:
        raise ValueError("審核請求格式無效")
    if not isinstance(data["jobId"], str) or not re.fullmatch(
        r"[a-zA-Z0-9_-]{1,64}", data["jobId"]
    ):
        raise ValueError("工作識別碼無效")
    files = data["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_IMAGES:
        raise ValueError("一次最多審核兩張圖片")
    for entry in files:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"name", "bytes"}
            or not isinstance(entry["name"], str)
            or entry["name"] != safe_name(entry["name"])
            or type(entry["bytes"]) is not int
            or not 0 < entry["bytes"] <= MAX_IMAGE_BYTES
        ):
            raise ValueError("圖片資訊無效")
    if not isinstance(data["engineDigest"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", data["engineDigest"]
    ):
        raise ValueError("引擎識別碼無效")
    return data


def validate_result(data, count):
    """Check a worker's answer for ``count`` images; it is data from the network."""
    if not isinstance(data, dict) or set(data) != {"results", "engineDigest"}:
        raise ValueError("審核結果格式無效")
    if data["engineDigest"] != engine_digest():
        raise ValueError("審核節點引擎版本不一致")
    results = data["results"]
    if not isinstance(results, list) or len(results) != count:
        raise ValueError("審核結果數量不符")
    for index, item in enumerate(results):
        if (
            not isinstance(item, dict)
            or set(item)
            != {"index", "verdict", "stage", "categories", "reason", "stages"}
            or item["index"] != index
            or item["verdict"] not in (APPROVED, REJECTED, UNAVAILABLE)
            or type(item["stage"]) is not int
            or not 0 <= item["stage"] <= 3
            or not isinstance(item["categories"], list)
            or any(c not in CATEGORIES for c in item["categories"])
            or not isinstance(item["reason"], str)
            or len(item["reason"]) > 300
            or not isinstance(item["stages"], list)
            or len(item["stages"]) > 3
        ):
            raise ValueError("審核結果無效")
        for stage in item["stages"]:
            if (
                not isinstance(stage, dict)
                or set(stage) != {"stage", "verdict", "seconds"}
                or stage["stage"] not in (1, 2, 3)
                or stage["verdict"] not in (SAFE, UNSAFE, UNCERTAIN, ERROR)
                or type(stage["seconds"]) not in (int, float)
                or not math.isfinite(stage["seconds"])
                or not 0 <= stage["seconds"] <= REVIEW_SECONDS
            ):
                raise ValueError("審核階段資訊無效")
        # Approval needs all three stages, none unsafe, and a clear "safe" from
        # the last one; the worker cannot claim less.
        if item["verdict"] == APPROVED:
            stages = item["stages"]
            if (
                [s["stage"] for s in stages] != [1, 2, 3]
                or any(s["verdict"] not in (SAFE, UNCERTAIN) for s in stages)
                or stages[2]["verdict"] != SAFE
            ):
                raise ValueError("審核結果與階段不符")
    return data

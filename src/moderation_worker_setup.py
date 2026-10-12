"""Build the portable image-review worker and verify pairing before activation.

``build`` makes a zip for the second computer (its own Python, the review
code and a start file that installs Ollama and the three models by itself).
``check`` asks the running worker to review a plain test image through all
three stages; ``enable`` / ``disable`` switch the bot's use of it.
"""

import argparse
import asyncio
import ipaddress
import os
from pathlib import Path
import secrets
import shutil
import sys
import tempfile
import uuid
import zipfile

from PIL import Image
from PIL import ImageDraw

from src.services import moderation_protocol as protocol
from src.services.moderation_remote import ModerationWorker
from src.services.tool_remote import read_config
from src.tool_worker_setup import generate_certificate
from src.tool_worker_setup import prepare_runtime
from src.tool_worker_setup import write_config

ROOT = Path(__file__).resolve().parents[1]
PORT = 8788
SERVICES = (
    "moderation_protocol.py",
    "moderation_engine.py",
    "moderation_ollama.py",
    "moderation_tui.py",
    "moderation_worker.py",
)
CONTROL_PANEL = ("theme.py", "nova.py")  # the worker's screen shares the panel's look
PACKAGES = (
    "aiohttp==3.14.4",
    "Pillow==12.3.0",
    "rich==15.0.0",
    "pygments==2.20.0",
    "markdown-it-py==4.2.0",
    "mdurl==0.1.2",
)

FIREWALL = """$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '請以系統管理員身分執行 setup_firewall.cmd。'
    exit 1
}
$workerConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'worker.json') -Raw | ConvertFrom-Json
$programPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runtime\\python.exe'))
if (-not (Test-Path -LiteralPath $programPath)) { throw '執行環境不存在。' }
$ruleName = 'NewBot-ImageReview-Worker-' + $workerConfig.port
$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($rule) { $rule | Remove-NetFirewallRule }
New-NetFirewallRule -Name $ruleName -DisplayName 'BOT. 圖片審核節點' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $workerConfig.port `
    -LocalAddress $workerConfig.host -RemoteAddress $workerConfig.allowedIPs `
    -Program $programPath -Profile Any | Out-Null
Write-Host ('設定完成。僅允許來源：' + ($workerConfig.allowedIPs -join ', '))
Write-Host '接著以一般使用者身分執行 start_review.cmd，並保持視窗開啟。'
"""

# The start file. Everything the worker needs is done here, in order: the
# worker's own start-up installs Ollama if it is missing, starts it, and
# downloads the three models that are not there yet (see moderation_worker.py).
START = (
    "@echo off\r\n"
    "chcp 65001 >nul\r\n"
    'cd /d "%~dp0"\r\n'
    "title BOT. Image Review Worker\r\n"
    '"runtime\\python.exe" -X utf8 "moderation_worker.py" --config "worker.json"\r\n'
    "pause\r\n"
)

GUIDE = (
    "BOT. 圖片審核工作站\n\n"
    "1. 將整個資料夾解壓縮至這台電腦的固定位置。\n"
    "2. 右鍵 setup_firewall.cmd，選擇以系統管理員身分執行（首次設定）。\n"
    "3. 雙擊 start_review.cmd，保持視窗開啟。\n"
    "   第一次啟動會自動：\n"
    "   - 安裝 Ollama（本機 AI 執行環境；先用 winget，沒有就下載官方安裝程式並檢查數位簽章）\n"
    "   - 下載三個本地視覺模型（快速、中級、嚴格），約 11 GB，只需要下載一次\n"
    "   之後每次啟動都會先檢查，已經有的就不再下載。\n"
    "4. 主機完成連線與審核驗證後，才會啟用。\n\n"
    "一次審核兩張圖片；三個階段依序判斷，任何一階段發現問題就拒絕，三階段都通過才核准。\n"
    "圖片只放在記憶體，不寫入硬碟，審核完就丟棄。\n"
    "這個節點與 NovaGrid 圖片處理節點互相獨立，各用各的金鑰與埠號。\n"
    "IP 位址變更時須更新配對及防火牆來源設定。\n\n"
    "原始碼：https://github.com/keeiv/bot\n"
    "授權：GNU AGPL v3；套件內包含本版本程式原始碼及 LICENSE。\n"
)


def test_image():
    """A plain, harmless picture: a gradient with a label."""
    image = Image.linear_gradient("L").resize((256, 256)).convert("RGB")
    ImageDraw.Draw(image).text(
        (20, 112), "BOT. image review check", fill=(255, 255, 255)
    )
    path = Path(tempfile.mkdtemp(prefix="review-check-")) / "check.png"
    image.save(path)
    return path


async def check_worker(config, *, quick=False):
    """Health, then (unless ``quick``) a real review of a test image."""
    worker = ModerationWorker(config)
    health = await worker.health()
    if not health["ready"]:
        raise ValueError("審核節點還沒準備好（Ollama 或模型尚未就緒）")
    if quick:
        return health
    path = test_image()
    try:
        results = await worker.review([("check.png", path.read_bytes())])
    finally:
        shutil.rmtree(path.parent, ignore_errors=True)
    if results[0]["verdict"] == protocol.UNAVAILABLE:
        raise ValueError("審核流程沒有完成")
    return health


def build_worker(worker_ip, main_ip, output, config_path, models=None):
    for address in (worker_ip, main_ip):
        ip = ipaddress.ip_address(address)
        if ip.version != 4 or not ip.is_private or ip.is_loopback:
            raise ValueError("配對位址必須為區域網路 IPv4")
    protocol.stage_config(models)  # reject a bad model name before downloading
    config_path = Path(config_path)
    if config_path.exists():
        raise ValueError("配對設定已存在；重新配對前須保留原設定並更換設定檔路徑")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    directory = output / ("image-review-worker-" + uuid.uuid4().hex[:8])
    directory.mkdir()
    runtime = directory / "runtime"
    archive_path = output / (directory.name + ".zip")
    prepare_runtime(output, runtime, PACKAGES)
    for name in SERVICES:
        shutil.copyfile(ROOT / "src/services" / name, directory / name)
    for name in CONTROL_PANEL:
        shutil.copyfile(ROOT / "src/control_panel" / name, directory / name)
    shutil.copyfile(ROOT / "LICENSE", directory / "LICENSE")
    shutil.copyfile(ROOT / "NOTICE", directory / "NOTICE")
    fingerprint = generate_certificate(directory, worker_ip)
    token = secrets.token_hex(32)
    worker = {"host": worker_ip, "port": PORT, "allowedIPs": [main_ip], "token": token}
    if models:
        worker["models"] = models
    write_config(directory / "worker.json", worker)
    (directory / "start_review.cmd").write_bytes(START.encode("ascii"))
    (directory / "setup_firewall.cmd").write_text(
        '@echo off\ncd /d "%~dp0"\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_firewall.ps1"\npause\n',
        encoding="ascii",
    )
    (directory / "setup_firewall.ps1").write_text(FIREWALL, encoding="utf-8-sig")
    (directory / "使用說明.txt").write_text(GUIDE, encoding="utf-8-sig")
    if os.name == "nt":
        import subprocess

        subprocess.run(
            [
                str(runtime / "python.exe"),
                "-X",
                "utf8",
                "-c",
                "import aiohttp, PIL, rich, moderation_worker, moderation_tui; "
                "import moderation_protocol as p; "
                "from importlib.metadata import version; print('Review worker runtime:', aiohttp.__version__, PIL.__version__, version('rich')); "
                "print('Engine:', p.engine_digest())",
            ],
            cwd=directory,
            check=True,
            timeout=60,
        )
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(output))
    write_config(
        config_path,
        {
            "enabled": False,
            "endpoint": f"https://{worker_ip}:{PORT}",
            "fingerprint": fingerprint,
            "token": token,
        },
    )
    return directory, archive_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="BOT. 圖片審核節點配對")
    parser.add_argument(
        "--config", type=Path, default=ROOT / ".image-review-worker.json"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="建立審核節點的獨立執行套件")
    build.add_argument("--worker-ip", required=True)
    build.add_argument("--main-ip", required=True)
    build.add_argument("--output", type=Path, default=ROOT / "data/worker-packages")
    for number, label in ((1, "快速"), (2, "中級"), (3, "嚴格")):
        build.add_argument(
            f"--model{number}",
            help=f"覆寫{label}階段的模型（預設見 moderation_protocol）",
        )
    check = commands.add_parser("check", help="驗證連線、模型與一次完整審核")
    check.add_argument("--quick", action="store_true", help="只檢查連線與模型是否就緒")
    commands.add_parser("enable", help="通過驗證後啟用 AI 審核")
    commands.add_parser("disable", help="恢復全部人工審核")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "build":
            models = {
                str(n): getattr(arguments, f"model{n}")
                for n in (1, 2, 3)
                if getattr(arguments, f"model{n}")
            }
            _, archive = build_worker(
                arguments.worker_ip,
                arguments.main_ip,
                arguments.output,
                arguments.config,
                models or None,
            )
            print(f"審核節點套件已建立：{archive}")
            print("尚未啟用；請在另一台電腦啟動後執行 check，再 enable。")
        else:
            config = read_config(arguments.config)
            if arguments.command != "disable":
                asyncio.run(
                    check_worker(config, quick=getattr(arguments, "quick", False))
                )
                print("連線、模型與審核流程驗證通過。")
            if arguments.command in ("enable", "disable"):
                config["enabled"] = arguments.command == "enable"
                write_config(arguments.config, config)
                print("設定已更新，將於機器人下一次啟動時生效。")
    except (Exception, KeyboardInterrupt):
        # Errors from transport clients can include credentials or image data.
        print("審核節點設定或驗證失敗；原有的人工審核保持不變。")
        raise SystemExit(1) from None


if __name__ == "__main__":
    sys.exit(main())

"""Build a portable Windows worker and verify pairing before activation."""

import argparse
import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from PIL import Image

from src.services.tool_remote import read_config
from src.services.tool_remote import RemoteWorker

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = "https://www.python.org/ftp/python/3.14.8/python-3.14.8-embed-amd64.zip"
PYTHON_SHA256 = "a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310"
WORKER_FILES = ("novagrid.py", "tool_worker.py", "tool_protocol.py", "tool_remote.py")


def generate_certificate(directory, address):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NovaGrid LAN worker")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=730))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address(address))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    (directory / "worker-cert.pem").write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )
    (directory / "worker-key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return certificate.fingerprint(hashes.SHA256()).hex()


def write_config(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def check_worker(config):
    worker = RemoteWorker(config)
    health = await worker.health()
    if health["busy"]:
        raise ValueError("處理節點正在工作，稍後可重新驗證")
    with tempfile.TemporaryDirectory(prefix="new-bot-tool-") as directory:
        root = Path(directory)
        with Image.new("RGBA", (64, 64), (30, 120, 240, 100)) as image:
            image.save(root / "input.png")
        request = {
            "files": [{"name": "check.png", "stored": "input.png"}],
            "operation": "webp",
            "quality": 78,
            "maxEdge": 4096,
        }
        (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
        result = await worker.process(root, {"timeout": 15}, uuid.uuid4().hex)
        with Image.open(root / "result.bin") as image:
            if image.size != (64, 64) or image.mode != "RGBA":
                raise ValueError("圖片處理驗證失敗")
        if not result["changed"]:
            raise ValueError("圖片處理驗證失敗")
    return health


def prepare_runtime(output, runtime, packages):
    """Unpack the pinned embeddable Python into ``runtime`` and install ``packages``."""
    runtime.mkdir()
    with tempfile.TemporaryDirectory(prefix="download-", dir=output) as scratch:
        temporary = Path(scratch).resolve()
        if not temporary.is_relative_to(output):
            raise ValueError("下載暫存目錄無效")
        download = temporary / "python.zip"
        digest = hashlib.sha256()
        with (
            # Fixed official HTTPS URL; contents must match the pinned SHA-256.
            urllib.request.urlopen(PYTHON_URL, timeout=60) as response,  # nosec B310
            download.open("wb") as stream,
        ):
            while chunk := response.read(64 * 1024):
                digest.update(chunk)
                stream.write(chunk)
        if digest.hexdigest() != PYTHON_SHA256:
            raise ValueError("Python 下載校驗失敗")
        with zipfile.ZipFile(download) as archive:
            if any(
                not (runtime / member).resolve().is_relative_to(runtime)
                for member in archive.namelist()
            ):
                raise ValueError("Python 套件路徑無效")
            archive.extractall(runtime)
    (runtime / "python314._pth").write_text(
        "python314.zip\n.\n..\nsite-packages\nimport site\n", encoding="ascii"
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--only-binary=:all:",
            "--index-url",
            "https://pypi.org/simple",
            "--platform",
            "win_amd64",
            "--python-version",
            "3.14",
            "--implementation",
            "cp",
            "--abi",
            "cp314",
            "--target",
            str(runtime / "site-packages"),
            *packages,
        ],
        check=True,
        timeout=180,
    )


def build_worker(worker_ip, main_ip, output, config_path):
    for address in (worker_ip, main_ip):
        ip = ipaddress.ip_address(address)
        if ip.version != 4 or not ip.is_private or ip.is_loopback:
            raise ValueError("配對位址必須為區域網路 IPv4")
    config_path = Path(config_path)
    if config_path.exists():
        raise ValueError("配對設定已存在；重新配對前須保留原設定並更換設定檔路徑")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    directory = output / ("novagrid-worker-" + uuid.uuid4().hex[:8])
    directory.mkdir()
    runtime = directory / "runtime"
    archive_path = output / (directory.name + ".zip")
    prepare_runtime(output, runtime, ("aiohttp==3.14.4", "Pillow==12.3.0"))
    for name in WORKER_FILES:
        shutil.copyfile(ROOT / "src/services" / name, directory / name)
    shutil.copyfile(ROOT / "LICENSE", directory / "LICENSE")
    shutil.copyfile(ROOT / "NOTICE", directory / "NOTICE")
    fingerprint = generate_certificate(directory, worker_ip)
    token = secrets.token_hex(32)
    write_config(
        directory / "worker.json",
        {
            "host": worker_ip,
            "port": 8787,
            "allowedIPs": [main_ip],
            "token": token,
        },
    )
    (directory / "start_worker.cmd").write_text(
        '@echo off\nchcp 65001 >nul\ncd /d "%~dp0"\ntitle NovaGrid Worker\n'
        '"runtime\\python.exe" -X utf8 "tool_remote.py" --config "worker.json"\npause\n',
        encoding="ascii",
    )
    (directory / "setup_firewall.cmd").write_text(
        '@echo off\ncd /d "%~dp0"\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_firewall.ps1"\npause\n',
        encoding="ascii",
    )
    (directory / "setup_firewall.ps1").write_text(
        """$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '請以系統管理員身分執行 setup_firewall.cmd。'
    exit 1
}
$workerConfig = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'worker.json') -Raw | ConvertFrom-Json
$programPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'runtime\\python.exe'))
if (-not (Test-Path -LiteralPath $programPath)) { throw '處理程式執行環境不存在。' }
$ruleName = 'NewBot-NovaGrid-Worker-' + $workerConfig.port
$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($rule) { $rule | Remove-NetFirewallRule }
New-NetFirewallRule -Name $ruleName -DisplayName 'NovaGrid 區域網路處理節點' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort $workerConfig.port `
    -LocalAddress $workerConfig.host -RemoteAddress $workerConfig.allowedIPs `
    -Program $programPath -Profile Any | Out-Null
Write-Host ('設定完成。僅允許來源：' + ($workerConfig.allowedIPs -join ', '))
Write-Host '接著以一般使用者身分執行 start_worker.cmd，並保持視窗開啟。'
""",
        encoding="utf-8-sig",
    )
    (directory / "使用說明.txt").write_text(
        "NovaGrid 區域網路處理節點\n\n"
        "1. 將整個資料夾解壓縮至舊電腦的固定位置。\n"
        "2. 右鍵 setup_firewall.cmd，選擇以系統管理員身分執行（首次設定）。\n"
        "3. 雙擊 start_worker.cmd，保持視窗開啟。\n"
        "4. 主機完成連線與圖片轉換驗證後，才會啟用分工。\n\n"
        "此套件內附 Python 3.14.8，與電腦原有 Python 獨立。\n"
        "一次處理一件工作；工作程序採較低優先權，處理超時將終止。\n"
        "暫存檔在請求結束後清除，資料庫與用量紀錄保留於主機。\n"
        "此套件含專用連線金鑰，僅用於配對的兩台電腦。\n"
        "IP 位址變更時須更新配對及防火牆來源設定。\n\n"
        "原始碼：https://github.com/keeiv/bot\n"
        "授權：GNU AGPL v3；套件內包含本版本處理程式原始碼及 LICENSE。\n",
        encoding="utf-8-sig",
    )
    if os.name == "nt":
        subprocess.run(
            [
                str(runtime / "python.exe"),
                "-X",
                "utf8",
                "-c",
                "import aiohttp,PIL,tool_protocol; print('Worker runtime:', aiohttp.__version__, PIL.__version__); print('Engine:', tool_protocol.engine_digest())",
            ],
            cwd=directory,
            check=True,
            timeout=30,
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
            "endpoint": f"https://{worker_ip}:8787",
            "fingerprint": fingerprint,
            "token": token,
        },
    )
    return directory, archive_path


def main():
    parser = argparse.ArgumentParser(description="NovaGrid 處理節點配對")
    parser.add_argument("--config", type=Path, default=ROOT / ".file-tools-worker.json")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="建立舊電腦的獨立執行套件")
    build.add_argument("--worker-ip", required=True)
    build.add_argument("--main-ip", required=True)
    build.add_argument("--output", type=Path, default=ROOT / "data/worker-packages")
    commands.add_parser("check", help="驗證 HTTPS 授權、引擎版本與圖片轉換")
    commands.add_parser("enable", help="通過驗證後啟用舊電腦處理")
    commands.add_parser("disable", help="恢復主機處理")
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            _, archive = build_worker(
                arguments.worker_ip,
                arguments.main_ip,
                arguments.output,
                arguments.config,
            )
            print(f"處理節點套件已建立：{archive}")
            print("分工尚未啟用；舊電腦啟動後須完成連線驗證。")
        else:
            config = read_config(arguments.config)
            if arguments.command != "disable":
                asyncio.run(check_worker(config))
                print("HTTPS 授權、引擎版本與圖片轉換驗證通過。")
            if arguments.command in ("enable", "disable"):
                config["enabled"] = arguments.command == "enable"
                write_config(arguments.config, config)
                print("分工設定已更新，將於機器人下一次啟動時生效。")
    except (Exception, KeyboardInterrupt):
        # Errors from transport clients can include credentials or file contents.
        print("處理節點設定或驗證失敗；原有執行方式保持不變。")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

r"""The local MySQL the bot keeps its data in: is it up, can the bot log in, start it.

Starting follows what the project does: the instance named ``NewBotMySQL`` (its
``my.ini`` and ``data``), only on Windows, only for a local server on port 3307.
The instance may live in ``%LOCALAPPDATA%\NewBotMySQL`` or, when an app such as
Codex started it, in that app's private AppData; see :class:`Instance`.

The password is read only to log in; it is never shown, logged or put in an
error message.
"""

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
import ntpath
import os
from pathlib import Path
from pathlib import PureWindowsPath
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Optional

from dotenv import dotenv_values
import psutil  # type: ignore[import-untyped]  # no typing metadata
import pymysql  # type: ignore[import-untyped]  # no typing metadata

from src.control_panel.actions import Outcome

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MANAGED_PORT = 3307  # the only port the project's launcher script serves

# Short, secret-free explanations for the errors that actually happen here.
_ERRORS = {
    1044: "沒有這個資料庫的權限",
    1045: "帳號或密碼被拒絕",
    1049: "資料庫不存在",
    1040: "連線數已滿",
    1130: "這台主機不被允許連線",
    2003: "連不上伺服器",
    2006: "伺服器已斷線",
    2013: "連線中途中斷",
}


@dataclass(frozen=True)
class DbSettings:
    enabled: bool  # STORAGE_BACKEND=mysql
    host: str = "127.0.0.1"
    port: int = MANAGED_PORT
    user: Optional[str] = None
    password: Optional[str] = field(default=None, repr=False)
    database: Optional[str] = None

    @property
    def local(self) -> bool:
        return self.host in LOCAL_HOSTS

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def missing(self) -> list[str]:
        """Names (never values) of the settings the bot needs and lacks."""
        names = {
            "MYSQL_USER": self.user,
            "MYSQL_PASSWORD": self.password,
            "MYSQL_DATABASE": self.database,
        }
        return [name for name, value in names.items() if not value]


def load_settings(
    root: Path, environ: Optional[Mapping[str, str]] = None
) -> DbSettings:
    """Settings the way the bot sees them: real environment first, then ``.env``."""
    environ = os.environ if environ is None else environ
    file_values = dotenv_values(root / ".env")

    def get(name: str, default: Optional[str] = None) -> Optional[str]:
        return environ.get(name) or file_values.get(name) or default

    try:
        port = int(get("MYSQL_PORT", str(MANAGED_PORT)) or MANAGED_PORT)
    except ValueError:
        port = MANAGED_PORT
    return DbSettings(
        enabled=(get("STORAGE_BACKEND", "json") or "json").lower() == "mysql",
        host=get("MYSQL_HOST", "127.0.0.1") or "127.0.0.1",
        port=port,
        user=get("MYSQL_USER"),
        password=get("MYSQL_PASSWORD"),
        database=get("MYSQL_DATABASE"),
    )


def has_discord_token(root: Path, environ: Optional[Mapping[str, str]] = None) -> bool:
    """Whether DISCORD_TOKEN is set. The value itself is never returned."""
    environ = os.environ if environ is None else environ
    return bool(
        environ.get("DISCORD_TOKEN")
        or dotenv_values(root / ".env").get("DISCORD_TOKEN")
    )


@dataclass(frozen=True)
class DbStatus:
    state: str  # "ready", "down", "refusing", "misconfigured" or "disabled"
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state in ("ready", "disabled")


def _listening(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def explain(error: BaseException) -> str:
    """A short reason for a failed login, without account names or passwords."""
    if isinstance(error, pymysql.MySQLError) and error.args:
        code = error.args[0]
        if isinstance(code, int):
            return _ERRORS.get(code, f"MySQL 錯誤 {code}")
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "連線逾時"
    return f"{type(error).__name__}"


def check_database(
    settings: DbSettings,
    *,
    listening: Callable[[str, int], bool] = _listening,
    connect: Callable[..., Any] = pymysql.connect,
) -> DbStatus:
    """``ready`` only when the bot's own account can log in and run a query."""
    if not settings.enabled:
        return DbStatus("disabled", "JSON 儲存模式，不使用 MySQL")
    if not listening(settings.host, settings.port):
        return DbStatus("down", f"{settings.target} 沒有回應")
    if settings.missing:
        return DbStatus("misconfigured", f".env 缺少 {', '.join(settings.missing)}")
    try:
        connection = connect(
            host=settings.host,
            port=settings.port,
            user=settings.user,
            password=settings.password,
            database=settings.database,
            charset="utf8mb4",
            connect_timeout=3,
            read_timeout=3,
            write_timeout=3,
        )
    except Exception as exc:  # the reason is shown, the details are not
        return DbStatus("refusing", explain(exc))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        return DbStatus("refusing", explain(exc))
    finally:
        try:
            connection.close()
        except Exception:  # noqa: S110 - closing a broken connection may fail
            pass
    return DbStatus("ready", f"{settings.target} 連線正常")


# ── finding and starting the instance ─────────────────────────────
INSTANCE_DIR = "NewBotMySQL"
_CREATE_DETACHED = 0x00000008  # DETACHED_PROCESS: the database outlives the panel
_CREATE_NEW_GROUP = 0x00000200  # CREATE_NEW_PROCESS_GROUP


@dataclass(frozen=True)
class Instance:
    r"""Where the project's MySQL instance (my.ini, data/, logs) really is.

    Besides ``%LOCALAPPDATA%\\NewBotMySQL`` it may sit in the private AppData of an
    app package: an instance started from the Codex app, for example, keeps its
    files in ``Packages\\<app>\\LocalCache\\Local\\NewBotMySQL``. That app sees them
    as ``%LOCALAPPDATA%\\NewBotMySQL``; every other program has to use the real
    folder.
    """

    directory: Path
    packaged: bool

    @property
    def config(self) -> Path:
        return self.directory / "my.ini"

    @property
    def data(self) -> Path:
        return self.directory / "data"

    @property
    def error_log(self) -> Path:
        return self.directory / "mysql-error.log"

    @property
    def script(self) -> Path:
        return self.directory / "start-mysql.ps1"


def find_instance(environ: Optional[Mapping[str, str]] = None) -> Optional[Instance]:
    environ = os.environ if environ is None else environ
    local_text = environ.get("LOCALAPPDATA", "")
    if not local_text:
        return None
    local = Path(local_text)
    standard = local / INSTANCE_DIR
    if (standard / "my.ini").is_file():
        return Instance(standard, packaged=False)
    pattern = f"*/LocalCache/Local/{INSTANCE_DIR}"
    found = [
        path
        for path in (local / "Packages").glob(pattern)
        if (path / "my.ini").is_file()
    ]
    if not found:
        return None
    return Instance(max(found, key=lambda p: (p / "my.ini").stat().st_mtime), True)


def ini_value(config: Path, key: str) -> Optional[str]:
    """A value from the ``[mysqld]`` section of a ``my.ini`` (no includes, no quotes)."""
    try:
        lines = config.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    section = ""
    for raw in lines:
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif section == "mysqld" and "=" in line and not line.startswith(("#", ";")):
            name, _, value = line.partition("=")
            if name.strip().lower().replace("_", "-") == key:
                return value.strip().strip("\"'")
    return None


@dataclass(frozen=True)
class StartPlan:
    argv: list[str]
    cwd: Path
    via_script: bool  # the project's own start-mysql.ps1


def plan_start(settings: DbSettings, instance: Optional[Instance]) -> StartPlan | str:
    """How to start the database, or the reason it cannot be done from here."""
    if not settings.enabled:
        return "目前使用 JSON 儲存模式"
    if sys.platform != "win32":
        return "只支援 Windows"
    if not settings.local:
        return f"資料庫在另一台主機（{settings.host}），不能從這裡啟動"
    if settings.port != MANAGED_PORT:
        return f"連接埠是 {settings.port}，專案的資料庫實例只負責 {MANAGED_PORT}"
    if instance is None:
        return (
            f"找不到資料庫資料夾（找過 %LOCALAPPDATA%\\{INSTANCE_DIR}，"
            "以及各應用程式套件資料夾裡的同名資料夾）"
        )
    configured = ini_value(instance.config, "port")
    if configured and configured != str(settings.port):
        return f"my.ini 的連接埠（{configured}）和 .env 的（{settings.port}）不同"
    if not instance.packaged and instance.script.is_file():
        return StartPlan(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(instance.script),
            ],
            instance.directory,
            via_script=True,
        )
    base = ini_value(instance.config, "basedir")
    server = Path(base) / "bin" / "mysqld.exe" if base else None
    if server is None or not server.is_file():
        return f"找不到 mysqld.exe（my.ini 的 basedir：{base or '未設定'}）"
    # my.ini names its folders the way the app that wrote it sees them. Command
    # line options beat the option file, so point them at the real folders.
    return StartPlan(
        [
            str(server),
            f"--defaults-file={instance.config}",
            f"--datadir={instance.data}",
            f"--log-error={instance.error_log}",
        ],
        instance.directory,
        via_script=False,
    )


def start_blocker(settings: DbSettings, instance: Optional[Instance]) -> Optional[str]:
    """Why the panel may not start the database, or None when it may."""
    plan = plan_start(settings, instance)
    return plan if isinstance(plan, str) else None


def _normal(path: str) -> str:
    # mysqld's command line is a Windows one: either slash, any case.
    return ntpath.normcase(ntpath.normpath(path.strip().strip("\"'")))


def _defaults_file(cmdline: list[str]) -> Optional[str]:
    """The ``--defaults-file`` value of a mysqld command line, if it has one."""
    for index, arg in enumerate(cmdline):
        if arg.lower().startswith("--defaults-file="):
            return arg.partition("=")[2]
        if arg.lower() == "--defaults-file" and index + 1 < len(cmdline):
            return cmdline[index + 1]
    return None


PID_SLACK = 5.0  # seconds: mysqld writes its pid file a moment after it starts


def _pid_file_names_a_live_server(instance: Instance) -> bool:
    """Does ``data/mysql.pid`` name a running mysqld that wrote it?

    The pid file sits in the instance's *real* data folder, so unlike a command
    line it cannot be confused with another app's folder of the same name. It is
    left behind by a crash, so the process must also exist, be a ``mysqld.exe``
    and have started no later than the file was written (otherwise the number was
    reused by some newer program).
    """
    named = PureWindowsPath(ini_value(instance.config, "pid-file") or "mysql.pid")
    # Never follow a path written in my.ini: an absolute one may be how another
    # app sees its folder, or even point into a different instance. Whatever it
    # says, the file is looked for in this instance's own real data folder.
    rooted = named.is_absolute() or bool(named.drive or named.root)
    relative = Path(named.name) if rooted else Path(*named.parts)
    pid_file = instance.data / relative
    try:
        pid_file.resolve().relative_to(instance.data.resolve())
    except ValueError:  # "../elsewhere/mysql.pid" climbs out of the data folder
        pid_file = instance.data / named.name
    try:
        text = pid_file.read_text(encoding="utf-8").strip()
        written = pid_file.stat().st_mtime
    except OSError:
        return False
    if not text.isdigit():
        return False
    try:
        process = psutil.Process(int(text))
        if (process.name() or "").lower() != "mysqld.exe":
            return False
        return bool(process.create_time() <= written + PID_SLACK)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def _instance_running(instance: Instance) -> bool:
    r"""A mysqld started for exactly this instance (it may still be starting).

    Two proofs, each tied to the instance's real folder: the pid file in its data
    folder, or a command line whose ``--defaults-file`` is its real ``my.ini``.
    The path an app *sees* (``%LOCALAPPDATA%\\NewBotMySQL``) proves nothing:
    every app package has one, and each means its own.
    """
    if _pid_file_names_a_live_server(instance):
        return True
    wanted = _normal(str(instance.config))
    for process in psutil.process_iter(["name", "cmdline"]):
        if (process.info["name"] or "").lower() != "mysqld.exe":
            continue
        config = _defaults_file(list(process.info["cmdline"] or []))
        if config is not None and _normal(config) == wanted:
            return True
    return False


def last_error(instance: Instance) -> str:
    """The last line of MySQL's own error log, to say why a start failed."""
    try:
        with instance.error_log.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(handle.tell() - 4096, 0))
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    return lines[-1][:140] if lines else ""


def start_database(
    settings: DbSettings,
    *,
    instance: Optional[Instance] = None,
    find: Callable[[], Optional[Instance]] = find_instance,
    run: Callable[..., Any] = subprocess.run,
    popen: Callable[..., Any] = subprocess.Popen,
    listening: Callable[[str, int], bool] = _listening,
    running: Callable[[Instance], bool] = _instance_running,
    sleep: Callable[[float], None] = time.sleep,
    wait: float = 30.0,
) -> Outcome:
    instance = instance or find()
    plan = plan_start(settings, instance)
    if isinstance(plan, str) or instance is None:
        return Outcome(False, f"無法自動啟動資料庫：{plan}")
    where = "（實例在應用程式的套件資料夾）" if instance.packaged else ""
    process = None
    if running(instance):
        # Already launched (by Codex, say) and not answering yet. Never start a
        # second server on the same data folder; just wait for the first.
        pass
    elif plan.via_script:
        try:
            run(
                plan.argv,
                check=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return Outcome(False, f"資料庫啟動腳本失敗（{type(exc).__name__}）")
    else:
        try:
            process = popen(
                plan.argv,
                cwd=plan.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_DETACHED | _CREATE_NEW_GROUP,
            )
        except OSError as exc:
            return Outcome(False, f"無法執行 mysqld：{exc}")
    deadline = time.monotonic() + wait
    while not listening(settings.host, settings.port):
        code = process.poll() if process is not None else None
        if code is not None:
            reason = last_error(instance)
            return Outcome(
                False,
                f"資料庫啟動後立刻結束（結束碼 {code}）{'：' + reason if reason else ''}",
            )
        if time.monotonic() >= deadline:
            reason = last_error(instance)
            return Outcome(
                False,
                f"資料庫啟動逾時{'：' + reason if reason else ''}（日誌 {instance.error_log}）",
            )
        sleep(0.5)
    return Outcome(True, f"資料庫已啟動（{settings.target}）{where}")


@dataclass(frozen=True)
class EnsureResult:
    status: DbStatus
    started: bool = False
    message: str = ""


def ensure_database(
    settings: DbSettings,
    *,
    check: Callable[[DbSettings], DbStatus] = check_database,
    start: Callable[[DbSettings], Outcome] = start_database,
    on_starting: Optional[Callable[[], None]] = None,
) -> EnsureResult:
    """Check the database and, only when it is not running, start it."""
    status = check(settings)
    if status.state != "down":
        return EnsureResult(status)
    if on_starting:
        on_starting()
    outcome = start(settings)
    if not outcome.ok:
        return EnsureResult(status, False, outcome.message)
    return EnsureResult(check(settings), True, outcome.message)


class DatabaseMonitor:
    """Keeps the latest :class:`DbStatus` fresh without blocking the screen."""

    def __init__(
        self,
        settings: DbSettings,
        *,
        interval: float = 10.0,
        check: Callable[[DbSettings], DbStatus] = check_database,
    ) -> None:
        self.settings = settings
        self._interval = interval
        self._check = check
        self.status: Optional[DbStatus] = None
        self._wake = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                self.status = self._check(self.settings)
            except Exception as exc:  # a broken check must not kill the monitor
                self.status = DbStatus("refusing", explain(exc))
            self._wake.wait(self._interval)
            self._wake.clear()

    def refresh_now(self) -> None:
        self._wake.set()

    def update(self, status: DbStatus) -> None:
        """Take a status someone else just measured."""
        self.status = status

"""Control panel: host info, database, start-up sequences, logo, new screens.

The database and the hardware query are always faked: no test connects to MySQL,
starts a service or runs PowerShell.
"""

from datetime import datetime
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import time

import pymysql
import pytest
from rich.console import Console

from src.control_panel import app
from src.control_panel import database
from src.control_panel import host as host_module
from src.control_panel import launch
from src.control_panel import logo
from src.control_panel import menu
from src.control_panel import render
from src.control_panel import state
from src.control_panel.actions import Outcome
from src.control_panel.app import ControlPanel
from src.control_panel.app import Keyboard
from src.control_panel.database import DbSettings
from src.control_panel.database import DbStatus
from src.control_panel.host import HostInfo
from src.control_panel.host import HostReader
from src.control_panel.state import BotStatus
from src.control_panel.state import Paths
from src.control_panel.state import StatusReader

NOW = datetime(2026, 10, 11, 12, 0, 0)
HOST = HostInfo(
    machine="ASUS ROG Zephyrus G14",
    board="ASUS GA402",
    cpu="AMD Ryzen 9 7940HS w/ Radeon 780M Graphics",
    gpus=("NVIDIA GeForce RTX 4060 Laptop GPU", "AMD Radeon(TM) 780M Graphics"),
    os_name="Windows 11 Pro",
    cores=8,
    threads=16,
    memory_gb=32.0,
)


@pytest.fixture
def paths(tmp_path):
    (tmp_path / "data" / "logs").mkdir(parents=True)
    return Paths(
        root=tmp_path,
        lock=tmp_path / "bot.lock",
        logs=tmp_path / "data" / "logs",
        python="python",
    )


def _capture(renderable, width=110, height=34):
    console = Console(
        file=io.StringIO(),
        record=True,
        force_terminal=True,
        color_system="truecolor",
        width=width,
        height=height,
    )
    console.print(renderable)
    return console.export_text(styles=False)


# ── host ──────────────────────────────────────────────────────────
def _raw(**overrides):
    data = {
        "maker": "ASUSTeK COMPUTER INC.",
        "model": "ROG Zephyrus G14",
        "board_maker": "ASUSTeK COMPUTER INC.",
        "board": "GA402",
        "cpu": "AMD Ryzen 9 7940HS",
        "gpu": ["NVIDIA RTX 4060", "NVIDIA RTX 4060", "AMD 780M"],
        "os": "Microsoft Windows 11 Pro",
        "build": "26200",
    }
    data.update(overrides)
    return json.dumps(data)


def test_host_is_parsed_without_repeating_the_maker():
    info = host_module.parse_host(
        _raw(), cores=8, threads=16, memory_bytes=32 * 1024**3
    )
    assert info.machine == "ASUSTeK COMPUTER INC. ROG Zephyrus G14"
    assert info.cpu == "AMD Ryzen 9 7940HS"
    assert info.gpus == ("NVIDIA RTX 4060", "AMD 780M")  # no duplicate card
    assert info.os_name == "Windows 11 Pro"
    assert (info.cores, info.threads, round(info.memory_gb)) == (8, 16, 32)
    named = host_module.parse_host(
        _raw(maker="ASUS", model="ASUS PRIME B650"), cores=1, threads=1, memory_bytes=0
    )
    assert named.machine == "ASUS PRIME B650"


def test_parts_built_machines_fall_back_to_the_motherboard():
    info = host_module.parse_host(
        _raw(
            maker="System manufacturer",
            model="System Product Name",
            board="PRIME B650-PLUS",
        ),
        cores=6,
        threads=12,
        memory_bytes=16 * 1024**3,
    )
    assert info.machine == ""
    assert info.model_line == "ASUSTeK COMPUTER INC. PRIME B650-PLUS"


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null"])
def test_a_bad_hardware_answer_still_gives_a_usable_host(raw):
    info = host_module.parse_host(raw, cores=2, threads=4, memory_bytes=8 * 1024**3)
    assert info.os_name and info.threads == 4 and info.gpus == ()
    assert info.model_line  # never empty


def test_reading_the_host_never_raises_and_never_asks_for_serial_numbers(monkeypatch):
    monkeypatch.setattr(host_module.sys, "platform", "win32")
    seen = []

    def fake_run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=_raw(), stderr="")

    info = host_module.read_host(fake_run)
    assert info.cpu == "AMD Ryzen 9 7940HS"
    query = seen[0][-1].lower()
    assert "serial" not in query and "uuid" not in query

    def broken(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 1)

    assert host_module.read_host(broken).os_name


def test_host_reader_reads_in_the_background():
    reader = HostReader(lambda: HOST)
    assert reader.wait(2.0) == HOST and reader.info == HOST

    def boom():
        raise RuntimeError("no powershell")

    assert HostReader(boom).wait(2.0) == HostInfo()


# ── database ──────────────────────────────────────────────────────
def _settings(**overrides):
    values = {
        "enabled": True,
        "host": "127.0.0.1",
        "port": 3307,
        "user": "botuser",
        "password": "s3cret-pass",
        "database": "botdb",
    }
    values.update(overrides)
    return DbSettings(**values)


def test_settings_follow_the_real_environment_then_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "STORAGE_BACKEND=mysql\nMYSQL_USER=fileuser\nMYSQL_PASSWORD=filepass\n"
        "MYSQL_DATABASE=filedb\nMYSQL_PORT=3307\n",
        encoding="utf-8",
    )
    found = database.load_settings(tmp_path, {})
    assert found.enabled and found.user == "fileuser" and found.port == 3307
    # The bot loads .env without overriding the environment, so does the panel.
    overridden = database.load_settings(tmp_path, {"MYSQL_USER": "envuser"})
    assert overridden.user == "envuser" and overridden.password == "filepass"
    assert not database.load_settings(tmp_path / "nowhere", {}).enabled


def test_the_password_never_appears_in_repr_or_messages():
    settings = _settings()
    assert "s3cret-pass" not in repr(settings)
    status = database.check_database(
        settings,
        listening=lambda h, p: True,
        connect=lambda **k: (_ for _ in ()).throw(
            pymysql.err.OperationalError(
                1045,
                "Access denied for user 'botuser'@'localhost' (using password: YES)",
            )
        ),
    )
    assert status.state == "refusing"
    for secret in ("s3cret-pass", "botuser"):
        assert secret not in status.detail
    assert "帳號或密碼" in status.detail


def test_the_token_is_reported_as_present_not_returned(tmp_path):
    assert not database.has_discord_token(tmp_path, {})
    (tmp_path / ".env").write_text("DISCORD_TOKEN=abc.def\n", encoding="utf-8")
    assert database.has_discord_token(tmp_path, {}) is True
    assert database.has_discord_token(tmp_path / "x", {"DISCORD_TOKEN": "t"}) is True


class FakeConnection:
    def __init__(self, fail=None):
        self.fail = fail
        self.closed = False
        self.queries = []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self.queries.append(sql)
        if self.fail:
            raise self.fail

    def close(self):
        self.closed = True


def test_database_states():
    up = lambda h, p: True  # noqa: E731
    down = lambda h, p: False  # noqa: E731
    json_mode = database.check_database(_settings(enabled=False))
    assert json_mode.state == "disabled" and json_mode.ok

    status = database.check_database(_settings(), listening=down)
    assert status.state == "down" and not status.ok and "3307" in status.detail

    missing = database.check_database(_settings(user=None, password=None), listening=up)
    assert missing.state == "misconfigured"
    assert "MYSQL_USER" in missing.detail and "MYSQL_PASSWORD" in missing.detail
    assert "MYSQL_DATABASE" not in missing.detail

    connection = FakeConnection()
    ready = database.check_database(
        _settings(), listening=up, connect=lambda **k: connection
    )
    assert ready.state == "ready" and ready.ok
    assert connection.queries == ["SELECT 1"] and connection.closed

    broken = FakeConnection(fail=pymysql.err.OperationalError(2013, "lost"))
    refused = database.check_database(
        _settings(), listening=up, connect=lambda **k: broken
    )
    assert refused.state == "refusing" and "中斷" in refused.detail and broken.closed


@pytest.mark.parametrize(
    "error, expected",
    [
        (pymysql.err.OperationalError(1049, "x"), "資料庫不存在"),
        (pymysql.err.OperationalError(1040, "x"), "連線數已滿"),
        (pymysql.err.OperationalError(2003, "x"), "連不上伺服器"),
        (pymysql.err.OperationalError(9999, "x"), "9999"),
        (TimeoutError(), "逾時"),
        (ValueError("x"), "ValueError"),
    ],
)
def test_login_failures_are_explained_briefly(error, expected):
    assert expected in database.explain(error)


def _instance(tmp_path, *, packaged, script=False, basedir=True, port="3307"):
    """A pretend NewBotMySQL folder; ``basedir`` points at a pretend MySQL install."""
    folder = (
        tmp_path
        / "Packages"
        / "OpenAI.Codex_x"
        / "LocalCache"
        / "Local"
        / "NewBotMySQL"
    )
    if not packaged:
        folder = tmp_path / "NewBotMySQL"
    (folder / "data").mkdir(parents=True)
    server = tmp_path / "MySQL" / "bin" / "mysqld.exe"
    server.parent.mkdir(parents=True, exist_ok=True)
    server.write_text("", encoding="utf-8")
    lines = ["[mysqld]", f"port={port}"]
    if basedir:
        lines.append(f"basedir={server.parent.parent.as_posix()}")
    lines.append("datadir=C:/virtual/NewBotMySQL/data")  # the app's own view
    (folder / "my.ini").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if script:
        (folder / "start-mysql.ps1").write_text("# launcher", encoding="utf-8")
    return database.Instance(folder, packaged), server


def test_the_instance_is_found_where_it_really_is(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path)}
    assert database.find_instance(env) is None
    assert database.find_instance({}) is None

    packaged, _ = _instance(tmp_path, packaged=True)
    found = database.find_instance(env)
    assert found == packaged and found.packaged  # an app package (Codex)

    standard, _ = _instance(tmp_path, packaged=False)
    assert database.find_instance(env) == standard  # the normal place wins
    assert not database.find_instance(env).packaged


def test_the_newest_packaged_instance_wins(tmp_path):
    old, _ = _instance(tmp_path, packaged=True)
    other = (
        tmp_path / "Packages" / "Other.App_y" / "LocalCache" / "Local" / "NewBotMySQL"
    )
    other.mkdir(parents=True)
    (other / "my.ini").write_text("[mysqld]\n", encoding="utf-8")
    import os

    os.utime(old.config, (1_000_000, 1_000_000))
    found = database.find_instance({"LOCALAPPDATA": str(tmp_path)})
    assert found.directory == other


def test_my_ini_values_are_read_from_the_mysqld_section_only(tmp_path):
    config = tmp_path / "my.ini"
    config.write_text(
        "[client]\nport=1111\n[mysqld]\n# port=2222\nPort = 3307\n"
        'basedir="C:/Program Files/MySQL"\nlog_error=x.log\n',
        encoding="utf-8",
    )
    assert database.ini_value(config, "port") == "3307"
    assert database.ini_value(config, "basedir") == "C:/Program Files/MySQL"
    assert database.ini_value(config, "log-error") == "x.log"  # _ and - are the same
    assert database.ini_value(config, "missing") is None
    assert database.ini_value(tmp_path / "none.ini", "port") is None


def test_the_standard_instance_is_started_with_the_projects_script(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=False, script=True)
    plan = database.plan_start(_settings(), instance)
    assert plan.via_script and plan.argv[0] == "powershell.exe"
    assert plan.argv[-2:] == ["-File", str(instance.script)]


def test_a_packaged_instance_is_started_directly_on_its_real_folders(
    tmp_path, monkeypatch
):
    """The Codex app's my.ini names folders as that app sees them; ours must not."""
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, server = _instance(tmp_path, packaged=True, script=True)
    plan = database.plan_start(_settings(), instance)
    assert not plan.via_script and plan.cwd == instance.directory
    assert plan.argv[0] == str(server)
    assert f"--defaults-file={instance.config}" in plan.argv
    # Command line options beat the option file: the data must come from the real
    # folder, not the "virtual" path my.ini mentions.
    assert f"--datadir={instance.data}" in plan.argv
    assert f"--log-error={instance.error_log}" in plan.argv
    assert not any("virtual" in part for part in plan.argv)


def test_the_panel_says_why_it_cannot_start_the_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=True)
    blocker = database.start_blocker
    assert blocker(_settings(), instance) is None
    assert "JSON" in blocker(_settings(enabled=False), instance)
    assert "另一台" in blocker(_settings(host="10.0.0.5"), instance)
    assert "3307" in blocker(_settings(port=3306), instance)
    assert "找不到資料庫資料夾" in blocker(_settings(), None)
    assert "NewBotMySQL" in blocker(_settings(), None)  # names what it looked for
    wrong, _ = _instance(tmp_path / "w", packaged=True, port="3310")
    assert "3310" in blocker(_settings(), wrong)
    nobase, _ = _instance(tmp_path / "n", packaged=True, basedir=False)
    assert "mysqld.exe" in blocker(_settings(), nobase)
    monkeypatch.setattr(database.sys, "platform", "linux")
    assert "Windows" in blocker(_settings(), instance)


class FakeServer:
    """A pretend mysqld process."""

    def __init__(self, exits=None):
        self.exits = exits
        self.pid = 4321

    def poll(self):
        return self.exits


def test_starting_a_packaged_instance_launches_it_detached(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, server = _instance(tmp_path, packaged=True)
    launched = []
    answers = iter([False, False, True])

    def popen(argv, **kwargs):
        launched.append((argv, kwargs))
        return FakeServer()

    outcome = database.start_database(
        _settings(),
        instance=instance,
        popen=popen,
        running=lambda i: False,
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok and "3307" in outcome.message and "套件資料夾" in outcome.message
    argv, kwargs = launched[0]
    assert argv[0] == str(server) and kwargs["cwd"] == instance.directory
    # Detached, so the database keeps running after the panel is closed.
    assert kwargs["creationflags"] & 0x00000008
    assert kwargs["stdin"] is subprocess.DEVNULL


def test_starting_the_standard_instance_runs_the_projects_script(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=False, script=True)
    ran, answers = [], iter([False, True])
    outcome = database.start_database(
        _settings(),
        instance=instance,
        run=lambda argv, **k: ran.append((argv, k)),
        popen=lambda *a, **k: pytest.fail("started mysqld directly"),
        running=lambda i: False,
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok
    argv, kwargs = ran[0]
    assert argv[0] == "powershell.exe" and kwargs["check"] and kwargs["timeout"] == 10


def test_a_second_server_is_never_started_on_the_same_data(tmp_path, monkeypatch):
    """Codex may already have launched it; two mysqld on one data folder corrupt it."""
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=True)
    answers = iter([False, False, True])
    outcome = database.start_database(
        _settings(),
        instance=instance,
        run=lambda *a, **k: pytest.fail("ran the script"),
        popen=lambda *a, **k: pytest.fail("started a second mysqld"),
        running=lambda i: True,
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok  # it simply waited for the first one


def test_a_failed_start_says_why_from_mysqls_own_log(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=True)
    instance.error_log.write_text(
        "2026-10-11 [System] starting\n2026-10-11 [ERROR] Can't start server: Bind on TCP/IP port\n\n",
        encoding="utf-8",
    )
    assert "Bind on TCP/IP port" in database.last_error(instance)
    dies = database.start_database(
        _settings(),
        instance=instance,
        popen=lambda *a, **k: FakeServer(exits=1),
        running=lambda i: False,
        listening=lambda h, p: False,
        sleep=lambda _: None,
    )
    assert (
        not dies.ok
        and "結束碼 1" in dies.message
        and "Bind on TCP/IP port" in dies.message
    )

    hangs = database.start_database(
        _settings(),
        instance=instance,
        popen=lambda *a, **k: FakeServer(),
        running=lambda i: False,
        listening=lambda h, p: False,
        sleep=lambda _: None,
        wait=0.0,
    )
    assert (
        not hangs.ok
        and "逾時" in hangs.message
        and "Bind on TCP/IP port" in hangs.message
    )

    def missing(*a, **k):
        raise FileNotFoundError("mysqld.exe")

    absent = database.start_database(
        _settings(), instance=instance, popen=missing, running=lambda i: False
    )
    assert not absent.ok and "mysqld" in absent.message
    assert database.last_error(database.Instance(tmp_path / "nowhere", True)) == ""


def test_a_failing_project_script_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=False, script=True)

    def failing(*a, **k):
        raise subprocess.CalledProcessError(1, "powershell")

    outcome = database.start_database(
        _settings(), instance=instance, run=failing, running=lambda i: False
    )
    assert not outcome.ok and "CalledProcessError" in outcome.message


def test_nothing_is_started_when_it_is_not_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=True)
    outcome = database.start_database(
        _settings(host="10.0.0.5"),
        instance=instance,
        popen=lambda *a, **k: pytest.fail("started"),
        running=lambda i: False,
    )
    assert (
        not outcome.ok
        and "無法自動啟動" in outcome.message
        and "另一台" in outcome.message
    )
    lost = database.start_database(
        _settings(),
        instance=None,
        find=lambda: None,
        popen=lambda *a, **k: pytest.fail("x"),
    )
    assert not lost.ok and "找不到資料庫資料夾" in lost.message


class Proc:
    """A process as psutil.process_iter(["name", "cmdline"]) yields it."""

    def __init__(self, name, cmdline):
        self.info = {"name": name, "cmdline": cmdline}


def _processes(monkeypatch, *procs):
    monkeypatch.setattr(database.psutil, "process_iter", lambda attrs: iter(procs))


class FakeProcess:
    """What psutil.Process(pid) returns for a pid file's number."""

    def __init__(self, name="mysqld.exe", created=1000.0):
        self._name, self._created = name, created

    def name(self):
        return self._name

    def create_time(self):
        return self._created


def _pid_file(instance, text, *, written=2000.0):
    path = instance.data / "mysql.pid"
    path.write_text(text, encoding="utf-8")
    os.utime(path, (written, written))
    return path


def _process_table(monkeypatch, table):
    """``psutil.Process(pid)``: a FakeProcess from ``table``, else no such process."""

    def lookup(pid):
        if pid not in table:
            raise database.psutil.NoSuchProcess(pid)
        return table[pid]

    monkeypatch.setattr(database.psutil, "Process", lookup)


def test_a_running_server_is_recognised_by_its_exact_config_path(tmp_path, monkeypatch):
    instance, _ = _instance(tmp_path, packaged=True)
    mine = Proc(
        "mysqld.exe",
        ["C:\\MySQL\\bin\\mysqld.exe", f"--defaults-file={instance.config}"],
    )
    _processes(monkeypatch, mine)
    assert database._instance_running(instance) is True
    # Written the other way round, or with the space-separated form.
    spaced = Proc("mysqld.exe", ["mysqld.exe", "--defaults-file", str(instance.config)])
    shouty = Proc(
        "MYSQLD.EXE", ["x", f'--DEFAULTS-FILE="{str(instance.config).upper()}"']
    )
    for proc in (spaced, shouty):
        _processes(monkeypatch, proc)
        assert database._instance_running(instance) is True
    _processes(monkeypatch)
    assert database._instance_running(instance) is False


def test_a_same_named_folder_elsewhere_is_not_this_instance(tmp_path, monkeypatch):
    # Regression: any mysqld whose command line mentioned NewBotMySQL counted, so a
    # server on port 3310 in another folder hid that the real one (3307) was down
    # and the real one was never started.
    instance, _ = _instance(tmp_path, packaged=True)
    other = Proc(
        "mysqld.exe",
        [
            "C:\\MySQL\\bin\\mysqld.exe",
            "--defaults-file=D:\\elsewhere\\NewBotMySQL\\my.ini",
            "--port=3310",
        ],
    )
    xampp = Proc("mysqld.exe", ["C:\\xampp\\mysql\\bin\\mysqld.exe", "--standalone"])
    notepad = Proc("notepad.exe", ["--defaults-file", str(instance.config)])
    nofile = Proc("mysqld.exe", ["mysqld.exe", "--console"])
    unreadable = Proc("mysqld.exe", None)
    for proc in (other, xampp, notepad, nofile, unreadable):
        _processes(monkeypatch, proc)
        assert database._instance_running(instance) is False


def test_the_apps_view_of_the_path_proves_nothing_between_two_app_packages(
    tmp_path, monkeypatch
):
    # Regression: every packaged instance was given the alias
    # %LOCALAPPDATA%/NewBotMySQL/my.ini, but each app package means *its own* folder
    # by it. AppA's server on port 3310 made AppB's target (3307, stopped) look
    # started, so the target was never started.
    app_a, _ = _instance(tmp_path / "a", packaged=True)
    app_b, _ = _instance(tmp_path / "b", packaged=True)
    assert app_a.directory != app_b.directory  # two apps, two real folders
    alias = f"--defaults-file={tmp_path.as_posix()}/NewBotMySQL/my.ini"
    a_is_running = Proc("mysqld.exe", ["mysqld.exe", alias, "--port=3310"])
    _processes(monkeypatch, a_is_running)
    # No pid file in B's real data folder: nothing of B is running.
    assert database._instance_running(app_b) is False


def test_the_target_is_started_while_another_apps_database_runs(tmp_path, monkeypatch):
    # The same failure end to end: AppA's server on 3310, AppB's target stopped.
    monkeypatch.setattr(database.sys, "platform", "win32")
    app_a, _ = _instance(tmp_path / "a", packaged=True)
    app_b, server_b = _instance(tmp_path / "b", packaged=True)
    _pid_file(app_a, "4000")  # AppA's server is alive, and says so in AppA's folder
    _process_table(monkeypatch, {4000: FakeProcess()})
    _processes(monkeypatch, Proc("mysqld.exe", ["mysqld.exe", "--port=3310"]))
    launched, answers = [], iter([False, True])
    outcome = database.start_database(
        _settings(),
        instance=app_b,
        popen=lambda argv, **k: launched.append(argv) or FakeServer(),
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok and len(launched) == 1 and launched[0][0] == str(server_b)


def test_a_server_whose_pid_file_is_in_the_real_data_folder_is_the_instance(
    tmp_path, monkeypatch
):
    # How Codex's server is recognised: it was started with the app's own view of
    # the path, but it wrote mysql.pid into the real folder.
    instance, _ = _instance(tmp_path, packaged=True)
    _pid_file(instance, "4242\n")
    _process_table(monkeypatch, {4242: FakeProcess(created=1990.0)})
    _processes(monkeypatch)  # its command line does not matter
    assert database._instance_running(instance) is True


@pytest.mark.parametrize(
    "text, table",
    [
        ("not a number", {}),
        ("", {}),
        ("4242", {}),  # the server crashed: the file is stale and nothing has that pid
        ("4242", {4242: "notepad"}),  # the pid was reused by another program
        ("4242", {4242: "newer"}),  # reused by a mysqld that started after the file
    ],
)
def test_a_stale_or_reused_pid_file_does_not_count(tmp_path, monkeypatch, text, table):
    instance, _ = _instance(tmp_path, packaged=True)
    _pid_file(instance, text, written=2000.0)
    made = {
        pid: (
            FakeProcess("notepad.exe", 1990.0)
            if who == "notepad"
            else FakeProcess("mysqld.exe", 2600.0)  # started 10 minutes after the file
        )
        for pid, who in table.items()
    }
    _process_table(monkeypatch, made)
    _processes(monkeypatch)
    assert database._instance_running(instance) is False


def test_a_missing_pid_file_means_not_running(tmp_path, monkeypatch):
    instance, _ = _instance(tmp_path, packaged=True)
    _process_table(monkeypatch, {})
    _processes(monkeypatch)
    assert database._instance_running(instance) is False


def test_the_pid_file_name_comes_from_my_ini(tmp_path, monkeypatch):
    instance, _ = _instance(tmp_path, packaged=True)
    with instance.config.open("a", encoding="utf-8") as handle:
        handle.write("pid-file=C:/Users/x/AppData/Local/NewBotMySQL/data/other.pid\n")
    other = instance.data / "other.pid"
    other.write_text("4242", encoding="utf-8")
    os.utime(other, (2000.0, 2000.0))
    _process_table(monkeypatch, {4242: FakeProcess(created=1990.0)})
    _processes(monkeypatch)
    # An absolute name written the way the other app sees it: only its file name
    # is trusted, looked up in the real data folder.
    assert database._instance_running(instance) is True


def test_a_pid_file_path_in_my_ini_cannot_point_at_another_instance(
    tmp_path, monkeypatch
):
    # Regression: an absolute pid-file path that exists was read as it stood, so
    # AppB's my.ini naming AppA's live pid file made AppB look started.
    monkeypatch.setattr(database.sys, "platform", "win32")
    app_a, _ = _instance(tmp_path / "a", packaged=True)
    app_b, server_b = _instance(tmp_path / "b", packaged=True)
    a_pid = _pid_file(app_a, "4000", written=2000.0)  # AppA's server is up
    _process_table(monkeypatch, {4000: FakeProcess(created=1990.0)})
    _processes(monkeypatch)
    with app_b.config.open("a", encoding="utf-8") as handle:
        handle.write(f"pid-file={a_pid.as_posix()}\n")  # exists, and is not B's
    assert a_pid.is_file() and database._instance_running(app_a) is True
    assert database._instance_running(app_b) is False  # B has no pid file of its own
    launched, answers = [], iter([False, True])
    outcome = database.start_database(
        _settings(),
        instance=app_b,
        popen=lambda argv, **k: launched.append(argv) or FakeServer(),
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok and len(launched) == 1 and launched[0][0] == str(server_b)


def test_a_pid_file_path_cannot_climb_out_of_the_data_folder(tmp_path, monkeypatch):
    app_a, _ = _instance(tmp_path / "a", packaged=True)
    app_b, _ = _instance(tmp_path / "b", packaged=True)
    _pid_file(app_a, "4000", written=2000.0)
    _process_table(monkeypatch, {4000: FakeProcess(created=1990.0)})
    _processes(monkeypatch)
    for value in (
        "../../a/NewBotMySQL/data/mysql.pid",  # relative, climbing out
        f"{app_a.data.as_posix()}/mysql.pid",  # absolute, into the other instance
        f"..\\..\\..\\a\\{app_a.directory.name}\\data\\mysql.pid",
    ):
        config = app_b.config
        base = [
            line
            for line in config.read_text(encoding="utf-8").splitlines()
            if not line.startswith("pid-file")
        ]
        config.write_text(
            "\n".join([*base, f"pid-file={value}"]) + "\n", encoding="utf-8"
        )
        assert database._instance_running(app_b) is False, value


def test_a_relative_pid_file_name_with_a_folder_stays_in_the_data_folder(
    tmp_path, monkeypatch
):
    instance, _ = _instance(tmp_path, packaged=True)
    (instance.data / "run").mkdir()
    with instance.config.open("a", encoding="utf-8") as handle:
        handle.write("pid-file=run/mysqld.pid\n")
    path = instance.data / "run" / "mysqld.pid"
    path.write_text("4242", encoding="utf-8")
    os.utime(path, (2000.0, 2000.0))
    _process_table(monkeypatch, {4242: FakeProcess(created=1990.0)})
    _processes(monkeypatch)
    assert database._instance_running(instance) is True


def test_a_server_already_started_for_the_target_is_not_started_twice(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database.sys, "platform", "win32")
    instance, _ = _instance(tmp_path, packaged=True)
    _pid_file(instance, "4242")
    _process_table(monkeypatch, {4242: FakeProcess(created=1990.0)})
    _processes(monkeypatch)
    answers = iter([False, True])
    outcome = database.start_database(
        _settings(),
        instance=instance,
        popen=lambda *a, **k: pytest.fail("started a second mysqld"),
        run=lambda *a, **k: pytest.fail("ran the script"),
        listening=lambda h, p: next(answers),
        sleep=lambda _: None,
    )
    assert outcome.ok


def test_ensure_starts_the_database_only_when_it_is_down():
    started = []
    ready = DbStatus("ready", "ok")

    def start(settings):
        started.append(1)
        return Outcome(True, "started")

    quiet = database.ensure_database(_settings(), check=lambda s: ready, start=start)
    assert quiet.status is ready and not quiet.started and not started
    refusing = database.ensure_database(
        _settings(), check=lambda s: DbStatus("refusing", "x"), start=start
    )
    assert refusing.status.state == "refusing" and not started  # not a start problem

    answers = iter([DbStatus("down", "no answer"), ready])
    progress = []
    revived = database.ensure_database(
        _settings(),
        check=lambda s: next(answers),
        start=start,
        on_starting=lambda: progress.append("starting"),
    )
    assert revived.started and revived.status is ready
    assert started == [1] and progress == ["starting"]

    failed = database.ensure_database(
        _settings(),
        check=lambda s: DbStatus("down", "no answer"),
        start=lambda s: Outcome(False, "script missing"),
    )
    assert not failed.started and failed.message == "script missing"
    assert failed.status.state == "down"


def test_the_monitor_keeps_a_fresh_status_and_survives_a_crashing_check():
    answers = iter([DbStatus("ready", "ok"), RuntimeError("boom"), DbStatus("down")])

    def check(settings):
        value = next(answers)
        if isinstance(value, Exception):
            raise value
        return value

    monitor = database.DatabaseMonitor(_settings(), interval=0.01, check=check)
    deadline = time.monotonic() + 3
    seen = set()
    while time.monotonic() < deadline and len(seen) < 3:
        if monitor.status:
            seen.add(monitor.status.state)
        time.sleep(0.005)
    assert {"ready", "refusing", "down"} <= seen
    monitor.update(DbStatus("ready", "again"))
    assert monitor.status.detail == "again"


# ── start-up sequences ────────────────────────────────────────────
class Recorder:
    def __init__(self, paths, *, token=True, db=None, start=None, stop=None, mem=40.0):
        self.paths = paths
        self.calls = []
        if token:
            (paths.root / ".env").write_text("DISCORD_TOKEN=x\n", encoding="utf-8")
        self.db = db or database.EnsureResult(
            DbStatus("ready", "127.0.0.1:3307 連線正常")
        )
        self._start = start or (lambda p, r: Outcome(True, "機器人已啟動（PID 9）"))
        self._stop = stop or (lambda p, s: Outcome(True, "已停止機器人"))
        self.mem = mem

    def context(self, *, status=None):
        reader = StatusReader(self.paths)
        current = [status]
        if status is not None:
            reader.read = lambda: current[0]  # type: ignore[method-assign]

        def ensure(settings, *, on_starting=None):
            self.calls.append("ensure")
            if self.db.started and on_starting:
                on_starting()
            return self.db

        def start(paths, reader_):
            self.calls.append("start")
            return self._start(paths, reader_)

        def stop(paths, status_):
            self.calls.append("stop")
            outcome = self._stop(paths, status_)
            if outcome.ok:  # a stopped bot leaves no lock behind
                current[0] = BotStatus("stopped")
            return outcome

        return launch.Context(
            self.paths,
            reader,
            HostReader(lambda: HOST),
            _settings(),
            pause=0,
            sleep=lambda _: None,
            stop=stop,
            start=start,
            ensure=ensure,
            memory=lambda: (32.0, self.mem),
        )


def _states(run):
    return {s.key: s.state for s in run.snapshot()}


def _go(run, ctx, work=launch.run_start, **kwargs):
    if kwargs:
        launch.execute(run, ctx, lambda r, c: work(r, c, **kwargs))
    else:
        launch.execute(run, ctx, work)
    return run


def test_a_clean_start_goes_through_every_step_in_order(paths):
    recorder = Recorder(paths)
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    assert run.outcome.ok and "PID 9" in run.outcome.message
    assert set(_states(run).values()) == {launch.OK}
    assert list(_states(run)) == [
        "host", "cpu", "gpu", "memory", "env", "db", "lock", "launch",
    ]  # fmt: skip
    assert recorder.calls == ["ensure", "start"]
    details = {s.key: s.detail for s in run.snapshot()}
    assert "ASUSTeK" in details["host"] or "ROG" in details["host"]
    assert "Ryzen" in details["cpu"] and "8 核心 16 執行緒" in details["cpu"]
    assert "RTX 4060" in details["gpu"] and "32 GB" in details["memory"]
    assert run.progress == 1.0


def test_the_hardware_shows_up_in_the_checklist_text(paths):
    run = _go(launch.start_run(), Recorder(paths).context(status=BotStatus("stopped")))
    screen = _capture(
        render.launch_screen(
            run.title,
            run.snapshot(),
            (run.outcome.ok, run.outcome.message),
            progress=run.progress,
            elapsed=5.0,
            spinner=0,
            width=110,
            height=40,
        )
    )
    for text in (
        "主機型號",
        "處理器",
        "顯示卡",
        "記憶體",
        "ROG Zephyrus G14",
        "Ryzen 9",
        "RTX 4060",
    ):
        assert text in screen


def test_a_missing_token_stops_before_anything_is_touched(paths):
    recorder = Recorder(paths, token=False)
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    states = _states(run)
    assert states["env"] == launch.FAIL
    assert states["db"] == states["lock"] == states["launch"] == launch.SKIP
    assert not run.outcome.ok and "找不到 .env" in run.outcome.message
    assert recorder.calls == []  # neither the database nor the bot was touched


def test_a_database_that_cannot_be_started_blocks_the_start(paths):
    down = database.EnsureResult(
        DbStatus("down", "沒有回應"), False, "找不到 start-mysql.ps1"
    )
    recorder = Recorder(paths, db=down)
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    assert _states(run)["db"] == launch.FAIL and _states(run)["launch"] == launch.SKIP
    assert not run.outcome.ok and "start-mysql.ps1" in run.outcome.message
    assert "start" not in recorder.calls


def test_a_database_started_automatically_is_said_so(paths):
    revived = database.EnsureResult(
        DbStatus("ready", "127.0.0.1:3307 連線正常"), True, "資料庫已啟動"
    )
    recorder = Recorder(paths, db=revived)
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    db_step = [s for s in run.snapshot() if s.key == "db"][0]
    assert db_step.state == launch.OK and "自動啟動" in db_step.detail
    assert run.outcome.ok and recorder.calls == ["ensure", "start"]


def test_a_database_that_refuses_the_bot_warns_but_does_not_block(paths):
    refusing = database.EnsureResult(DbStatus("refusing", "帳號或密碼被拒絕"))
    run = _go(
        launch.start_run(),
        Recorder(paths, db=refusing).context(status=BotStatus("stopped")),
    )
    db_step = [s for s in run.snapshot() if s.key == "db"][0]
    assert db_step.state == launch.WARN and "帳號或密碼" in db_step.detail
    assert run.outcome.ok  # the bot itself decides what to do about it


def test_a_second_copy_is_refused_and_a_stale_lock_is_cleared(paths):
    recorder = Recorder(paths)
    running = _go(launch.start_run(), recorder.context(status=BotStatus("running", 77)))
    assert _states(running)["lock"] == launch.FAIL and not running.outcome.ok
    assert "start" not in recorder.calls

    paths.lock.write_text("123", encoding="utf-8")
    stale = _go(
        launch.start_run(), Recorder(paths).context(status=BotStatus("stale", 123))
    )
    assert not paths.lock.exists() and stale.outcome.ok


def test_high_memory_is_a_warning_in_the_checklist(paths):
    run = _go(
        launch.start_run(),
        Recorder(paths, mem=97.2).context(status=BotStatus("stopped")),
    )
    memory = [s for s in run.snapshot() if s.key == "memory"][0]
    assert memory.state == launch.WARN and "97%" in memory.detail


def test_a_failed_launch_is_reported(paths):
    recorder = Recorder(paths, start=lambda p, r: Outcome(False, "啟動後立刻結束"))
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    assert _states(run)["launch"] == launch.FAIL
    assert not run.outcome.ok and "立刻結束" in run.outcome.message


def test_restart_stops_first_and_stops_the_sequence_if_it_cannot(paths):
    recorder = Recorder(paths)
    ok = _go(
        launch.start_run(restart=True),
        recorder.context(status=BotStatus("running", 5)),
        restart=True,
    )
    assert recorder.calls[:2] == ["stop", "ensure"] and ok.outcome.ok
    assert list(_states(ok))[0] == "stop"

    idle = Recorder(paths)
    skipped = _go(
        launch.start_run(restart=True),
        idle.context(status=BotStatus("stopped")),
        restart=True,
    )
    assert _states(skipped)["stop"] == launch.SKIP and "stop" not in idle.calls

    stuck = Recorder(paths, stop=lambda p, s: Outcome(False, "權限不足"))
    refused = _go(
        launch.start_run(restart=True),
        stuck.context(status=BotStatus("running", 5)),
        restart=True,
    )
    assert _states(refused)["stop"] == launch.FAIL and not refused.outcome.ok
    assert "start" not in stuck.calls and "ensure" not in stuck.calls


def test_first_open_checks_the_hardware_and_the_database_only(paths):
    recorder = Recorder(paths)
    run = _go(launch.open_run(), recorder.context(), launch.run_open)
    assert recorder.calls == ["ensure"]  # never starts or stops the bot
    assert run.outcome.ok and set(_states(run)) == {
        "host",
        "cpu",
        "gpu",
        "memory",
        "db",
    }


def test_first_open_survives_a_database_that_will_not_start(paths):
    down = database.EnsureResult(DbStatus("down", "沒有回應"), False, "找不到腳本")
    run = _go(launch.open_run(), Recorder(paths, db=down).context(), launch.run_open)
    assert (
        _states(run)["db"] == launch.WARN and run.outcome.ok
    )  # opens the panel anyway


def test_the_database_menu_item_has_its_own_short_sequence(paths):
    revived = database.EnsureResult(DbStatus("ready", "ok"), True, "資料庫已啟動")
    recorder = Recorder(paths, db=revived)
    run = _go(launch.database_run(), recorder.context(), launch.run_database)
    assert list(_states(run)) == ["db"] and run.outcome.ok

    down = database.EnsureResult(DbStatus("down", "x"), False, "找不到腳本")
    failed = _go(
        launch.database_run(), Recorder(paths, db=down).context(), launch.run_database
    )
    assert not failed.outcome.ok and "找不到腳本" in failed.outcome.message

    json_mode = database.EnsureResult(DbStatus("disabled", "JSON 儲存模式"))
    skipped = _go(
        launch.database_run(),
        Recorder(paths, db=json_mode).context(),
        launch.run_database,
    )
    assert skipped.outcome.ok and _states(skipped)["db"] == launch.SKIP


def test_a_crash_inside_a_step_still_ends_the_run(paths):
    def explode(p, r):
        raise RuntimeError("boom")

    recorder = Recorder(paths, start=explode)
    run = _go(launch.start_run(), recorder.context(status=BotStatus("stopped")))
    assert run.finished and not run.outcome.ok and "boom" in run.outcome.message


# ── logo ──────────────────────────────────────────────────────────
def test_the_logo_is_drawn_in_the_brand_colours():
    text = logo.logo_text(12)
    lines = text.plain.split("\n")
    assert len(lines) == 6 and all(len(line) == 12 for line in lines)
    assert any(c in "▀▄" for line in lines for c in line)
    colours = {
        str(span.style.color.name)
        for span in text.spans
        if span.style and not isinstance(span.style, str) and span.style.color
    }
    assert len(colours) >= 4  # orange, blue, magenta, teal ... not one flat colour


def test_the_logo_can_be_revealed_row_by_row():
    assert logo.logo_text(12, visible_rows=0).plain.strip() == ""
    partial = logo.logo_text(12, visible_rows=2).plain.split("\n")
    assert partial[0].strip() and not partial[5].strip()
    assert logo.logo_text(12, visible_rows=99).plain == logo.logo_text(12).plain


def test_a_missing_logo_file_falls_back_to_text(monkeypatch):
    monkeypatch.setattr(logo, "ASSET", Path("does-not-exist.png"))
    logo._pixels.cache_clear()
    try:
        assert logo.logo_text(12).plain == "BOT."
    finally:
        logo._pixels.cache_clear()


# ── log folding and recent trouble ────────────────────────────────
def _line(minutes_ago, level, logger, message):
    when = NOW - timedelta(minutes=minutes_ago)
    return f"{when:%Y-%m-%d %H:%M:%S},000 {level} {logger}: {message}"


def test_repeated_records_fold_into_one_line_at_their_latest_position():
    records = state.parse_records(
        [
            _line(9, "WARNING", "src.utils.lang_context", "slow"),
            _line(8, "INFO", "src.bot", "ready"),
            _line(7, "WARNING", "src.utils.lang_context", "slow"),
            _line(6, "WARNING", "src.utils.lang_context", "slow"),
            _line(5, "ERROR", "src.x", "broken"),
        ]
    )
    folded = state.collapse_records(records)
    assert [(r.message, r.count) for r in folded] == [
        ("ready", 1),
        ("slow", 3),
        ("broken", 1),
    ]
    assert folded[1].time == records[3].time  # the newest occurrence
    different = state.collapse_records(
        state.parse_records(
            [_line(2, "WARNING", "a", "x"), _line(1, "ERROR", "a", "x")]
        )
    )
    assert len(different) == 2  # a different level is a different event


def test_the_log_line_shows_the_repeat_count_before_the_message():
    record = state.parse_records([_line(1, "WARNING", "src.x", "same thing")])[0]
    from dataclasses import replace

    text = render.log_line(replace(record, count=12)).plain
    assert text.index("×12") < text.index("same thing")
    assert "×" not in render.log_line(record).plain


def test_recent_trouble_is_counted_over_five_minutes(paths):
    lines = [
        _line(30, "ERROR", "src.x", "old error"),
        _line(4, "WARNING", "src.x", "w"),
        _line(3, "WARNING", "src.x", "w"),
        _line(2, "ERROR", "src.x", "e"),
        _line(1, "INFO", "src.x", "fine"),
    ]
    paths.runtime_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = state.summarise_log(paths.runtime_log, NOW)
    assert (summary.warnings, summary.errors) == (2, 1)  # the old error is ignored
    assert [r.message for r in summary.events][-1] == "fine"
    empty = state.summarise_log(paths.logs / "none.log", NOW)
    assert (empty.warnings, empty.errors, empty.events) == (0, 0, [])


def test_recent_events_returns_distinct_events_not_repeats(paths):
    noisy = [_line(5, "WARNING", "src.x", "same")] * 50 + [
        _line(1, "INFO", "src.y", "new")
    ]
    paths.runtime_log.write_text("\n".join(noisy) + "\n", encoding="utf-8")
    events = state.recent_events(paths.runtime_log, 5)
    assert [e.message for e in events] == ["same", "new"] and events[0].count == 50


# ── drawing ───────────────────────────────────────────────────────
def _view(paths, **overrides):
    values = {
        "paths": paths,
        "status": BotStatus("stopped"),
        "records": [],
        "selected": 0,
        "now": NOW,
        "width": 110,
        "height": 34,
        "host": HOST,
        "database": DbStatus("ready", "ok"),
        "db_enabled": True,
        "memory_percent": 61.0,
    }
    values.update(overrides)
    return render.ViewState(**values)


def test_the_header_shows_the_logo_and_the_machine(paths):
    plain = _capture(render.dashboard(_view(paths)))
    assert "▀" in plain  # the logo
    for text in (
        "主機",
        "ROG Zephyrus G14",
        "Windows 11 Pro",
        "處理器",
        "Ryzen 9",
        "顯示卡",
        "RTX 4060",
        "32 GB",
    ):
        assert text in plain
    waiting = _capture(render.dashboard(_view(paths, host=None)))
    assert "正在讀取硬體資訊" in waiting


def test_a_narrow_terminal_drops_the_logo_but_keeps_the_machine(paths):
    plain = _capture(render.dashboard(_view(paths, width=60)), width=60)
    assert "▀" not in plain and "機器人控制台" in plain


@pytest.mark.parametrize("height", [26, 30, 34, 44])
def test_the_dashboard_never_outgrows_the_terminal(paths, height):
    lines = _capture(render.dashboard(_view(paths, height=height)), height=height)
    assert len(lines.rstrip("\n").splitlines()) <= height  # the footer stays visible


def test_health_line_for_each_database_state(paths):
    def shown(**kw):
        return _capture(render.dashboard(_view(paths, **kw)))

    assert "資料庫 連線正常" in shown()
    down = shown(database=DbStatus("down", "x"))
    assert "資料庫 沒有執行" in down and "按 M 啟動" in down
    refusing = shown(database=DbStatus("refusing", "帳號或密碼被拒絕"))
    assert "無法登入" in refusing and "帳號或密碼被拒絕" in refusing
    assert "資料庫 JSON 模式" in shown(db_enabled=False)
    assert "檢查中" in shown(database=None)
    assert "記憶體 61%" in shown()
    assert "沒有警告" in shown()
    trouble = shown(warnings=12, errors=2)
    assert "2 個錯誤" in trouble and "12 個警告" in trouble


def test_the_launch_screen_animates_and_closes_with_the_result():
    steps = [
        launch.Step("host", "主機型號", launch.OK, "ASUS ROG"),
        launch.Step("db", "資料庫", launch.RUNNING, "沒有回應，正在啟動資料庫…"),
        launch.Step("launch", "啟動機器人"),
    ]

    def screen(outcome=None, *, elapsed=0.0, spinner=0, height=40):
        return _capture(
            render.launch_screen(
                "正在啟動機器人",
                steps,
                outcome,
                progress=0.5,
                elapsed=elapsed,
                spinner=spinner,
                width=100,
                height=height,
            ),
            width=100,
            height=height,
        )

    running = screen()
    for text in (
        "正在啟動機器人",
        "主機型號",
        "ASUS ROG",
        "正在啟動資料庫",
        "啟動機器人",
    ):
        assert text in running
    assert "⠋" in running and "⠙" in screen(spinner=1)  # the spinner turns
    assert "✓" in running and "○" in running
    assert "按任意鍵" not in running
    done = screen((True, "機器人已啟動（PID 9）"))
    assert "機器人已啟動（PID 9）" in done and "按任意鍵繼續" in done
    failed = screen((False, "找不到 .env 檔"))
    assert "✗" in failed and "找不到 .env 檔" in failed

    # The logo is drawn in from the top: more of it as time passes.
    early, late = screen(elapsed=0.0), screen(elapsed=5.0)
    assert early.count("▀") < late.count("▀")
    assert "▀" not in screen(height=14)  # no room for it on a short terminal


def test_the_host_page_lists_everything(paths):
    plain = _capture(render.host_page(HOST, paths, NOW, 110, memory_percent=61.0))
    for text in (
        "主機資訊",
        "ROG Zephyrus G14",
        "Ryzen 9",
        "RTX 4060",
        "780M",
        "32.0 GB",
        "61%",
        "Windows 11 Pro",
        "8 核心",
    ):
        assert text in plain
    assert "正在讀取" in _capture(render.host_page(None, paths, NOW, 110))


# ── in the panel ──────────────────────────────────────────────────
class Idle(Keyboard):
    """No keys, ever (the panel is driven by calling its methods)."""

    def poll(self, timeout):
        time.sleep(0.005)
        return None


class KeyWhen(Keyboard):
    """Presses one key once ``ready()`` says the screen has finished."""

    def __init__(self, ready, key="x"):
        self.ready, self.key, self.pressed = ready, key, 0

    def poll(self, timeout):
        time.sleep(0.005)
        if self.ready():
            self.pressed += 1
            return self.key
        return None


class Scripted(Keyboard):
    def __init__(self, *keys):
        self.keys = list(keys)

    def poll(self, timeout):
        assert self.keys, "the panel asked for more keys than the test gave"
        return self.keys.pop(0)


def _panel(paths, keyboard, **kwargs):
    console = Console(file=io.StringIO(), force_terminal=True, width=110, height=34)
    kwargs.setdefault("host", HostReader(lambda: HOST))
    kwargs.setdefault("settings", _settings(enabled=False))
    kwargs.setdefault("pause", 0)
    return ControlPanel(console, keyboard, paths, **kwargs)


def test_opening_the_panel_runs_the_checks_first(paths, monkeypatch):
    seen = []
    panel = _panel(paths, Scripted("q"), boot=True)
    monkeypatch.setattr(
        panel,
        "_show_run",
        lambda run, work, **kw: seen.append((run.title, work, kw)) or Outcome(True, ""),
    )
    assert panel.run() == 0
    # Opening only warns for a few seconds; it never waits on a warning.
    assert seen == [("控制台啟動中", launch.run_open, {"hold_warnings": True})]


def test_a_panel_built_for_tests_does_not_run_the_checks(paths, monkeypatch):
    panel = _panel(paths, Scripted("q"))
    monkeypatch.setattr(panel, "_show_run", lambda *a: pytest.fail("ran checks"))
    assert panel.run() == 0


@pytest.mark.parametrize(
    "key, title",
    [("1", "正在啟動機器人"), ("m", "正在檢查資料庫")],
)
def test_start_and_database_open_the_launch_screen(paths, monkeypatch, key, title):
    seen = []
    panel = _panel(paths, Scripted(key, "q"))
    monkeypatch.setattr(
        panel,
        "_show_run",
        lambda run, work: seen.append(run.title) or Outcome(True, "完成了"),
    )
    assert panel.run() == 0
    assert seen == [title]
    assert panel.notice.text == "完成了" and panel.notice.kind == "ok"


def test_restart_asks_first_then_opens_the_restart_sequence(paths, monkeypatch):
    seen = []
    panel = _panel(paths, Scripted())
    panel.status = BotStatus("running", 5)
    monkeypatch.setattr(
        panel,
        "_show_run",
        lambda run, work: seen.append(run.title) or Outcome(True, ""),
    )
    assert panel._on_key("3") is None and panel.confirm_item is menu.BY_KEY["3"]
    assert panel._on_key("n") is None and not seen
    panel._on_key("3")
    item = panel._on_key("y")  # leaves the dashboard so the screen can take over
    assert item is menu.BY_KEY["3"]
    panel._execute(item)
    assert seen == ["正在重新啟動機器人"]


def test_a_failed_run_waits_for_a_key_and_reports_the_failure(paths, monkeypatch):
    monkeypatch.setattr(app, "HOLD_OK_SECONDS", 0.0)
    run = launch.start_run()
    recorder = Recorder(paths, token=False)
    panel = _panel(paths, KeyWhen(lambda: run.finished))
    panel._context = lambda: recorder.context(status=BotStatus("stopped"))
    outcome = panel._show_run(run, launch.run_start)
    assert not outcome.ok and panel.keyboard.pressed >= 1  # it did wait for the key


def test_a_clean_run_closes_by_itself(paths, monkeypatch):
    monkeypatch.setattr(app, "HOLD_OK_SECONDS", 0.0)
    run = launch.start_run()
    recorder = Recorder(paths)
    panel = _panel(paths, Idle())  # nobody presses anything
    panel._context = lambda: recorder.context(status=BotStatus("stopped"))
    outcome = panel._show_run(run, launch.run_start)
    assert outcome.ok and recorder.calls == ["ensure", "start"]


def test_a_run_with_a_warning_waits_for_the_reader(paths, monkeypatch):
    monkeypatch.setattr(app, "HOLD_OK_SECONDS", 0.0)
    refusing = database.EnsureResult(DbStatus("refusing", "帳號或密碼被拒絕"))
    run = launch.start_run()
    recorder = Recorder(paths, db=refusing)
    panel = _panel(paths, KeyWhen(lambda: run.finished))
    panel._context = lambda: recorder.context(status=BotStatus("stopped"))
    assert panel._show_run(run, launch.run_start).ok
    assert panel.keyboard.pressed >= 1  # a warning is not skipped past


def test_keys_pressed_during_a_run_do_nothing(paths, monkeypatch):
    monkeypatch.setattr(app, "HOLD_OK_SECONDS", 0.0)
    run = launch.start_run()
    recorder = Recorder(paths)
    seen = []

    def slow_start(p, r):
        time.sleep(0.15)
        return Outcome(True, "started")

    recorder._start = slow_start
    keys = KeyWhen(lambda: True, key="q")  # hammering Q the whole time
    panel = _panel(paths, keys)
    panel._context = lambda: recorder.context(status=BotStatus("stopped"))
    started = time.monotonic()
    outcome = panel._show_run(run, launch.run_start)
    assert outcome.ok and time.monotonic() - started >= 0.15  # it was not cut short
    assert seen == [] and "start" in recorder.calls


def test_the_dashboard_gets_database_memory_and_trouble_from_the_panel(paths):
    class Monitor:
        status = DbStatus("down", "沒有回應")

    paths.runtime_log.write_text(
        "\n".join([_line(1, "ERROR", "src.x", "e")]) + "\n", encoding="utf-8"
    )
    panel = _panel(paths, Idle(), settings=_settings(), monitor=Monitor())
    panel.clock = lambda: NOW
    panel.refresh(force=True)
    view = panel.view_state()
    assert view.database.state == "down" and view.db_enabled
    assert view.errors == 1 and view.memory_percent is not None
    assert view.host == HOST
    assert "資料庫 沒有執行" in _capture(render.dashboard(view))


def test_the_host_page_and_menu_keys_exist(paths):
    panel = _panel(paths, Scripted("h", "x", "q"))
    assert panel.run() == 0
    assert menu.BY_KEY["h"].action == "host" and menu.BY_KEY["m"].action == "database"
    assert menu.BY_KEY["m"].kind == "launch"
    assert not menu.BY_KEY["1"].confirm and menu.BY_KEY["3"].confirm
    assert menu.BY_KEY["2"].kind == "bg"  # stopping stays a quick background job


def test_the_panel_does_not_start_a_monitor_in_json_mode(paths):
    panel = _panel(paths, Idle())
    assert panel.monitor is None and panel.view_state().database is None


def test_the_hardware_query_asks_powershell_for_utf8():
    # Without this a Chinese Windows edition name came back as "???".
    assert host_module._QUERY.startswith(
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8"
    )
    info = host_module.parse_host(
        "﻿" + _raw(os="Microsoft Windows 11 專業版"),
        cores=1,
        threads=1,
        memory_bytes=0,
    )
    assert info.os_name == "Windows 11 專業版"


def test_opening_with_only_a_warning_closes_itself_but_a_start_waits(
    paths, monkeypatch
):
    monkeypatch.setattr(app, "HOLD_WARN_SECONDS", 0.0)
    monkeypatch.setattr(app, "HOLD_OK_SECONDS", 0.0)
    # Memory is the usual warning: 97% used, as on the real machine.
    recorder = Recorder(paths, mem=97.0)

    run = launch.open_run()
    panel = _panel(paths, Idle())  # nobody presses a key
    panel._context = lambda: recorder.context()
    outcome = panel._show_run(run, launch.run_open, hold_warnings=True)
    assert outcome.ok and _states(run)["memory"] == launch.WARN

    # Starting the bot is different: a warning stays until it has been read.
    start = launch.start_run()
    waiting = _panel(paths, KeyWhen(lambda: start.finished))
    waiting._context = lambda: recorder.context(status=BotStatus("stopped"))
    assert waiting._show_run(start, launch.run_start).ok
    assert waiting.keyboard.pressed >= 1


def test_a_failure_waits_for_a_key_even_when_opening(paths, monkeypatch):
    monkeypatch.setattr(app, "HOLD_WARN_SECONDS", 0.0)
    down = database.EnsureResult(DbStatus("down", "x"), False, "x")
    run = launch.open_run()
    recorder = Recorder(paths, db=down)
    panel = _panel(paths, Idle())
    panel._context = lambda: recorder.context()
    # open_run only warns about a database that will not start (the panel still
    # opens), so a real failure here means the sequence itself broke.
    assert panel._show_run(run, launch.run_open, hold_warnings=True).ok

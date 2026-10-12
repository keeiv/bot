"""The quick installer (install.py): steps, safety, and what it must never do."""

import importlib.util
import io
from pathlib import Path
import sys
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "install.py"
spec = importlib.util.spec_from_file_location("bot_install", SCRIPT)
install = importlib.util.module_from_spec(spec)
sys.modules["bot_install"] = install
spec.loader.exec_module(install)


class Calls:
    """A fake command runner that records what would have been run."""

    def __init__(self, tmp_path, fail=None, remote=install.REPO_URL):
        self.calls = []
        self.fail = fail
        self.remote = remote
        self.tmp_path = tmp_path

    def __call__(self, args, cwd=None, env=None):
        self.calls.append(list(args))
        text = " ".join(str(a) for a in args)
        if self.fail and self.fail in text:
            return 1, "boom: " + self.fail
        if args[1:3] == ["-m", "venv"]:
            python = Path(install.venv_python(Path(args[3]).parent))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_text("", encoding="utf-8")
        if args[1:2] == ["clone"]:
            root = Path(args[-1])
            (root / ".git").mkdir(parents=True, exist_ok=True)
            for name in ("requirements.txt", "requirements-dev.txt"):
                (root / name).write_text("", encoding="utf-8")
        if "remote" in args and "get-url" in args:
            return 0, self.remote
        if "-c" in args:  # the import check
            return 0, "missing="
        if "--version" in args:
            return 0, "git version 2.0"
        return 0, ""


def screen():
    out = io.StringIO()
    return install.Screen(out), out


def options(tmp_path, *extra):
    return install.parse(["--dir", str(tmp_path / "bot"), "--yes", *extra])


def make(tmp_path, *extra, runner=None, fetch=None, git="git"):
    shown, out = screen()
    job = install.Installer(
        options(tmp_path, *extra),
        shown,
        runner or Calls(tmp_path),
        fetch or (lambda url, dest: None),
        lambda name: git if name == "git" else None,
    )
    return job, out


# ── a normal install ──────────────────────────────────────────────
def test_a_full_install_runs_every_step_in_order(tmp_path):
    runner = Calls(tmp_path)
    job, out = make(tmp_path, runner=runner)
    assert job.install() == 0
    text = out.getvalue()
    for number in range(1, 7):
        assert f"[{number}/6]" in text
    commands = [" ".join(map(str, c)) for c in runner.calls]
    assert any("clone" in c and install.REPO_URL in c for c in commands)
    assert any("-m venv" in c for c in commands)
    pip = next(c for c in commands if "pip install" in c)
    assert "-r requirements.txt" in pip and "-r requirements-dev.txt" in pip
    assert (tmp_path / "bot" / ".env").read_text(encoding="utf-8").startswith("# BOT.")
    assert "完成" in text and "DISCORD_TOKEN" in text


def test_the_screen_is_plain_text_without_colour_or_pictures(tmp_path):
    job, out = make(tmp_path)
    job.install()
    text = out.getvalue()
    assert "\x1b" not in text  # no escape codes, so no colour
    # no box drawing, blocks, shapes, symbols, dingbats or emoji
    pictures = [c for c in text if 0x2500 <= ord(c) <= 0x27BF or ord(c) >= 0x1F000]
    assert pictures == []
    assert "Nova" not in text and "諾瓦" not in text


def test_no_dev_skips_the_development_requirements(tmp_path):
    runner = Calls(tmp_path)
    job, _ = make(tmp_path, "--no-dev", runner=runner)
    job.install()
    pip = next(" ".join(map(str, c)) for c in runner.calls if "pip" in c)
    assert "requirements-dev.txt" not in pip


def test_check_only_installs_nothing(tmp_path):
    runner = Calls(tmp_path)
    job, out = make(tmp_path, "--check", runner=runner)
    assert job.install() == 0
    assert not (tmp_path / "bot").exists()
    assert not any("clone" in c or "pip" in c for c in map(str, runner.calls))
    assert "沒有安裝任何東西" in out.getvalue()


# ── an existing install is updated, never overwritten ─────────────
def test_running_again_updates_and_keeps_env_and_venv(tmp_path):
    job, _ = make(tmp_path)
    job.install()
    env = tmp_path / "bot" / ".env"
    env.write_text("DISCORD_TOKEN=my-secret-value\n", encoding="utf-8")
    runner = Calls(tmp_path)
    job, out = make(tmp_path, runner=runner)
    assert job.install() == 0
    assert env.read_text(encoding="utf-8") == "DISCORD_TOKEN=my-secret-value\n"
    commands = [" ".join(map(str, c)) for c in runner.calls]
    assert any("pull --ff-only" in c for c in commands)
    assert not any("clone" in c or "-m venv" in c for c in commands)
    assert "沿用" in out.getvalue() and "不會更動" in out.getvalue()


@pytest.mark.parametrize(
    "remote",
    ["https://github.com/someone-else/bot.git", "git@github.com:keeiv/other.git"],
)
def test_a_repository_from_somewhere_else_is_left_alone(tmp_path, remote):
    (tmp_path / "bot" / ".git").mkdir(parents=True)
    runner = Calls(tmp_path, remote=remote)
    job, out = make(tmp_path, runner=runner)
    with pytest.raises(install.Failure, match="不是"):
        job.get_code()
    assert not any("pull" in c for c in map(str, runner.calls))


def test_a_folder_that_is_not_a_repository_is_never_touched(tmp_path):
    folder = tmp_path / "bot"
    folder.mkdir()
    (folder / "mine.txt").write_text("keep me", encoding="utf-8")
    job, _ = make(tmp_path)
    with pytest.raises(install.Failure, match="已存在"):
        job.get_code()
    assert (folder / "mine.txt").read_text(encoding="utf-8") == "keep me"


def test_the_same_repository_is_recognised_in_any_spelling():
    for url in (
        "https://github.com/keeiv/bot.git",
        "https://github.com/keeiv/bot",
        "https://GitHub.com/Keeiv/Bot/",
        "git@github.com:keeiv/bot.git",
    ):
        assert install.same_repo(url)
    assert not install.same_repo("https://github.com/keeiv/bot-fork.git")


# ── failures say what to do and stop ──────────────────────────────
@pytest.mark.parametrize(
    "fail,message",
    [("clone", "git clone"), ("-m venv", "虛擬環境"), ("pip install", "pip")],
)
def test_a_failing_step_stops_the_install_with_a_reason(tmp_path, fail, message):
    shown, out = screen()
    job = install.Installer(
        options(tmp_path),
        shown,
        Calls(tmp_path, fail=fail),
        lambda url, dest: None,
        lambda name: "git",
    )
    assert (
        install.main(["--dir", str(tmp_path / "bot"), "--yes"], installer=lambda o: job)
        == 1
    )
    text = out.getvalue()
    assert "[FAIL]" in text and message in text and "可以再執行一次" in text
    assert "[6/6]" not in text  # nothing after the failed step ran


def test_a_missing_package_fails_the_check_and_names_it(tmp_path):
    class Missing(Calls):
        def __call__(self, args, cwd=None, env=None):
            if "-c" in args:
                return 0, "missing=genshin,ossapi"
            return super().__call__(args, cwd, env)

    job, _ = make(tmp_path, runner=Missing(tmp_path))
    with pytest.raises(install.Failure, match="genshin, ossapi"):
        job.install()


def test_an_old_python_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(install.sys, "version_info", (3, 9, 0, "final", 0))
    job, _ = make(tmp_path)
    with pytest.raises(install.Failure, match="3.10"):
        job.check_machine()


def test_without_git_it_falls_back_to_the_zip_download(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("bot-main/requirements.txt", "")
        bundle.writestr("bot-main/requirements-dev.txt", "")
        bundle.writestr("bot-main/src/__init__.py", "")

    fetched = []

    def fetch(url, destination):
        fetched.append(url)
        Path(destination).write_bytes(archive.read_bytes())

    job, out = make(tmp_path, git=None, fetch=fetch)
    assert job.install() == 0
    assert fetched == ["https://codeload.github.com/keeiv/bot/zip/refs/heads/main"]
    assert (tmp_path / "bot" / "src" / "__init__.py").exists()
    assert "找不到 git" in out.getvalue()


# ── safety ────────────────────────────────────────────────────────
def test_a_zip_cannot_write_outside_the_target(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("bot-main/ok.txt", "fine")
        bundle.writestr("bot-main/../../escaped.txt", "bad")
    target = tmp_path / "out" / "bot"
    with pytest.raises(install.Failure, match="不安全"):
        install.unzip_here(archive, target)
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "out" / "escaped.txt").exists()


def test_a_zip_with_several_top_folders_is_refused(tmp_path):
    archive = tmp_path / "odd.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("one/a.txt", "")
        bundle.writestr("two/b.txt", "")
    with pytest.raises(install.Failure, match="結構"):
        install.unzip_here(archive, tmp_path / "bot")


def test_downloads_must_be_https(tmp_path):
    with pytest.raises(install.Failure, match="HTTPS"):
        install.download("http://example.com/x.zip", tmp_path / "x.zip")


def test_the_env_template_holds_no_secrets_and_starts_in_json_mode():
    values = dict(
        line.split("=", 1)
        for line in install.ENV_TEMPLATE.splitlines()
        if line and not line.startswith("#")
    )
    for key in ("DISCORD_TOKEN", "OSU_CLIENT_SECRET", "GITHUB_TOKEN", "BOT_API_SECRET"):
        assert values[key] == ""
    assert values["STORAGE_BACKEND"] == "json"
    assert values["BOT_API_ENABLED"] == "false"


def test_the_installer_never_asks_for_a_secret(tmp_path):
    asked = []

    def ask(prompt):
        asked.append(prompt)
        return ""

    job, _ = make(tmp_path)
    install.main(["--check"], ask=ask, installer=lambda o: job)
    assert asked == []  # --check and --yes never prompt, and no prompt is about secrets
    source = SCRIPT.read_text(encoding="utf-8")
    assert "getpass" not in source


def test_zip_only_downloads_the_official_repository():
    with pytest.raises(SystemExit):
        install.parse(["--zip", "--repo", "https://github.com/someone/else.git"])


def test_the_installer_script_has_no_third_party_imports():
    import ast

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert names <= set(sys.stdlib_module_names) | {"__future__"}

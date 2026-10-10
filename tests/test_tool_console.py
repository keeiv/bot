"""Developer-only tier overrides preserve real allowance and tenure."""

from pathlib import Path

import pytest

from src.config.constants import DEVELOPER_IDS
from src.services.tool_quota import ToolQuota
from src.tool_console import execute


def test_terminal_override_shared_persistent_expires_and_restores(tmp_path):
    now = [1800000000.0]
    path = tmp_path / "quota.db"
    quota = ToolQuota(path, clock=lambda: now[0])
    uid = str(next(iter(DEVELOPER_IDS)))
    original = quota.snapshot(uid)
    job = quota.reserve(uid, quota.quote(uid, [1], "png"))
    quota.finish(uid, job, 0.1, True)
    for tier in ("Run.", "Dash.", "Grow.", "Ultra.", "Free."):
        assert tier in execute(quota, uid, f"plan {tier}")
        state = ToolQuota(path, clock=lambda: now[0]).snapshot(uid)
        assert state["tier"]["name"] == tier
        assert state["firstSeen"] == original["firstSeen"]
        assert state["weekly"]["used"] == 1
        assert state["naturalTier"]["name"] == "Nova 20x."
    execute(quota, uid, "plan Ultra.")
    now[0] += 86401
    assert quota.snapshot(uid)["tier"]["name"] == "Nova 20x."
    execute(quota, uid, "plan Ultra.")
    execute(quota, uid, "plan auto")
    assert quota.snapshot(uid)["testTierExpiresAt"] is None
    assert quota.snapshot(uid)["tier"]["name"] == "Nova 20x."
    execute(quota, uid, "plan Free.")
    execute(quota, uid, "plan Nova")
    assert quota.snapshot(uid)["tier"]["name"] == "Nova 20x."


def test_terminal_cannot_target_non_developer_or_other_account(tmp_path):
    quota = ToolQuota(tmp_path / "quota.db")
    uid = str(next(iter(DEVELOPER_IDS)))
    for operation in (
        lambda: quota.set_test_tier("123", "Ultra."),
        lambda: execute(quota, "123", "status"),
    ):
        with pytest.raises(PermissionError):
            operation()
    for command in ("plan Unknown", "plan Ultra. 123", "plan Ultra.; reset", "reset"):
        with pytest.raises(ValueError):
            execute(quota, uid, command)
    assert quota.snapshot(uid)["tier"]["name"] == "Nova 20x."
    assert quota.snapshot("123")["tier"]["name"] == "Free."


def test_terminal_grant_is_explicit_single_target_and_developer_only(tmp_path):
    quota = ToolQuota(tmp_path / "quota.db")
    uid = str(next(iter(DEVELOPER_IDS)))
    assert "Nova 20x." in execute(quota, uid, "nova 123")
    with pytest.raises(PermissionError):
        execute(quota, "123", "nova 124")
    for command in ("nova", "nova all", "nova 123 124", "unova"):
        with pytest.raises(ValueError):
            execute(quota, uid, command)
    assert "Free." in execute(quota, uid, "unova 123")
    assert quota.snapshot(uid)["tier"]["name"] == "Nova 20x."


def test_launcher_has_separate_terminal_option():
    launcher = Path(__file__).resolve().parents[1] / "run_bot.bat"
    if not launcher.is_file():
        pytest.skip("Local Windows launcher is not part of the source checkout")
    source = launcher.read_text(encoding="utf-8")
    assert "[T] Developer file-tools terminal" in source
    assert "-X utf8 -m src.tool_console" in source
    assert "if !MENU_CHOICE! == 14 goto TOOL_TERMINAL" in source

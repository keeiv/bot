"""The control panel's data browser: Chinese names, safe edits, JSON listing."""

import io
import json

import pytest
from rich.console import Console

from src.control_panel import data_browser
from src.control_panel import labels
from src.control_panel.app import ControlPanel
from src.control_panel.app import Keyboard
from src.control_panel.state import BotStatus
from src.control_panel.state import Paths

SETTINGS = "data/storage/anti_spam_settings.json"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    (tmp_path / "data" / "logs").mkdir(parents=True)
    _put(
        tmp_path,
        SETTINGS,
        {
            "1461": {
                "ban_delete_days": 1,
                "enabled": True,
                "flood_limit": 5,
                "api_token": "do-not-show",
                "cookies": {"ltuid": "hidden"},
            }
        },
    )
    return tmp_path


def _put(root, path, data, pretty=True):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)
    target.write_text(text, encoding="utf-8")


def _browser(root, reason=None):
    browser = data_browser.Browser(data_browser.Store(root), lambda: reason)
    browser.load()
    return browser


def _open(browser, path):
    browser.selected = next(i for i, r in enumerate(browser.rows()) if r.key == path)
    browser.enter()


# ── names ─────────────────────────────────────────────────────────


def test_fields_read_in_chinese():
    assert labels.field_label("ban_delete_days") == "封禁時刪除幾天內的訊息"
    assert labels.field_label("guild_id") == "伺服器 ID"
    assert labels.field_label("flood_limit") == "洗版上限"
    assert labels.field_label("created_at") == "建立時間"
    assert labels.field_label("1461", "guilds") == "伺服器 1461"
    assert labels.field_label("unlocked_at_first_win") == "解鎖時間：first_win"
    assert labels.field_label("mystery_field") == "mystery_field"


def test_documents_have_chinese_names():
    assert labels.document_label(SETTINGS) == "防洗版：設定"
    assert labels.document_label("data/storage/pets/42.json") == "夥伴：42"
    assert labels.document_label("data/storage/unknown.json") == "unknown"
    assert (
        labels.field_label("42", document="data/storage/petition.json") == "使用者 42"
    )


def test_leftovers_are_marked_and_listed_last(root):
    _put(root, "data/storage/daily.json", {})
    _put(root, "data/guild_42_messages.json", {})
    _put(root, "data/storage/zzz_new.json", {})
    assert labels.is_unused("data/storage/daily.json")
    assert labels.is_unused("data/guild_42_messages.json")
    assert not labels.is_unused(SETTINGS)
    paths = [row.key for row in _browser(root).rows()]
    assert paths[:2] == [SETTINGS, "data/storage/zzz_new.json"]
    assert set(paths[2:]) == {"data/storage/daily.json", "data/guild_42_messages.json"}


def test_credentials_are_recognised():
    for key in ("api_token", "cookies", "client_secret", "password", "jws"):
        assert labels.is_sensitive(key)
    assert not labels.is_sensitive("ban_delete_days")


# ── values ────────────────────────────────────────────────────────


def test_typed_values_keep_their_type():
    assert data_browser.parse_value("7", 1) == 7
    assert data_browser.parse_value("1,500", 0) == 1500
    assert data_browser.parse_value("1.5", 2.0) == 1.5
    assert data_browser.parse_value("否", True) is False
    assert data_browser.parse_value("yes", False) is True
    assert data_browser.parse_value("你好", "old") == "你好"
    assert data_browser.parse_value('""', "old") == ""
    assert data_browser.parse_value("30", None) == 30
    assert data_browser.parse_value("空", None) is None
    assert data_browser.parse_value("是", None) is True
    with pytest.raises(ValueError):
        data_browser.parse_value("seven", 1)
    with pytest.raises(ValueError):
        data_browser.parse_value("maybe", True)


def test_set_at_leaves_the_original_alone():
    data = {"a": [{"b": 1}]}
    changed = data_browser.set_at(data, ["a", 0, "b"], 2)
    assert changed == {"a": [{"b": 2}]} and data == {"a": [{"b": 1}]}


def test_values_describe_themselves():
    assert data_browser.describe("enabled", True) == "是"
    assert data_browser.describe("x", None) == "（空）"
    assert data_browser.describe("x", "") == "（空字串）"
    assert data_browser.describe("x", {"a": 1}) == "1 個欄位"
    assert data_browser.describe("created_at", 1_700_000_000).startswith(
        "1700000000（2023-"
    )


def test_edits_wait_for_the_bot_to_stop():
    assert data_browser.read_only_reason(BotStatus("running", 1))
    assert data_browser.read_only_reason(BotStatus("stale", 1))
    assert data_browser.read_only_reason(BotStatus("stopped")) is None


# ── browsing ──────────────────────────────────────────────────────


def test_listing_skips_caches_and_gathers_companions(root):
    _put(root, "data/ai/models_cache.json", {})
    _put(root, "data/cache/x.json", {})
    _put(root, "data/backups/data-browser/1/x.json", {})
    _put(root, "data/.claude.json", {})
    _put(root, "data/storage/pets/1.json", {"level": 3})
    _put(root, "data/storage/pets/2.json", {"level": 5})
    browser = _browser(root)
    paths = [row.key for row in browser.rows()]
    assert paths == [SETTINGS, labels.PET_FOLDER]
    assert browser.rows()[-1].label == "夥伴（2 份）"
    _open(browser, labels.PET_FOLDER)
    assert [row.label for row in browser.rows()] == ["夥伴：1", "夥伴：2"]
    assert browser.breadcrumb() == ["資料庫", "夥伴（2 份）"]


def test_rows_show_chinese_and_hide_credentials(root):
    browser = _browser(root)
    _open(browser, SETTINGS)
    browser.enter()  # the server
    rows = {row.english: row for row in browser.rows()}
    assert rows["ban_delete_days"].label == "封禁時刪除幾天內的訊息"
    assert rows["ban_delete_days"].text == "1" and rows["ban_delete_days"].editable
    assert rows["enabled"].text == "是"
    assert rows["api_token"].kind == "secret" and not rows["api_token"].editable
    assert "do-not-show" not in rows["api_token"].text
    assert browser.breadcrumb() == ["資料庫", "防洗版：設定", "伺服器 1461"]
    browser.selected = list(rows).index("cookies")
    browser.enter()  # inside a credential: everything stays hidden
    assert [row.kind for row in browser.rows()] == ["secret"]


def test_back_returns_to_where_you_were(root):
    browser = _browser(root)
    _open(browser, SETTINGS)
    browser.enter()
    browser.move(2)
    assert browser.back() and browser.trail == []
    assert browser.back() and browser.doc is None
    assert not browser.back()  # already at the top


# ── writing ───────────────────────────────────────────────────────


def _edit_days(browser, value):
    _open(browser, SETTINGS)
    browser.enter()
    row = browser.rows()[0]
    assert row.english == "ban_delete_days"
    return browser.apply(row, value)


def test_a_write_backs_up_first_and_keeps_the_file_readable(root):
    browser = _browser(root)
    backup = _edit_days(browser, 7)
    text = (root / SETTINGS).read_text(encoding="utf-8")
    assert json.loads(text)["1461"]["ban_delete_days"] == 7
    assert "\n" in text  # still indented for people who open the file
    saved = json.loads((root / backup).read_text(encoding="utf-8"))
    assert saved["1461"]["ban_delete_days"] == 1
    assert backup.startswith(data_browser.BACKUP_FOLDER)


def test_no_write_while_the_bot_runs(root):
    browser = _browser(root, reason="機器人執行中")
    with pytest.raises(data_browser.ReadOnly):
        _edit_days(browser, 7)
    assert (
        json.loads((root / SETTINGS).read_text("utf-8"))["1461"]["ban_delete_days"] == 1
    )


def test_no_write_over_a_change_made_meanwhile(root):
    browser = _browser(root)
    _open(browser, SETTINGS)
    browser.enter()
    data = json.loads((root / SETTINGS).read_text("utf-8"))
    data["1461"]["flood_limit"] = 9  # the bot wrote while the page was open
    _put(root, SETTINGS, data)
    with pytest.raises(data_browser.Conflict):
        browser.apply(browser.rows()[0], 7)
    after = json.loads((root / SETTINGS).read_text("utf-8"))["1461"]
    assert after["ban_delete_days"] == 1 and after["flood_limit"] == 9
    assert not (root / data_browser.BACKUP_FOLDER).exists()


def test_page_draws_without_error(root):
    browser = _browser(root)
    _open(browser, SETTINGS)
    browser.enter()
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=30)
    from datetime import datetime

    console.print(data_browser.page(browser, datetime(2026, 1, 1), 100, 30))
    out = console.file.getvalue()
    assert "[封禁時刪除幾天內的訊息]" in out and "ban_delete_days" in out
    assert "do-not-show" not in out and "可修改" in out


# ── in the panel ──────────────────────────────────────────────────


class ScriptedKeys(Keyboard):
    def __init__(self, *keys):
        self.keys = list(keys)

    def poll(self, timeout):
        assert self.keys, "the panel asked for more keys than the test gave"
        return self.keys.pop(0)


def _panel(root, *keys, typed="7"):
    paths = Paths(
        root=root, lock=root / "bot.lock", logs=root / "data" / "logs", python="python"
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=100, height=34)
    panel = ControlPanel(console, ScriptedKeys(*keys), paths)
    console.input = lambda prompt="": typed  # type: ignore[method-assign]
    return panel


def test_panel_edit_asks_before_writing(root):
    # open the document, open the server, edit the first field, confirm, leave
    panel = _panel(root, "enter", "enter", "e", "y", "q")
    panel._data_browser(data_browser.Store(root))
    assert (
        json.loads((root / SETTINGS).read_text("utf-8"))["1461"]["ban_delete_days"] == 7
    )


def test_panel_edit_cancelled_by_any_other_key(root):
    panel = _panel(root, "enter", "enter", "e", "n", "q")
    panel._data_browser(data_browser.Store(root))
    assert (
        json.loads((root / SETTINGS).read_text("utf-8"))["1461"]["ban_delete_days"] == 1
    )


def test_panel_refuses_a_bad_number(root):
    panel = _panel(root, "enter", "enter", "e", "q", typed="seven")
    panel._data_browser(data_browser.Store(root))
    assert (
        json.loads((root / SETTINGS).read_text("utf-8"))["1461"]["ban_delete_days"] == 1
    )

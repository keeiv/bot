"""Local, allowlisted developer console for file-tool tier testing."""

import argparse
from datetime import datetime
from pathlib import Path
import shlex

from dotenv import load_dotenv

from src.config.constants import DEVELOPER_IDS
from src.services.tool_quota import TAIPEI
from src.services.tool_quota import ToolQuota
from src.services.tool_quota import valid_id
from src.utils.mysql_runtime import prepare_storage

HELP = "指令：status｜plan Free./Run./Dash./Grow./Ultra.｜plan Nova（還原預設）｜nova [userid]｜unova [userid]｜help｜exit"


def developer_id(value):
    uid = valid_id(value)
    if int(uid) not in DEVELOPER_IDS:
        raise PermissionError("此 Discord ID 未列於 DEVELOPER_IDS")
    return uid


def describe(data):
    expiry = data.get("testTierExpiresAt")
    mode = (
        "測試至 " + datetime.fromtimestamp(expiry, TAIPEI).strftime("%Y/%m/%d %H:%M %z")
        if expiry
        else "固定授權等級" if data["tier"].get("hidden") else "依使用天數自動升級"
    )
    return (
        f"帳號 {data['userId']}｜目前 {data['tier']['name']}｜原始 {data['naturalTier']['name']}｜{mode}\n"
        f"週用量 {data['weekly']['used']}/{data['weekly']['limit']}｜"
        f"近三小時 {data['rolling']['used']}/{data['rolling']['limit']}｜預留 {data['reserved']}"
    )


def execute(quota, actor, command):
    uid = developer_id(actor)
    parts = shlex.split(command)
    if not parts or parts == ["help"]:
        return HELP
    if parts == ["status"]:
        return describe(quota.snapshot(uid))
    if len(parts) == 2 and parts[0] == "plan":
        return describe(quota.set_test_tier(uid, parts[1]))
    if len(parts) == 2 and parts[0] in {"nova", "unova"}:
        return describe(quota.set_nova(uid, parts[1], parts[0] == "nova"))
    raise ValueError(HELP)


def main(argv=None):
    parser = argparse.ArgumentParser(description="本機開發者檔案工具終端機")
    parser.add_argument("--user", help="DEVELOPER_IDS 中的 Discord 帳號 ID")
    parser.add_argument("--command", help="執行單一指令後離開，例如 plan Ultra.")
    args = parser.parse_args(argv)
    try:
        actor = developer_id(args.user or input("開發者 Discord ID：").strip())
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        prepare_storage()
        quota = ToolQuota()
        if args.command:
            print(execute(quota, actor, args.command))
            return 0
        print("開發者終端機 · 預設 Nova 20x. · 測試等級 24 小時後自動還原")
        print("切換等級不重置年資、用量或重置券；網站重新整理後生效。")
        print(HELP)
        print(execute(quota, actor, "status"))
        while True:
            command = input("tools> ").strip()
            if command in {"exit", "quit"}:
                return 0
            try:
                print(execute(quota, actor, command))
            except (ValueError, PermissionError) as exc:
                print(str(exc))
    except (EOFError, KeyboardInterrupt):
        return 0
    except (ValueError, PermissionError) as exc:
        print(str(exc))
        return 1
    except Exception:
        print("終端機無法連接儲存服務，請確認本機資料庫與設定。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

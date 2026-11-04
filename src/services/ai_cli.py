"""Ask Claude or GPT through the desktop apps' command-line tools.

Claude runs through Claude Code (the ``claude.exe`` that the Claude desktop app
keeps under ``%LOCALAPPDATA%/Claude-Data``) and GPT through the Codex CLI. Both
use the subscriptions signed in on this machine; no API key is involved.

Every call is a fresh session that is not saved, in an empty temporary folder,
with every tool turned off: a model can only read the text and images it is
given and write an answer. Text from members only ever reaches a model on
standard input, never on a command line.

Anything that stops an answer (the tool is missing or signed out, the quota is
used up, a timeout, an empty reply) raises :class:`AiCliError`; the caller
decides what that means. After a failure that model is skipped for a short
while, so a used-up quota is not asked again and again.

What each model did today (calls, failures, tokens, whether it is resting) is
written to ``data/ai_usage.json`` by :class:`UsageLog`, for the control panel.

Both tools run with homes of their own under ``data/ai`` (``CODEX_HOME`` and
``CLAUDE_CONFIG_DIR``), never the owner's: the owner's global instructions
(``AGENTS.md``, ``CLAUDE.md``), skills and settings must not reach members'
chats or the review policy. The bot's Codex therefore has its own sign-in
(``codex login`` with that ``CODEX_HOME``); Claude signs in with
``CLAUDE_CODE_OAUTH_TOKEN``.
"""

import asyncio
import base64
from dataclasses import dataclass
from dataclasses import field
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Awaitable, Callable, Optional, Sequence

CLAUDE, GPT = "claude", "gpt"
PROVIDERS = (CLAUDE, GPT)
MAX_RUNNING = 2  # model processes at the same time, for chat and review together
DOWN_SECONDS = 60  # after a failure, that model is not asked for this long
QUEUE_SECONDS = 45  # how long a request may wait for a free model process
MAX_DRAWINGS = 4  # images kept from one drawing request
MAX_DRAWING_BYTES = 20 * 1024 * 1024
USAGE_FILE = "data/ai_usage.json"
HOME = Path(os.getenv("AI_CLI_HOME", "data/ai"))

# Codex features that would let a model act on this machine or reach out of it.
CODEX_DISABLED = (
    "shell_tool",
    "unified_exec",
    "code_mode_host",
    "shell_snapshot",
    "apps",
    "plugins",
    "remote_plugin",
    "memories",
    "multi_agent",
    "image_generation",
    "view_image",
    "browser_use",
    "browser_use_external",
    "in_app_browser",
    "computer_use",
    "hooks",
    "skill_search",
    "tool_suggest",
    "sleep_tool",
    "goals",
)

# Environment the tools keep: everything except the bot's own secrets.
# The only environment a model process gets: what Windows and the two tools need
# to start, find their sign-in and reach the network. Nothing of the bot's own.
_PASS = {
    name.upper()
    for name in (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "NUMBER_OF_PROCESSORS",
        "USERNAME",
        "USERDOMAIN",
        "COMPUTERNAME",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "TEMP",
        "TMP",
        "LANG",
        "LC_ALL",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "NODE_EXTRA_CA_CERTS",
        # sign-in and configuration of the two tools
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CONFIG_DIR",
        "ANTHROPIC_API_KEY",
        "CODEX_HOME",
        "OPENAI_API_KEY",
    )
}

Runner = Callable[[Sequence[str], bytes, str, float], Awaitable[tuple[int, bytes]]]


@dataclass(frozen=True)
class Answer:
    text: str
    model: str  # the model that answered, as the tool reports it
    web_searches: int = 0
    drawings: list[bytes] = field(default_factory=list)


class AiCliError(Exception):
    """The model did not answer: missing, signed out, out of quota, or timed out."""


def find_claude(
    environ: Optional[dict[str, str]] = None, which: Callable[..., Any] = shutil.which
) -> Optional[str]:
    """``CLAUDE_CLI``, else the desktop app's Claude Code, else ``claude`` on PATH."""
    environ = dict(os.environ) if environ is None else environ
    if environ.get("CLAUDE_CLI"):
        return environ["CLAUDE_CLI"] if Path(environ["CLAUDE_CLI"]).is_file() else None
    base = environ.get("LOCALAPPDATA")
    if base:
        # The app updates Claude Code into a new versioned folder; take the newest.
        found = sorted(
            Path(base).glob("Claude-Data/*/claude-code/*/*/claude.exe"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if found:
            return str(found[0])
    return which("claude")


def find_codex(
    environ: Optional[dict[str, str]] = None, which: Callable[..., Any] = shutil.which
) -> Optional[str]:
    """``CODEX_CLI``, else ``codex`` on PATH (its native ``codex.exe`` when npm-installed)."""
    environ = dict(os.environ) if environ is None else environ
    if environ.get("CODEX_CLI"):
        return environ["CODEX_CLI"] if Path(environ["CODEX_CLI"]).is_file() else None
    found = which("codex")
    if not found:
        return None
    # npm installs a .cmd wrapper; the real program sits in the package folder.
    native = sorted(
        Path(found).parent.glob(
            "node_modules/@openai/codex/node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"
        )
    )
    return str(native[0]) if native else found


def child_environment(environ: Optional[dict[str, str]] = None) -> dict[str, str]:
    """The environment for a model process: an allowlist, so no bot secret can leak."""
    environ = dict(os.environ) if environ is None else environ
    return {key: value for key, value in environ.items() if key.upper() in _PASS}


def isolated_environment(
    environ: Optional[dict[str, str]] = None, home: Optional[Path] = None
) -> dict[str, str]:
    """The allowlisted environment, pointed at the bot's own homes for both tools."""
    home = (home or HOME).resolve()
    env = child_environment(environ)
    for key in [k for k in env if k.upper() in ("CODEX_HOME", "CLAUDE_CONFIG_DIR")]:
        del env[key]
    for name, key in (("codex", "CODEX_HOME"), ("claude", "CLAUDE_CONFIG_DIR")):
        folder = home / name
        folder.mkdir(parents=True, exist_ok=True)
        env[key] = str(folder)
    return env


async def run_process(
    args: Sequence[str], stdin: bytes, cwd: str, seconds: float
) -> tuple[int, bytes]:
    """Run ``args`` with ``stdin``; returns the exit code and standard output."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=cwd,
            env=isolated_environment(),
            creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
        )
    except OSError as error:
        raise AiCliError("無法啟動模型程式") from error
    try:
        output, _ = await asyncio.wait_for(process.communicate(stdin), seconds)
    except BaseException as error:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if isinstance(error, asyncio.TimeoutError):
            raise AiCliError("模型回覆逾時") from error
        raise
    return process.returncode or 0, output


def _tokens(usage: Any) -> int:
    """Input plus output tokens from a tool's usage report (cached input included)."""
    if not isinstance(usage, dict):
        return 0
    total = 0
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        value = usage.get(key)
        if type(value) is int and value > 0:
            total += value
    return total


def _events(output: bytes):
    for line in output.decode("utf-8", "replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


class UsageLog:
    """Today's use of each model, kept in a small JSON file the panel reads.

    Layout::

        {"date": "2026-11-04",
         "providers": {"claude": {"installed": true, "model": "haiku",
                                  "calls": 3, "failures": 1, "tokens": 51234,
                                  "down_until": 1793836800.0}}}

    ``down_until`` is wall-clock time (seconds); the counters restart each day.
    Writing never raises: the panel's numbers must not break a reply.
    """

    def __init__(self, path: str = USAGE_FILE, today=date.today, now=time.time):
        self.path = Path(path)
        self._today = today
        self._now = now
        self._data: Optional[dict[str, Any]] = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            self._data = data if isinstance(data, dict) else {}
        today = self._today().isoformat()
        same_day = self._data.get("date") == today
        old = self._data.get("providers")
        old = old if isinstance(old, dict) else {}
        providers = {}
        for name in PROVIDERS:
            entry = old.get(name)
            entry = entry if isinstance(entry, dict) else {}

            def number(key: str, kind: type, entry=entry) -> Any:
                # counters restart each day; a damaged value starts over too
                value = entry.get(key)
                return value if same_day and type(value) is kind else kind()

            providers[name] = {
                "installed": entry.get("installed") is True,
                "model": (
                    entry.get("model") if isinstance(entry.get("model"), str) else ""
                ),
                "calls": number("calls", int),
                "failures": number("failures", int),
                "tokens": number("tokens", int),
                "down_until": number("down_until", float),
            }
        self._data = {"date": today, "providers": providers}
        return self._data

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self._data), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            pass

    def installed(self, found: dict[str, bool]) -> None:
        data = self._load()
        for name, present in found.items():
            data["providers"][name]["installed"] = present
        self._save()

    def record(self, provider: str, model: str, tokens: int, ok: bool) -> None:
        entry = self._load()["providers"][provider]
        entry["installed"] = True
        entry["model"] = model
        entry["calls"] += 1
        entry["tokens"] += max(tokens, 0)
        if ok:
            entry["down_until"] = 0.0
        else:
            entry["failures"] += 1
            entry["down_until"] = self._now() + DOWN_SECONDS
        self._save()


class AiCli:
    """Both models, with a shared limit on how many run at once."""

    def __init__(
        self,
        *,
        claude: Optional[str] = None,
        codex: Optional[str] = None,
        runner: Runner = run_process,
        usage: Optional[UsageLog] = None,
        home: Optional[Path] = None,
    ) -> None:
        self.usage = usage
        self.home = home or HOME
        self._paths = {CLAUDE: claude, GPT: codex}
        self._looked = {CLAUDE: claude is not None, GPT: codex is not None}
        self._run = runner
        self._slots = asyncio.Semaphore(MAX_RUNNING)
        self._down_until = {CLAUDE: 0.0, GPT: 0.0}

    def path(self, provider: str) -> Optional[str]:
        if not self._looked[provider]:
            self._looked[provider] = True
            self._paths[provider] = (
                find_claude() if provider == CLAUDE else find_codex()
            )
        return self._paths[provider]

    def available(self, provider: str) -> bool:
        """True when the tool is installed (it may still be signed out or out of quota)."""
        return self.path(provider) is not None

    def report_installed(self) -> None:
        """Tell the panel which tools are present, before anyone has asked anything."""
        if self.usage is not None:
            self.usage.installed({p: self.available(p) for p in PROVIDERS})

    async def ask(
        self,
        provider: str,
        *,
        system: str,
        prompt: str,
        model: str,
        images: Sequence[str] = (),
        seconds: float = 90,
    ) -> str:
        """One answer from ``provider``, as text. ``images`` are base64 JPEGs."""
        answer = await self.ask_full(
            provider,
            system=system,
            prompt=prompt,
            model=model,
            images=images,
            seconds=seconds,
        )
        return answer.text

    async def ask_full(
        self,
        provider: str,
        *,
        system: str,
        prompt: str,
        model: str,
        images: Sequence[str] = (),
        seconds: float = 90,
        web: bool = False,
        draw: bool = False,
    ) -> Answer:
        """One answer with the model that gave it, its web searches and drawings.

        ``web`` lets the model search the web (Claude's server-side search; Codex's
        web search, which needs Codex's code mode while its shell stays off).
        ``draw`` lets GPT generate images; Claude cannot draw.
        """
        if provider not in PROVIDERS:
            raise ValueError("unknown provider")
        if draw and provider != GPT:
            raise ValueError("only GPT draws")
        if time.monotonic() < self._down_until[provider]:
            raise AiCliError("模型暫停使用中")
        executable = self.path(provider)
        if executable is None:
            raise AiCliError("找不到模型程式")
        try:
            await asyncio.wait_for(self._slots.acquire(), QUEUE_SECONDS)
        except asyncio.TimeoutError as error:
            raise AiCliError("等待模型逾時") from error
        try:
            # A request that queued while the model failed must not start it again.
            if time.monotonic() < self._down_until[provider]:
                raise AiCliError("模型暫停使用中")
            spent = [0]  # tokens, filled in even when the answer is unusable
            try:
                with tempfile.TemporaryDirectory(
                    prefix="bot-ai-", ignore_cleanup_errors=True
                ) as folder:
                    if provider == CLAUDE:
                        answer = await self._claude(
                            executable,
                            folder,
                            system,
                            prompt,
                            model,
                            images,
                            seconds,
                            spent,
                            web,
                        )
                    else:
                        answer = await self._codex(
                            executable,
                            folder,
                            system,
                            prompt,
                            model,
                            images,
                            seconds,
                            spent,
                            web,
                            draw,
                        )
            except AiCliError:
                self._down_until[provider] = time.monotonic() + DOWN_SECONDS
                if self.usage is not None:
                    self.usage.record(provider, model, spent[0], ok=False)
                raise
            if self.usage is not None:
                self.usage.record(provider, answer.model, spent[0], ok=True)
            return answer
        finally:
            self._slots.release()

    async def _claude(
        self, executable, folder, system, prompt, model, images, seconds, spent, web
    ):
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
            }
            for data in images
        ]
        content.append({"type": "text", "text": prompt})
        message = {"type": "user", "message": {"role": "user", "content": content}}
        # WebSearch runs on Anthropic's side; WebFetch (which would fetch from this
        # machine, local network included) is never offered.
        tools = (
            ["--tools", "WebSearch", "--allowedTools", "WebSearch"]
            if web
            else ["--tools", ""]
        )
        args = [
            executable,
            "-p",
            "--model",
            model,
            *tools,
            "--safe-mode",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--permission-prompts",
            "none",
            "--system-prompt",
            system,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        _, output = await self._run(
            args, (json.dumps(message) + "\n").encode("utf-8"), folder, seconds
        )
        result, used, searches = None, model, 0
        for event in _events(output):
            kind = event.get("type")
            if kind == "system" and isinstance(event.get("model"), str):
                used = event["model"]  # the model Claude Code really ran
            elif kind == "assistant":
                blocks = (event.get("message") or {}).get("content") or []
                searches += sum(
                    1
                    for block in blocks
                    if isinstance(block, dict)
                    # Claude Code reports its WebSearch tool as a tool_use;
                    # the API's own search would be a server_tool_use.
                    and (block.get("type"), block.get("name"))
                    in (("tool_use", "WebSearch"), ("server_tool_use", "web_search"))
                )
            elif kind == "result":
                result = event
                spent[0] = _tokens(event.get("usage"))
        # A used-up quota or an expired sign-in comes back as an error result.
        if (
            result is None
            or result.get("is_error")
            or not isinstance(result.get("result"), str)
            or not result["result"].strip()
        ):
            raise AiCliError("Claude 沒有回覆")
        return Answer(result["result"].strip(), used, searches)

    async def _codex(
        self,
        executable,
        folder,
        system,
        prompt,
        model,
        images,
        seconds,
        spent,
        web,
        draw,
    ):
        answer = Path(folder) / "answer.txt"
        attached: list[str] = []
        for index, data in enumerate(images):
            path = Path(folder) / f"image-{index}.jpg"
            path.write_bytes(base64.b64decode(data))
            attached += ["-i", str(path)]
        # Drawing saves a file, so it needs a writable workspace (the empty
        # temporary folder); without a shell the model cannot write anything else.
        args = [
            executable,
            "exec",
            *attached,
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "-s",
            "workspace-write" if draw else "read-only",
            "-m",
            model,
            "-c",
            'model_reasoning_effort="low"',
        ]
        if web:
            args += ["-c", "tools.web_search=true"]
        if draw:
            args += ["--enable", "image_generation"]
        for feature in CODEX_DISABLED:
            # Web search and drawing only exist through Codex's code mode (checked
            # with Codex 0.162: both fail without it). Code mode runs JavaScript in an
            # isolate with no require, Deno, process or fetch: it can only call the
            # tools left on here, never read files, the environment or the network.
            # The shell and program execution stay off, and CODEX_HOME holds only the
            # bot's own sign-in.
            if feature == "code_mode_host" and (web or draw):
                continue
            if feature == "image_generation" and draw:
                continue
            args += ["--disable", feature]
        args += ["-C", folder, "-o", str(answer), "--color", "never", "--json", "-"]
        # Codex has no separate system prompt in exec mode: the instructions lead.
        stdin = f"<instructions>\n{system}\n</instructions>\n\n{prompt}"
        code, output = await self._run(args, stdin.encode("utf-8"), folder, seconds)
        thread, searches = "", 0
        for event in _events(output):
            if event.get("type") == "thread.started":
                thread = str(event.get("thread_id") or "")
            elif event.get("type") == "turn.completed":
                spent[0] += _tokens(event.get("usage"))
            elif event.get("type") == "item.completed":
                item = event.get("item") or {}
                if item.get("type") == "web_search" and item.get("query"):
                    searches += 1
        drawn = self._drawings(thread) if draw else []
        text = answer.read_text(encoding="utf-8").strip() if answer.is_file() else ""
        if code != 0 or not (text or drawn):
            raise AiCliError("GPT 沒有回覆")
        return Answer(text, model, searches, drawn)

    def _drawings(self, thread: str) -> list[bytes]:
        """Images Codex saved for this session, read and then removed."""
        if not re.fullmatch(r"[0-9a-f-]{8,64}", thread):
            return []
        folder = self.home / "codex" / "generated_images" / thread
        if not folder.is_dir():
            return []
        found = []
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                data = path.read_bytes()
                if 0 < len(data) <= MAX_DRAWING_BYTES:
                    found.append(data)
        shutil.rmtree(folder, ignore_errors=True)
        return found[:MAX_DRAWINGS]


_shared: Optional[AiCli] = None


def shared() -> AiCli:
    """The one :class:`AiCli` the bot uses, so the limit covers every caller."""
    global _shared
    if _shared is None:
        _shared = AiCli(usage=UsageLog())
    return _shared

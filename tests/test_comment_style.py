"""Comments read the same in every file: English, and one form of section banner.

The copy members see is bilingual and lives in ``src/locales``; this is only
about what a developer reads in the source.
"""

import ast
import io
from pathlib import Path
import re
import subprocess
import tokenize

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tracked() -> list[Path]:
    """The files in the repository; ones kept on a single machine are not held to this."""
    listed = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if listed.returncode == 0 and listed.stdout.strip():
        return sorted(ROOT / name for name in listed.stdout.split())
    return sorted(
        path
        for folder in ("src", "services", "tests")
        for path in (ROOT / folder).rglob("*.py")
        if "__pycache__" not in path.parts
    )


FILES = _tracked()
CJK = re.compile(r"[㐀-鿿]")
DECORATION = "─═=~*-"
BANNER = re.compile(r"^# ── \S.* ─{3,}$")
BANNER_WIDTH = 68  # from "#" to the last dash, unless the title needs more
# English comments that quote a label, a name or a path as it really is.
QUOTED = {
    "Claude維護",
    "無本地模型",
    "文件",
    "BOT. 控制台.lnk",
    "諾瓦",
    "十四行詩",
    "晨曦",
    "異相仲裁",
    "今日",
}


def _without_quoted(text: str) -> str:
    for quoted in QUOTED:
        text = text.replace(quoted, "")
    return text


def _comments(source: str):
    lines = source.split("\n")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            alone = lines[token.start[0] - 1].strip() == token.string
            yield token.start[0], token.string, alone


def _docstrings(source: str):
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, kinds):
            text = ast.get_docstring(node)
            if text:
                yield getattr(node, "lineno", 1), text


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_comments_and_docstrings_are_english_with_one_banner_form(path):
    source = path.read_text(encoding="utf-8")
    chinese, banners = [], []
    for line, text, alone in _comments(source):
        if CJK.search(_without_quoted(text)):
            chinese.append((line, text))
        body = text[1:].strip()
        decorated = len(body) >= 3 and body[0] in DECORATION and body[:2] == body[0] * 2
        if alone and decorated and not text.startswith("# --"):
            ok = BANNER.match(text) and (
                len(text) == BANNER_WIDTH or text.endswith(" ───")
            )
            if not ok:
                banners.append((line, text))
    for line, text in _docstrings(source):
        if CJK.search(_without_quoted(text)):
            chinese.append((line, text.split("\n")[0]))
    assert not chinese, f"write these in English: {chinese[:5]}"
    assert not banners, f"use '# ── Title ───': {banners[:5]}"

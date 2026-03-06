#!/usr/bin/env python3
"""英語標準檢查腳本

此腳本檢查專案檔案中是否包含非英文字元（中文為主），含：
- 變數、函式、類別名稱
- 註解與字串（嚴格模式）

用途：在 CI 或本地檢查時使用，預設檢查 `src/`。
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


class EnglishStandardsChecker:
    """檢查器：檢查檔案是否含有中文字元。

    參數:
      - allowed_paths: 可例外的路徑（允許出現非英文）
      - strict_mode: 是否啟用嚴格模式（同時檢查字串與註解）
    """

    def __init__(self, allowed_paths: List[str] | None = None, strict_mode: bool = False):
        self.allowed_paths = allowed_paths or ["README.md", "docs/"]
        self.strict_mode = strict_mode
        self.chinese_pattern = re.compile(r"[\u4e00-\u9fff]")
        self.issues: List[Tuple[str, int, str]] = []

    def check_file(self, file_path: Path) -> bool:
        """檢查單一檔案，回傳是否通過檢查。"""
        if self.is_allowed_file(file_path):
            return True

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if file_path.suffix == ".py":
                return self.check_python_file(file_path, content)
            return self.check_text_file(file_path, content)
        except Exception as e:
            print(f"Error checking {file_path}: {e}")
            return False

    def is_allowed_file(self, file_path: Path) -> bool:
        for allowed in self.allowed_paths:
            if allowed in str(file_path):
                return True
        return False

    def check_python_file(self, file_path: Path, content: str) -> bool:
        try:
            tree = ast.parse(content)
            if self.strict_mode:
                self.check_strings_and_comments(content, file_path)
            self.check_ast_nodes(tree, file_path)
        except SyntaxError:
            self.add_issue(file_path, 0, "Syntax error in file")

        return len(self.issues) == 0

    def check_ast_nodes(self, tree: ast.AST, file_path: Path) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.has_chinese(node.name):
                    self.add_issue(file_path, node.lineno, f"Function name '{node.name}' contains Chinese characters")
            elif isinstance(node, ast.ClassDef):
                if self.has_chinese(node.name):
                    self.add_issue(file_path, node.lineno, f"Class name '{node.name}' contains Chinese characters")
            elif isinstance(node, ast.Name):
                if self.has_chinese(node.id) and node.id not in dir(__builtins__):
                    self.add_issue(file_path, node.lineno, f"Variable name '{node.id}' contains Chinese characters")

    def check_strings_and_comments(self, content: str, file_path: Path) -> None:
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line.strip()) <= 1:
                continue
            if self.has_chinese(line):
                self.add_issue(file_path, i, "Line contains Chinese characters")

    def check_text_file(self, file_path: Path, content: str) -> bool:
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if self.has_chinese(line):
                self.add_issue(file_path, i, f"Text contains Chinese characters: {line.strip()}")
        return len(self.issues) == 0

    def has_chinese(self, text: str) -> bool:
        return bool(self.chinese_pattern.search(text))

    def add_issue(self, file_path: Path, line: int, message: str) -> None:
        self.issues.append((str(file_path), line, message))

    def check_directory(self, directory: Path) -> bool:
        python_files = list(directory.rglob("*.py"))
        other_files: List[Path] = []
        for pattern in ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"]:
            other_files.extend(directory.rglob(pattern))
        all_files = python_files + other_files
        all_passed = True
        for file_path in all_files:
            if not self.check_file(file_path):
                all_passed = False
        return all_passed

    def print_issues(self) -> None:
        if not self.issues:
            print("All files pass English standards check")
            return
        print(f"Found {len(self.issues)} English standards violations:")
        for file_path, line, message in self.issues:
            print(f"  {file_path}:{line} - {message}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check English standards compliance")
    parser.add_argument("path", nargs="?", default="src/", help="Path to check (default: src/)")
    parser.add_argument("--allowed", nargs='+', default=["README.md", "docs/"], help="Allowed paths that can contain non-English text")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode (checks comments and strings)")

    args = parser.parse_args()
    checker = EnglishStandardsChecker(args.allowed, args.strict)
    path = Path(args.path)
    if path.is_file():
        passed = checker.check_file(path)
    else:
        passed = checker.check_directory(path)
    checker.print_issues()
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

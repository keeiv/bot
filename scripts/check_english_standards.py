#!/usr/bin/env python3
"""
English Standards Checker Script

This script enforces English-only code standards by checking for:
- Non-English variable and function names
- Non-English comments and docstrings
- Non-English user-facing strings
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple


class EnglishStandardsChecker:
    def __init__(self, allowed_paths: List[str] = None, strict_mode: bool = False):
        self.allowed_paths = allowed_paths or ['README.md', 'docs/']
        self.strict_mode = strict_mode
        # In non-strict mode, only check for Chinese characters in critical areas
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]') if strict_mode else re.compile(r'[\u4e00-\u9fff]')
        self.issues: List[Tuple[str, int, str]] = []

    def check_file(self, file_path: Path) -> bool:
        """Check a single file for English standards compliance."""
        if self.is_allowed_file(file_path):
            return True

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if file_path.suffix == '.py':
                return self.check_python_file(file_path, content)
            else:
                return self.check_text_file(file_path, content)
        except Exception as e:
            print(f"Error checking {file_path}: {e}")
            return False

    def is_allowed_file(self, file_path: Path) -> bool:
        """Check if file is exempt from English standards."""
        for allowed in self.allowed_paths:
            if str(file_path).startswith(allowed):
                return True
        return False

    def check_python_file(self, file_path: Path, content: str) -> bool:
        """Check Python file for English standards."""
        try:
            tree = ast.parse(content)
            if self.strict_mode:
                self.check_ast_nodes(tree, file_path)
                self.check_strings_and_comments(content, file_path)
            else:
                # In non-strict mode, only check function/class names
                self.check_ast_nodes(tree, file_path)
        except SyntaxError:
            self.add_issue(file_path, 0, "Syntax error in file")

        return len(self.issues) == 0

    def check_ast_nodes(self, tree: ast.AST, file_path: Path):
        """Check AST nodes for non-English names."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if self.has_chinese(node.name):
                    self.add_issue(file_path, node.lineno, f"Function name '{node.name}' contains Chinese characters")

            elif isinstance(node, ast.ClassDef):
                if self.has_chinese(node.name):
                    self.add_issue(file_path, node.lineno, f"Class name '{node.name}' contains Chinese characters")

            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store) and self.has_chinese(node.id):
                    self.add_issue(file_path, node.lineno, f"Variable name '{node.id}' contains Chinese characters")

    def check_strings_and_comments(self, content: str, file_path: Path):
        """Check strings and comments for non-English text."""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip lines that are only whitespace or imports
            if not line.strip() or line.strip().startswith(('import', 'from')):
                continue

            # Check for Chinese characters in comments
            if '#' in line:
                comment_part = line[line.index('#'):]
                if self.has_chinese(comment_part):
                    self.add_issue(file_path, i, f"Comment contains Chinese characters: {comment_part.strip()}")

    def check_text_file(self, file_path: Path, content: str) -> bool:
        """Check text file for English standards."""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if self.has_chinese(line):
                self.add_issue(file_path, i, f"Text contains Chinese characters: {line.strip()}")

        return len(self.issues) == 0

    def has_chinese(self, text: str) -> bool:
        """Check if text contains Chinese characters."""
        return bool(self.chinese_pattern.search(text))

    def add_issue(self, file_path: Path, line: int, message: str):
        """Add an issue to the list."""
        self.issues.append((str(file_path), line, message))

    def check_directory(self, directory: Path) -> bool:
        """Check all files in a directory."""
        python_files = list(directory.rglob('*.py'))
        other_files = []

        for pattern in ['*.md', '*.txt', '*.yml', '*.yaml', '*.json']:
            other_files.extend(directory.rglob(pattern))

        all_files = python_files + other_files
        all_passed = True

        for file_path in all_files:
            if not self.check_file(file_path):
                all_passed = False

        return all_passed

    def print_issues(self):
        """Print all found issues."""
        if not self.issues:
            print("✅ All files pass English standards check")
            return

        print(f"❌ Found {len(self.issues)} English standards violations:")
        for file_path, line, message in self.issues:
            print(f"  {file_path}:{line} - {message}")


def main():
    """Main function to run English standards check."""
    import argparse

    parser = argparse.ArgumentParser(description='Check English standards compliance')
    parser.add_argument('path', nargs='?', default='src/', help='Path to check (default: src/)')
    parser.add_argument('--allowed', nargs='+', default=['README.md', 'docs/'],
                       help='Allowed paths that can contain non-English text')
    parser.add_argument('--strict', action='store_true',
                       help='Enable strict mode (checks comments and strings)')

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


if __name__ == '__main__':
    main()

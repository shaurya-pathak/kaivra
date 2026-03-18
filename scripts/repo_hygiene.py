#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import tomllib
import yaml

MERGE_MARKERS = ("<<<<<<< ", "=======", ">>>>>>> ", "||||||| ")
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".rst"}
YAML_EXTENSIONS = {".yaml", ".yml"}
TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".markdown",
    ".py",
    ".pyi",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "node_modules",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check repo hygiene and optionally apply safe fixes."
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to inspect.")
    parser.add_argument(
        "--check", action="store_true", help="Report issues without modifying files."
    )
    return parser.parse_args()


def iter_target_files(paths: list[str]) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        if path.is_dir():
            for nested in path.rglob("*"):
                if any(part in IGNORED_DIRS for part in nested.parts):
                    continue
                if nested.is_file():
                    resolved = nested.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        files.append(nested)
            continue
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(path)

    return files


def should_treat_as_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or not path.suffix


def read_text(path: Path) -> str | None:
    if not should_treat_as_text(path):
        return None
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    return data


def normalize_text(path: Path, text: str) -> str:
    lines = text.splitlines()
    strip_trailing = path.suffix.lower() not in MARKDOWN_EXTENSIONS
    normalized_lines = [line.rstrip() if strip_trailing else line for line in lines]
    normalized = "\n".join(normalized_lines)
    if text.endswith("\n") or normalized:
        normalized += "\n"
    return normalized


def validate_structured_text(path: Path, text: str, errors: list[str]) -> None:
    suffix = path.suffix.lower()
    try:
        if suffix in YAML_EXTENSIONS:
            list(yaml.safe_load_all(text))
        elif suffix == ".toml":
            tomllib.loads(text)
    except Exception as exc:  # pragma: no cover - exact parser errors vary
        errors.append(f"{path}: failed to parse {suffix.lstrip('.')} ({exc})")


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    fixed_files: list[Path] = []

    for path in iter_target_files(args.paths):
        text = read_text(path)
        if text is None:
            continue

        for line in text.splitlines():
            if line.startswith(MERGE_MARKERS):
                errors.append(f"{path}: merge conflict marker found")
                break

        validate_structured_text(path, text, errors)

        normalized = normalize_text(path, text)
        if normalized != text:
            if args.check:
                errors.append(f"{path}: trailing whitespace or EOF newline needs normalization")
            else:
                path.write_text(normalized, encoding="utf-8")
                fixed_files.append(path)

    for file_path in fixed_files:
        print(f"fixed {file_path}")
    for error in errors:
        print(error, file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Apply all pending changesets to version.py and clean up changes/.

Each file in changes/*.md has the format:

    bump: minor
    Added support for foo and bar.

Run this script before merging a batch of PRs into main:

    python scripts/apply_changesets.py           # preview
    python scripts/apply_changesets.py --write   # apply

The script:
  1. Reads all changes/*.md files.
  2. Picks the highest bump level (major > minor).
  3. Bumps CURRENT_DSL_VERSION in src/kaivra/version.py.
  4. Prepends a combined entry to DSL_CHANGELOG.
  5. Updates "version" fields in all examples/**/*.json and tests/**/*.py
     to the new version string.
  6. Deletes the processed changeset files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CHANGES_DIR = REPO_ROOT / "changes"
VERSION_FILE = REPO_ROOT / "src" / "kaivra" / "version.py"
EXAMPLE_DIRS = [REPO_ROOT / "examples", REPO_ROOT / "tests"]


# ---------------------------------------------------------------------------
# Changeset parsing
# ---------------------------------------------------------------------------


def _parse_changeset(path: Path) -> tuple[str, str]:
    """Return (bump_level, description) from a changeset file.

    Expected format (leading/trailing blank lines tolerated):

        bump: minor
        Short description of what changed.
    """
    bump: str | None = None
    desc_lines: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if bump is None and stripped.lower().startswith("bump:"):
            bump = stripped.split(":", 1)[1].strip().lower()
        elif stripped:
            desc_lines.append(stripped)

    if bump not in {"minor", "major"}:
        raise ValueError(
            f"{path.name}: 'bump:' must be 'minor' or 'major', got {bump!r}.\n"
            "File must start with 'bump: minor' or 'bump: major'."
        )
    description = " ".join(desc_lines).strip()
    if not description:
        raise ValueError(f"{path.name}: changeset must include a non-empty description.")
    return bump, description


# ---------------------------------------------------------------------------
# Version arithmetic
# ---------------------------------------------------------------------------


def _bump_version(current: str, level: str) -> str:
    """'1.2' + 'minor' → '1.3';  '1.2' + 'major' → '2.0'."""
    parts = current.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Expected DSL version like '1.2', got {current!r}.")
    major, minor = int(parts[0]), int(parts[1])
    if level == "major":
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


# ---------------------------------------------------------------------------
# version.py rewrite
# ---------------------------------------------------------------------------

_CURRENT_VERSION_RE = re.compile(r'(CURRENT_DSL_VERSION\s*=\s*)"[^"]*"')
_CHANGELOG_LIST_RE = re.compile(r"(DSL_CHANGELOG: list\[tuple\[str, str\]\] = \[\n)")


def _rewrite_version_file(source: str, new_version: str, changelog_entry: str) -> str:
    # Bump CURRENT_DSL_VERSION
    if not _CURRENT_VERSION_RE.search(source):
        raise ValueError("Could not find CURRENT_DSL_VERSION in version.py.")
    source = _CURRENT_VERSION_RE.sub(f'\\1"{new_version}"', source)

    # Prepend changelog tuple
    entry_text = f'    (\n        "{new_version}",\n        "{changelog_entry}",\n    ),\n'
    if not _CHANGELOG_LIST_RE.search(source):
        raise ValueError("Could not find DSL_CHANGELOG list in version.py.")
    source = _CHANGELOG_LIST_RE.sub(r"\1" + entry_text, source)

    return source


# ---------------------------------------------------------------------------
# Example / test file version updates
# ---------------------------------------------------------------------------

_JSON_VERSION_RE = re.compile(r'("version"\s*:\s*)"[^"]*"')
_PY_VERSION_FIXTURE_RE = re.compile(r'("version":\s*)"([0-9]+\.[0-9]+)"')


def _update_json_versions(root: Path, new_version: str, dry_run: bool) -> list[Path]:
    updated: list[Path] = []
    for json_file in root.rglob("*.json"):
        text = json_file.read_text(encoding="utf-8")
        new_text, count = _JSON_VERSION_RE.subn(f'\\1"{new_version}"', text)
        if count and new_text != text:
            if not dry_run:
                json_file.write_text(new_text, encoding="utf-8")
            updated.append(json_file)
    return updated


def _update_py_versions(root: Path, new_version: str, dry_run: bool) -> list[Path]:
    updated: list[Path] = []
    for py_file in root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        new_text, count = _PY_VERSION_FIXTURE_RE.subn(f'\\1"{new_version}"', text)
        if count and new_text != text:
            if not dry_run:
                py_file.write_text(new_text, encoding="utf-8")
            updated.append(py_file)
    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply pending changesets and bump the DSL version.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write changes. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()
    dry_run = not args.write

    # ------------------------------------------------------------------
    # Collect changesets
    # ------------------------------------------------------------------
    changesets = sorted(p for p in CHANGES_DIR.glob("*.md") if p.name != ".gitkeep")
    if not changesets:
        print("No changesets found in changes/ — nothing to do.")
        return 0

    print(f"Found {len(changesets)} changeset(s):")
    bump_levels: list[str] = []
    descriptions: list[str] = []
    errors: list[str] = []

    for path in changesets:
        try:
            bump, desc = _parse_changeset(path)
            bump_levels.append(bump)
            descriptions.append(desc)
            print(f"  [{bump:5s}] {path.name}: {desc[:72]}")
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        print("\nChangeset errors:")
        for err in errors:
            print(f"  ERROR: {err}")
        return 1

    # ------------------------------------------------------------------
    # Compute new version
    # ------------------------------------------------------------------
    highest_bump = "major" if "major" in bump_levels else "minor"
    combined_description = "; ".join(descriptions)

    version_source = VERSION_FILE.read_text(encoding="utf-8")
    m = _CURRENT_VERSION_RE.search(version_source)
    if not m:
        print("ERROR: Could not find CURRENT_DSL_VERSION in version.py.", file=sys.stderr)
        return 1

    current_version = m.group(0).split('"')[1]
    new_version = _bump_version(current_version, highest_bump)

    print(f"\nDSL version:  {current_version}  →  {new_version}  ({highest_bump} bump)")
    print(f"Changelog:    {combined_description[:100]}")

    if dry_run:
        print("\n(Dry run — pass --write to apply changes.)")
        return 0

    # ------------------------------------------------------------------
    # Rewrite version.py
    # ------------------------------------------------------------------
    new_source = _rewrite_version_file(version_source, new_version, combined_description)
    VERSION_FILE.write_text(new_source, encoding="utf-8")
    print(f"\nUpdated {VERSION_FILE.relative_to(REPO_ROOT)}")

    # ------------------------------------------------------------------
    # Update example / test version fields
    # ------------------------------------------------------------------
    all_updated: list[Path] = []
    for search_root in EXAMPLE_DIRS:
        if search_root.is_dir():
            all_updated += _update_json_versions(search_root, new_version, dry_run=False)
            all_updated += _update_py_versions(search_root, new_version, dry_run=False)

    if all_updated:
        print(f"Updated version field in {len(all_updated)} file(s):")
        for p in all_updated:
            print(f"  {p.relative_to(REPO_ROOT)}")

    # ------------------------------------------------------------------
    # Delete processed changesets
    # ------------------------------------------------------------------
    for path in changesets:
        path.unlink()
        print(f"Deleted {path.relative_to(REPO_ROOT)}")

    print(f"\nDone — DSL is now at version {new_version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

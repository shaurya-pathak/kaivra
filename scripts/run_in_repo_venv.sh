#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: scripts/run_in_repo_venv.sh <tool> [args...]" >&2
    exit 2
fi

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
GIT_COMMON_DIR="$(git -C "$ROOT_DIR" rev-parse --git-common-dir 2>/dev/null || true)"
SHARED_ROOT=""

if [[ -n "$GIT_COMMON_DIR" ]]; then
    SHARED_ROOT="$(cd -- "${GIT_COMMON_DIR}/.." && pwd)"
fi

resolve_venv_root() {
    if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
        printf '%s\n' "$ROOT_DIR/.venv"
        return 0
    fi
    if [[ -n "$SHARED_ROOT" && -x "$SHARED_ROOT/.venv/bin/python" ]]; then
        printf '%s\n' "$SHARED_ROOT/.venv"
        return 0
    fi
    return 1
}

VENV_ROOT="$(resolve_venv_root || true)"
if [[ -z "$VENV_ROOT" ]]; then
    cat >&2 <<EOF
No repo virtualenv found.
Expected either:
  $ROOT_DIR/.venv
or:
  ${SHARED_ROOT:-<shared-repo-root>}/.venv

Run 'uv sync --extra dev' from the main repo checkout first.
EOF
    exit 1
fi

TOOL="$1"
shift
TOOL_PATH="$VENV_ROOT/bin/$TOOL"

if [[ ! -x "$TOOL_PATH" ]]; then
    echo "Tool '$TOOL' is not installed in $VENV_ROOT." >&2
    exit 1
fi

exec "$TOOL_PATH" "$@"

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${KAIVRA_PRECOMMIT_IMAGE:-kaivra-precommit:py313}"
_WORKSPACE=""  # set in main(); referenced by the EXIT trap
DOCKERFILE_PATH="$ROOT_DIR/docker/precommit.Dockerfile"
BUILD_CONTEXT="$ROOT_DIR/docker"
ENGINE_LABEL=""
ENGINE=()

log() {
    printf '[kaivra-precommit] %s\n' "$*" >&2
}

normalize_path() {
    local candidate
    for candidate in /opt/homebrew/bin /usr/local/bin; do
        if [[ -d "$candidate" && ":$PATH:" != *":$candidate:"* ]]; then
            PATH="$candidate:$PATH"
        fi
    done
    export PATH
}

run_engine() {
    "${ENGINE[@]}" "$@"
}

ensure_colima() {
    if ! command -v colima >/dev/null 2>&1; then
        return 1
    fi

    log "Docker is unavailable; starting Colima."
    colima start >/dev/null
}

select_engine() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        ENGINE=(docker)
        ENGINE_LABEL="docker"
        return 0
    fi

    if ensure_colima; then
        if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
            ENGINE=(docker)
            ENGINE_LABEL="docker via colima"
            return 0
        fi

        if command -v nerdctl >/dev/null 2>&1 && nerdctl info >/dev/null 2>&1; then
            ENGINE=(nerdctl)
            ENGINE_LABEL="nerdctl via colima"
            return 0
        fi
    fi

    if command -v docker >/dev/null 2>&1; then
        cat >&2 <<'EOF'
No working container runtime is available.
Start Docker Desktop, or install Colima plus either Docker CLI or nerdctl.
EOF
    else
        cat >&2 <<'EOF'
No supported container runtime was found.
Install Docker, or install Colima together with Docker CLI or nerdctl.
EOF
    fi
    return 1
}

main() {
    normalize_path
    select_engine
    log "Using ${ENGINE_LABEL}."
    log "Building ${IMAGE_TAG} from ${DOCKERFILE_PATH}."

    run_engine build \
        --tag "$IMAGE_TAG" \
        --file "$DOCKERFILE_PATH" \
        "$BUILD_CONTEXT"

    # Stage the repo under $HOME so Colima (and any other runtime that restricts
    # bind-mount paths) can always reach it. /tmp on macOS is a symlink to
    # /private/tmp which Colima does not mount by default; $HOME is always
    # included in Colima's mount set.
    _WORKSPACE="$(mktemp -d "$HOME/.kaivra-precommit-XXXXXX")"
    trap 'rm -rf "$_WORKSPACE"' EXIT

    log "Staging workspace in ${_WORKSPACE}."
    tar -C "$ROOT_DIR" \
        --exclude='./.venv' \
        --exclude='./__pycache__' \
        --exclude='./.git' \
        --exclude='./artifacts' \
        --exclude='./.pre-commit-cache' \
        -cf - . | tar -C "$_WORKSPACE" -xf -

    local user_args=()
    if command -v id >/dev/null 2>&1; then
        user_args=(--user "$(id -u):$(id -g)")
    fi

    log "Running full pytest suite inside the container."
    run_engine run --rm \
        "${user_args[@]}" \
        --volume "$_WORKSPACE:/workspace" \
        --workdir /workspace \
        --env HOME=/tmp/kaivra-home \
        --env UV_CACHE_DIR=/tmp/uv-cache \
        --env UV_PROJECT_ENVIRONMENT=/tmp/kaivra-precommit-venv \
        --env PYTHONDONTWRITEBYTECODE=1 \
        --env PYTHONPYCACHEPREFIX=/tmp/pycache \
        "$IMAGE_TAG" \
        bash -lc '
            set -euo pipefail
            uv sync --extra dev
            uv pip install --python /tmp/kaivra-precommit-venv/bin/python -e "./packages/kaivra-voice"
            /tmp/kaivra-precommit-venv/bin/pytest -q -p no:cacheprovider tests packages/kaivra-voice/tests
        '
}

main "$@"

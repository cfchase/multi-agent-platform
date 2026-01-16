#!/bin/bash
# Detect available container tool (docker preferred, then podman)
# Outputs the tool name to stdout for use by Makefile or other scripts
#
# Usage:
#   CONTAINER_TOOL=$(./scripts/lib/detect-container-tool.sh)
#
# Override with: export CONTAINER_TOOL=podman (or docker)

# Use timeout to prevent hanging when daemon isn't running
# macOS uses gtimeout from coreutils, Linux uses timeout
if command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_CMD="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
    TIMEOUT_CMD="timeout"
else
    TIMEOUT_CMD=""
fi

check_tool() {
    if [ -n "$TIMEOUT_CMD" ]; then
        $TIMEOUT_CMD 2s "$1" info >/dev/null 2>&1
    else
        "$1" info >/dev/null 2>&1
    fi
}

if check_tool docker; then
    echo "docker"
elif check_tool podman; then
    echo "podman"
else
    echo "docker"  # fallback default
fi

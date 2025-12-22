#!/bin/bash
# Sync VERSION file to pyproject.toml and package.json
#
# This script reads the version from the VERSION file at the repository root
# and updates both backend/pyproject.toml and frontend/package.json to match.

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read version from VERSION file
VERSION_FILE="$REPO_ROOT/VERSION"
if [[ ! -f "$VERSION_FILE" ]]; then
    echo "ERROR: VERSION file not found at $VERSION_FILE"
    exit 1
fi

VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')

if [[ -z "$VERSION" ]]; then
    echo "ERROR: VERSION file is empty"
    exit 1
fi

# Validate version format (basic semver: X.Y.Z)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid version format '$VERSION'. Expected X.Y.Z (e.g., 1.0.0)"
    exit 1
fi

echo "Syncing version: $VERSION"

# Update pyproject.toml
PYPROJECT="$REPO_ROOT/backend/pyproject.toml"
if [[ -f "$PYPROJECT" ]]; then
    # Use sed with backup for portability (works on both macOS and Linux)
    # The 0,/pattern/ range ensures we only replace the first match
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "1,/^version = /s/^version = \".*\"/version = \"$VERSION\"/" "$PYPROJECT"
    else
        sed -i "0,/^version = /s/^version = \".*\"/version = \"$VERSION\"/" "$PYPROJECT"
    fi
    echo "  Updated: backend/pyproject.toml"
else
    echo "  WARNING: $PYPROJECT not found"
fi

# Update package.json
PACKAGE_JSON="$REPO_ROOT/frontend/package.json"
if [[ -f "$PACKAGE_JSON" ]]; then
    # Use jq to update version in package.json
    if command -v jq &> /dev/null; then
        jq ".version = \"$VERSION\"" "$PACKAGE_JSON" > "$PACKAGE_JSON.tmp" && mv "$PACKAGE_JSON.tmp" "$PACKAGE_JSON"
        echo "  Updated: frontend/package.json"
    else
        echo "  WARNING: jq not installed, skipping package.json update"
    fi
else
    echo "  WARNING: $PACKAGE_JSON not found"
fi

# Update uv.lock to reflect the new version
if [[ -f "$PYPROJECT" ]]; then
    echo "  Updating: backend/uv.lock"
    (cd "$REPO_ROOT/backend" && uv lock 2>/dev/null) || echo "  WARNING: uv lock failed (uv may not be installed)"
fi

echo "Version sync complete: $VERSION"

#!/bin/bash
# Bump version in VERSION file and sync to other files
#
# Usage: ./bump-version.sh [patch|minor|major]
#
# Examples:
#   ./bump-version.sh patch  # 1.0.1 → 1.0.2
#   ./bump-version.sh minor  # 1.0.1 → 1.1.0
#   ./bump-version.sh major  # 1.0.1 → 2.0.0

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TYPE=$1

if [[ -z "$TYPE" ]]; then
    echo "Usage: $0 [patch|minor|major]"
    echo ""
    echo "Examples:"
    echo "  $0 patch  # 1.0.1 → 1.0.2 (bug fixes)"
    echo "  $0 minor  # 1.0.1 → 1.1.0 (new features)"
    echo "  $0 major  # 1.0.1 → 2.0.0 (breaking changes)"
    exit 1
fi

# Read current version
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

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

if [[ -z "$MAJOR" || -z "$MINOR" || -z "$PATCH" ]]; then
    echo "ERROR: Invalid version format '$VERSION'. Expected X.Y.Z"
    exit 1
fi

# Bump version based on type
case $TYPE in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
    *)
        echo "ERROR: Invalid type '$TYPE'. Use patch, minor, or major."
        exit 1
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Write new version
echo "$NEW_VERSION" > "$VERSION_FILE"
echo "Bumped version: $VERSION → $NEW_VERSION"

# Sync to other files
"$SCRIPT_DIR/sync-version.sh"

echo ""
echo "Next steps:"
echo "  git add VERSION backend/pyproject.toml backend/uv.lock frontend/package.json"
echo "  git commit -m \"chore: bump version to $NEW_VERSION\""

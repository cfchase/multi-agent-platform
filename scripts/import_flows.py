#!/usr/bin/env python3
"""
Import flows from configured sources into LangFlow.

Usage:
    python scripts/import_flows.py [config-file]

Environment variables:
    LANGFLOW_URL      - LangFlow API URL (default: http://localhost:7860)
    LANGFLOW_API_KEY  - LangFlow API key (optional)
    FLOW_SOURCE_PATH  - Simple mode: single local path to import
    GITHUB_FLOW_TOKEN - Token for private git repos
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import requests
import yaml

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "flow-sources.yaml"
LANGFLOW_URL = os.environ.get("LANGFLOW_URL", "http://localhost:7860")
LANGFLOW_USER = os.environ.get("LANGFLOW_USER", "admin")
LANGFLOW_PASSWORD = os.environ.get("LANGFLOW_PASSWORD", "admin")
CACHE_DIR = Path(os.environ.get("FLOW_CACHE_DIR", "/tmp/flow-cache"))

# Global access token
ACCESS_TOKEN: str | None = None


def log_info(msg: str) -> None:
    print(f"\033[0;32m[INFO]\033[0m {msg}")


def log_warn(msg: str) -> None:
    print(f"\033[1;33m[WARN]\033[0m {msg}")


def log_error(msg: str) -> None:
    print(f"\033[0;31m[ERROR]\033[0m {msg}")


def authenticate() -> bool:
    """Authenticate with LangFlow and get access token."""
    global ACCESS_TOKEN

    # Check for API key first
    api_key = os.environ.get("LANGFLOW_API_KEY")
    if api_key:
        ACCESS_TOKEN = api_key
        log_info("Using API key from LANGFLOW_API_KEY")
        return True

    log_info(f"Authenticating as {LANGFLOW_USER}...")
    try:
        resp = requests.post(
            f"{LANGFLOW_URL}/api/v1/login",
            data={"username": LANGFLOW_USER, "password": LANGFLOW_PASSWORD},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            ACCESS_TOKEN = data.get("access_token")
            if ACCESS_TOKEN:
                log_info("Authentication successful")
                return True
        log_error(f"Authentication failed: {resp.text[:200]}")
        return False
    except requests.RequestException as e:
        log_error(f"Authentication request failed: {e}")
        return False


def check_langflow() -> bool:
    """Check if LangFlow is accessible and optionally authenticate."""
    log_info(f"Checking LangFlow connectivity at {LANGFLOW_URL}...")
    try:
        resp = requests.get(f"{LANGFLOW_URL}/health", timeout=5)
        if resp.ok:
            log_info("LangFlow is accessible")
            # Try API without auth first (works with LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true)
            test_resp = requests.get(f"{LANGFLOW_URL}/api/v1/flows/", timeout=5)
            if test_resp.ok:
                log_info("API accessible without authentication (auto-login mode)")
                return True
            # If API requires auth, try to authenticate
            return authenticate()
    except requests.RequestException:
        pass
    log_error(f"Cannot connect to LangFlow at {LANGFLOW_URL}")
    log_error("Make sure LangFlow is running (make langflow-start)")
    return False


def import_flow(json_file: Path) -> bool:
    """Import a single flow JSON file to LangFlow."""
    flow_name = json_file.stem
    log_info(f"Importing flow: {flow_name}")

    try:
        with open(json_file) as f:
            flow_data = json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"  Invalid JSON in {json_file}: {e}")
        return False

    headers = {"Content-Type": "application/json"}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    try:
        resp = requests.post(
            f"{LANGFLOW_URL}/api/v1/flows/",
            headers=headers,
            json=flow_data,
            timeout=30,
        )
        if resp.ok and "id" in resp.text:
            log_info(f"  ✓ Imported: {flow_name}")
            return True
        else:
            log_warn(f"  Could not import {flow_name} (may already exist)")
            log_warn(f"  Response: {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        log_error(f"  Request failed: {e}")
        return False


def import_from_directory(directory: Path, source_name: str) -> int:
    """Scan a directory and import all flow JSON files."""
    if not directory.is_dir():
        log_warn(f"Directory not found: {directory}")
        return 0

    log_info(f"Scanning directory: {directory}")

    count = 0
    for json_file in directory.glob("*.json"):
        if import_flow(json_file):
            count += 1

    log_info(f"Imported {count} flow(s) from {source_name}")
    return count


def sync_git_repo(url: str, branch: str, name: str, token: str | None = None) -> Path | None:
    """Clone or pull a git repository."""
    repo_dir = CACHE_DIR / name
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Build authenticated URL if token provided
    clone_url = url
    if token and "github.com" in url:
        clone_url = url.replace("https://github.com", f"https://{token}@github.com")

    if (repo_dir / ".git").is_dir():
        log_info(f"Pulling updates for {name}...")
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log_warn(f"Pull failed, using cached version: {result.stderr}")
    else:
        log_info(f"Cloning {url} (branch: {branch})...")
        result = subprocess.run(
            ["git", "clone", "--branch", branch, "--depth", "1", clone_url, str(repo_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log_error(f"Failed to clone {url}: {result.stderr}")
            return None

    return repo_dir


def import_from_config(config_file: Path) -> None:
    """Parse YAML config and import flows."""
    if not config_file.exists():
        log_warn(f"Config file not found: {config_file}")
        return

    log_info(f"Reading config: {config_file}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    sources = config.get("flow_sources", [])
    if not sources:
        log_warn("No flow sources configured")
        return

    log_info(f"Found {len(sources)} flow source(s)")

    for source in sources:
        name = source.get("name", "unnamed")
        source_type = source.get("type", "local")
        enabled = source.get("enabled", True)

        if not enabled:
            log_info(f"Skipping disabled source: {name}")
            continue

        log_info(f"Processing source: {name} (type: {source_type})")

        if source_type == "git":
            url = source.get("url")
            branch = source.get("branch", "main")
            path = source.get("path", "flows")

            # Get token from environment if specified
            token = None
            auth_config = source.get("auth", {})
            env_var = auth_config.get("env_var")
            if env_var:
                token = os.environ.get(env_var)
                if not token:
                    log_warn(f"Auth env var {env_var} is not set, trying without auth")

            repo_dir = sync_git_repo(url, branch, name, token)
            if repo_dir:
                flow_path = repo_dir / path
                if flow_path.is_dir():
                    import_from_directory(flow_path, name)
                else:
                    log_error(f"Flow path not found: {flow_path}")

        elif source_type == "local":
            path = Path(source.get("path", ""))
            if not path.is_absolute():
                path = PROJECT_ROOT / path

            if path.is_dir():
                import_from_directory(path, name)
            else:
                log_error(f"Local path not found: {path}")

        else:
            log_warn(f"Unknown source type: {source_type}")

        print()


def main() -> None:
    print("=" * 40)
    print("LangFlow Flow Importer")
    print("=" * 40)
    print()

    if not check_langflow():
        sys.exit(1)

    print()

    # Check for simple mode (FLOW_SOURCE_PATH env var)
    simple_path = os.environ.get("FLOW_SOURCE_PATH")
    if simple_path:
        log_info(f"Simple mode: importing from {simple_path}")
        import_from_directory(Path(simple_path), "local")
        return

    # Check for config file argument or default
    config_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG

    if config_file.exists():
        import_from_config(config_file)
    else:
        # Default: import from built-in examples
        log_info("No config found, importing built-in examples...")
        examples_dir = PROJECT_ROOT / "langflow-flows" / "examples"
        import_from_directory(examples_dir, "examples")

    print()
    print("=" * 40)
    print("Import complete!")
    print("=" * 40)


if __name__ == "__main__":
    main()

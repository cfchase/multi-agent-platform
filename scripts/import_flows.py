#!/usr/bin/env python3
"""
Import flows from configured sources into LangFlow.

Usage:
    python scripts/import_flows.py [config-file]

Environment variables:
    LANGFLOW_URL      - LangFlow API URL (default: http://localhost:7860)
    LANGFLOW_USER     - LangFlow username (default: dev@localhost.local)
    LANGFLOW_PASSWORD - LangFlow password (default: devpassword123)
    LANGFLOW_API_KEY  - LangFlow API key (optional, overrides user/password)
    FLOW_SOURCE_PATH  - Simple mode: single local path to import
    GITHUB_FLOW_TOKEN - Token for private git repos

Config options per source:
    project           - LangFlow project name to import flows into
    pattern           - Glob pattern for finding flow files (default: **/*.json)
    public            - Set to true to make flows visible to all users
"""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "flow-sources.yaml"
LANGFLOW_URL = os.environ.get("LANGFLOW_URL", "http://localhost:7860")
LANGFLOW_USER = os.environ.get("LANGFLOW_USER", "dev@localhost.local")
LANGFLOW_PASSWORD = os.environ.get("LANGFLOW_PASSWORD", "devpassword123")
CACHE_DIR = Path(os.environ.get("FLOW_CACHE_DIR", "/tmp/flow-cache"))

# Component installation paths (relative to project root)
COMPONENTS_DIR = Path(os.environ.get("LANGFLOW_COMPONENTS_DIR", str(PROJECT_ROOT / ".local" / "langflow" / "components")))
PACKAGES_DIR = Path(os.environ.get("LANGFLOW_PACKAGES_DIR", str(PROJECT_ROOT / ".local" / "langflow" / "packages")))

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds, doubles each retry

# URL validation - allowed hosts for file imports
ALLOWED_URL_HOSTS = {
    "github.com",
    "raw.githubusercontent.com",
    "gitlab.com",
    "bitbucket.org",
}

# Blocked hosts to prevent SSRF
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",  # GCP metadata
}

# Global access token
ACCESS_TOKEN: str | None = None

# Cache for project name -> ID lookups
PROJECT_CACHE: dict[str, str] = {}


def log_info(msg: str) -> None:
    print(f"\033[0;32m[INFO]\033[0m {msg}")


def log_warn(msg: str) -> None:
    print(f"\033[1;33m[WARN]\033[0m {msg}")


def log_error(msg: str) -> None:
    print(f"\033[0;31m[ERROR]\033[0m {msg}")


def sanitize_token(text: str, token: str | None) -> str:
    """Remove sensitive tokens from text before logging."""
    if token and token in text:
        return text.replace(token, "***")
    return text


def validate_url(url: str) -> bool:
    """Validate URL to prevent SSRF attacks."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            log_error(f"Invalid URL scheme: {parsed.scheme}")
            return False
        if parsed.hostname in BLOCKED_HOSTS:
            log_error(f"Blocked host: {parsed.hostname}")
            return False
        # For strict mode, could enforce ALLOWED_URL_HOSTS
        # if parsed.hostname not in ALLOWED_URL_HOSTS:
        #     log_error(f"Host not in allowed list: {parsed.hostname}")
        #     return False
        return True
    except Exception as e:
        log_error(f"Invalid URL: {e}")
        return False


def validate_path(base: Path, user_path: str) -> Path | None:
    """Validate path to prevent path traversal attacks."""
    try:
        # Resolve the path and check it's within the base
        if Path(user_path).is_absolute():
            resolved = Path(user_path).resolve()
        else:
            resolved = (base / user_path).resolve()

        # For absolute paths, just ensure they exist and are safe
        # For relative paths, ensure they stay within project root
        if not Path(user_path).is_absolute():
            if not resolved.is_relative_to(base):
                log_error(f"Path traversal attempt blocked: {user_path}")
                return None
        return resolved
    except Exception as e:
        log_error(f"Invalid path: {e}")
        return None


def request_with_retry(
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response | None:
    """Make HTTP request with exponential backoff retry."""
    delay = RETRY_DELAY
    last_error = None

    for attempt in range(max_retries):
        try:
            resp = requests.request(method, url, **kwargs)
            return resp
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries - 1:
                log_warn(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff

    log_error(f"Request failed after {max_retries} attempts: {last_error}")
    return None


def find_component_classes(filepath: Path) -> list[str]:
    """Find classes that inherit from Component in a Python file.

    Scans the AST for class definitions that have a base class containing
    'Component' in the name (e.g., Component, CustomComponent).
    """
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
    except (SyntaxError, OSError) as e:
        log_warn(f"Could not parse {filepath}: {e}")
        return []

    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if "Component" in base_name:
                    classes.append(node.name)
                    break
    return classes


def generate_init_py(category_dir: Path) -> int:
    """Generate __init__.py that imports all component classes in the category.

    Returns the number of component classes found.
    """
    imports = []
    all_classes = []

    for py_file in category_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        module_name = py_file.stem
        classes = find_component_classes(py_file)

        for cls in classes:
            imports.append(f"from .{module_name} import {cls}")
            all_classes.append(cls)

    if not all_classes:
        log_warn(f"No component classes found in {category_dir}")
        return 0

    init_content = "# Auto-generated by import_flows.py\n"
    init_content += "\n".join(sorted(imports))
    init_content += "\n\n__all__ = [\n"
    init_content += "".join(f'    "{cls}",\n' for cls in sorted(all_classes))
    init_content += "]\n"

    init_file = category_dir / "__init__.py"
    with open(init_file, "w") as f:
        f.write(init_content)

    log_info(f"  Generated {init_file.name} with {len(all_classes)} component(s)")
    return len(all_classes)


def install_dependencies(dependencies: list[str], target_dir: Path) -> bool:
    """Install pip dependencies to the target directory.

    Returns True if all dependencies installed successfully.
    """
    if not dependencies:
        return True

    target_dir.mkdir(parents=True, exist_ok=True)

    log_info(f"  Installing {len(dependencies)} pip dependency(ies)...")

    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", str(target_dir),
        "--upgrade",
        "--quiet"
    ] + dependencies

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log_error(f"  pip install failed: {result.stderr}")
            return False
        log_info(f"  Dependencies installed to {target_dir}")
        return True
    except Exception as e:
        log_error(f"  pip install error: {e}")
        return False


def install_components(source: dict) -> bool:
    """Install components from a source entry.

    Handles:
    1. pip install dependencies to PACKAGES_DIR
    2. Copy .py files to COMPONENTS_DIR/{category}/
    3. Generate __init__.py for the category

    Returns True if successful.
    """
    name = source.get("name", "unnamed")
    path_str = source.get("path", "")
    category = source.get("category", "custom")
    dependencies = source.get("dependencies", [])

    # Validate source path
    source_path = validate_path(PROJECT_ROOT, path_str)
    if source_path is None:
        return False

    if not source_path.is_dir():
        log_error(f"Component source path not found: {source_path}")
        return False

    log_info(f"Installing components from: {source_path}")
    log_info(f"  Category: {category}")

    # Step 1: Install pip dependencies
    if dependencies:
        if not install_dependencies(dependencies, PACKAGES_DIR):
            log_warn(f"  Some dependencies failed to install")

    # Step 2: Create category directory
    category_dir = COMPONENTS_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)

    # Step 3: Copy component files
    py_files = list(source_path.glob("*.py"))
    if not py_files:
        log_warn(f"  No .py files found in {source_path}")
        return False

    copied = 0
    for py_file in py_files:
        if py_file.name == "__init__.py":
            continue
        dest = category_dir / py_file.name
        shutil.copy2(py_file, dest)
        log_info(f"  Copied: {py_file.name}")
        copied += 1

    if copied == 0:
        log_warn(f"  No component files copied")
        return False

    # Step 4: Generate __init__.py
    component_count = generate_init_py(category_dir)

    log_info(f"Installed {copied} file(s), {component_count} component(s) for '{name}'")
    return component_count > 0


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
    resp = request_with_retry(
        "POST",
        f"{LANGFLOW_URL}/api/v1/login",
        data={"username": LANGFLOW_USER, "password": LANGFLOW_PASSWORD},
        timeout=10,
    )
    if resp is None:
        return False

    if resp.ok:
        try:
            data = resp.json()
            ACCESS_TOKEN = data.get("access_token")
            if ACCESS_TOKEN:
                log_info("Authentication successful")
                return True
        except json.JSONDecodeError:
            pass
    log_error(f"Authentication failed: {resp.text[:200]}")
    return False


def list_all_flows() -> list[dict] | None:
    """List all flows from LangFlow.

    Returns list of flow objects with id, name, folder_id, etc.
    Returns None on error.
    """
    headers = {}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    resp = request_with_retry(
        "GET",
        f"{LANGFLOW_URL}/api/v1/flows/",
        headers=headers,
        params={"get_all": True},
        timeout=30,
    )

    if resp is None:
        return None

    if resp.ok:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            log_error(f"Failed to parse flows response: {e}")
            return None

    log_error(f"Failed to list flows: {resp.status_code}")
    return None


def delete_flow(flow_id: str) -> bool:
    """Delete a flow by ID.

    Returns True if deleted successfully.
    """
    headers = {"Content-Type": "application/json"}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    resp = request_with_retry(
        "DELETE",
        f"{LANGFLOW_URL}/api/v1/flows",
        headers=headers,
        json=[flow_id],  # API expects a list of IDs
        timeout=10,
    )

    if resp is None:
        return False

    if resp.ok:
        return True

    log_warn(f"Failed to delete flow {flow_id[:8]}...: {resp.status_code}")
    return False


def find_flow_by_name(flows: list[dict], name: str, project_id: str | None = None) -> dict | None:
    """Find a flow by name, optionally within a specific project.

    Args:
        flows: List of flow objects from list_all_flows()
        name: Flow name to search for
        project_id: Optional folder_id to filter by

    Returns the flow dict if found, None otherwise.
    """
    for flow in flows:
        if flow.get("name") == name:
            if project_id is None or flow.get("folder_id") == project_id:
                return flow
    return None


def create_project(project_name: str) -> str | None:
    """Create a new project and return its ID."""
    headers = {"Content-Type": "application/json"}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    resp = request_with_retry(
        "POST",
        f"{LANGFLOW_URL}/api/v1/projects/",
        headers=headers,
        json={"name": project_name, "description": ""},
        timeout=10,
    )
    if resp is None:
        return None

    if resp.ok:
        try:
            project = resp.json()
            project_id = project["id"]
            PROJECT_CACHE[project_name] = project_id
            log_info(f"Created project '{project_name}' (ID: {project_id[:8]}...)")
            return project_id
        except (json.JSONDecodeError, KeyError) as e:
            log_error(f"Failed to parse project response: {e}")
            return None
    else:
        log_error(f"Failed to create project '{project_name}': {resp.text[:200]}")
        return None


def get_project_id(project_name: str, create_if_missing: bool = True) -> str | None:
    """Look up a project by name and return its ID. Creates the project if not found."""
    if project_name in PROJECT_CACHE:
        return PROJECT_CACHE[project_name]

    headers = {}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    resp = request_with_retry(
        "GET",
        f"{LANGFLOW_URL}/api/v1/projects/",
        headers=headers,
        timeout=10,
    )
    if resp is None:
        return None

    if resp.ok:
        try:
            projects = resp.json()
            for project in projects:
                # Cache all projects while we're here
                PROJECT_CACHE[project["name"]] = project["id"]

            if project_name in PROJECT_CACHE:
                log_info(f"Found project '{project_name}' (ID: {PROJECT_CACHE[project_name][:8]}...)")
                return PROJECT_CACHE[project_name]
            elif create_if_missing:
                log_info(f"Project '{project_name}' not found, creating it...")
                return create_project(project_name)
            else:
                log_warn(f"Project '{project_name}' not found")
                log_warn(f"Available projects: {', '.join(p['name'] for p in projects)}")
                return None
        except (json.JSONDecodeError, KeyError) as e:
            log_error(f"Failed to parse projects response: {e}")
            return None
    return None


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


def import_flow_data(
    flow_data: dict,
    flow_name: str,
    project_id: str | None = None,
    public: bool = False,
) -> bool:
    """Import flow data to LangFlow."""
    headers = {"Content-Type": "application/json"}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"

    # Add project (folder_id) if specified
    if project_id:
        flow_data = {**flow_data, "folder_id": project_id}

    # Set access type
    if public:
        flow_data = {**flow_data, "access_type": "PUBLIC"}

    resp = request_with_retry(
        "POST",
        f"{LANGFLOW_URL}/api/v1/flows/",
        headers=headers,
        json=flow_data,
        timeout=30,
    )
    if resp is None:
        return False

    if resp.ok and "id" in resp.text:
        log_info(f"  ✓ Imported: {flow_name}")
        return True
    elif resp.status_code == 409:
        # Conflict - flow already exists
        log_info(f"  ○ Skipped (already exists): {flow_name}")
        return True  # Not a failure
    else:
        log_warn(f"  Could not import {flow_name}: {resp.status_code}")
        log_warn(f"  Response: {resp.text[:200]}")
        return False


def import_flow(
    json_file: Path, project_id: str | None = None, public: bool = False
) -> bool:
    """Import a single flow JSON file to LangFlow."""
    flow_name = json_file.stem
    log_info(f"Importing flow: {flow_name}")

    try:
        with open(json_file) as f:
            flow_data = json.load(f)
    except json.JSONDecodeError as e:
        log_error(f"  Invalid JSON in {json_file}: {e}")
        return False
    except OSError as e:
        log_error(f"  Failed to read {json_file}: {e}")
        return False

    return import_flow_data(flow_data, flow_name, project_id, public)


def import_from_url(
    url: str, name: str, project_id: str | None = None, public: bool = False
) -> bool:
    """Import a flow from a URL."""
    # Validate URL before fetching
    if not validate_url(url):
        return False

    log_info(f"Fetching flow from: {url}")

    resp = request_with_retry("GET", url, timeout=30)
    if resp is None:
        return False

    if not resp.ok:
        log_error(f"  Failed to fetch {url}: {resp.status_code}")
        return False

    try:
        flow_data = resp.json()
    except json.JSONDecodeError as e:
        log_error(f"  Invalid JSON from {url}: {e}")
        return False

    return import_flow_data(flow_data, name, project_id, public)


def import_from_directory(
    directory: Path,
    source_name: str,
    pattern: str = "**/*.json",
    project_id: str | None = None,
    public: bool = False,
) -> int:
    """Scan a directory and import flow JSON files matching pattern."""
    if not directory.is_dir():
        log_warn(f"Directory not found: {directory}")
        return 0

    log_info(f"Scanning directory: {directory} (pattern: {pattern})")

    files = list(directory.glob(pattern))
    if not files:
        log_warn(f"No files matching pattern '{pattern}' in {directory}")
        return 0

    count = 0
    for json_file in files:
        # Skip non-files (directories, symlinks to directories)
        if not json_file.is_file():
            continue
        if import_flow(json_file, project_id, public):
            count += 1

    log_info(f"Imported {count} flow(s) from {source_name}")
    return count


def sync_git_repo(url: str, branch: str, name: str, token: str | None = None) -> Path | None:
    """Clone or pull a git repository."""
    repo_dir = CACHE_DIR / name

    # Create cache directory with secure permissions
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CACHE_DIR, stat.S_IRWXU)  # 0o700 - owner only
    except OSError:
        pass  # Best effort

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
            # Sanitize stderr to remove any token exposure
            sanitized_err = sanitize_token(result.stderr, token)
            log_warn(f"Pull failed, using cached version: {sanitized_err}")
    else:
        log_info(f"Cloning {url} (branch: {branch})...")
        result = subprocess.run(
            ["git", "clone", "--branch", branch, "--depth", "1", clone_url, str(repo_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Sanitize stderr to remove any token exposure
            sanitized_err = sanitize_token(result.stderr, token)
            log_error(f"Failed to clone {url}: {sanitized_err}")
            return None

    return repo_dir


def import_from_config(config_file: Path) -> tuple[int, int]:
    """Parse YAML config and import flows. Returns (success_count, failure_count)."""
    if not config_file.exists():
        log_warn(f"Config file not found: {config_file}")
        return 0, 0

    log_info(f"Reading config: {config_file}")

    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        log_error(f"Invalid YAML in {config_file}: {e}")
        return 0, 0
    except OSError as e:
        log_error(f"Failed to read {config_file}: {e}")
        return 0, 0

    if config is None:
        log_warn("Empty config file")
        return 0, 0

    sources = config.get("flow_sources", [])
    if not sources:
        log_warn("No flow sources configured")
        return 0, 0

    # Separate component sources from flow sources
    component_sources = []
    flow_sources = []
    for source in sources:
        if source.get("type") == "components":
            component_sources.append(source)
        else:
            flow_sources.append(source)

    log_info(f"Found {len(sources)} source(s): {len(component_sources)} component(s), {len(flow_sources)} flow(s)")

    total_success = 0
    total_failure = 0
    components_installed = False

    # Pass 1: Process component sources first
    if component_sources:
        log_info("")
        log_info("=== Installing Components ===")
        for source in component_sources:
            name = source.get("name", "unnamed")
            enabled = source.get("enabled", True)

            if not enabled:
                log_info(f"Skipping disabled component source: {name}")
                continue

            log_info(f"Processing component source: {name}")
            if install_components(source):
                components_installed = True
            else:
                total_failure += 1
            print()

        if components_installed:
            log_info("NOTE: Restart LangFlow to load new components")
            print()

    # Pass 2: Process flow sources
    if flow_sources:
        log_info("=== Importing Flows ===")

    for source in flow_sources:
        name = source.get("name", "unnamed")
        source_type = source.get("type", "local")
        enabled = source.get("enabled", True)

        if not enabled:
            log_info(f"Skipping disabled source: {name}")
            continue

        log_info(f"Processing source: {name} (type: {source_type})")

        # Look up project ID if specified
        project_id = None
        project_name = source.get("project")
        if project_name:
            project_id = get_project_id(project_name)
            if not project_id:
                log_warn(f"Skipping source '{name}' - project not found")
                total_failure += 1
                continue

        # Check if flows should be public
        public = source.get("public", False)

        if source_type == "file":
            # Single file: local path or URL
            path = source.get("path", "")
            if path.startswith(("http://", "https://")):
                if import_from_url(path, name, project_id, public):
                    total_success += 1
                else:
                    total_failure += 1
            else:
                file_path = validate_path(PROJECT_ROOT, path)
                if file_path is None:
                    total_failure += 1
                elif file_path.is_file():
                    if import_flow(file_path, project_id, public):
                        total_success += 1
                    else:
                        total_failure += 1
                else:
                    log_error(f"File not found: {file_path}")
                    total_failure += 1

        elif source_type == "git":
            url = source.get("url")
            branch = source.get("branch", "main")
            pattern = source.get("pattern", "**/*.json")

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
                count = import_from_directory(repo_dir, name, pattern, project_id, public)
                total_success += count

        elif source_type == "local":
            path_str = source.get("path", "")
            pattern = source.get("pattern", "**/*.json")
            path = validate_path(PROJECT_ROOT, path_str)

            if path is None:
                total_failure += 1
            elif path.is_dir():
                count = import_from_directory(path, name, pattern, project_id, public)
                total_success += count
            else:
                log_error(f"Local path not found: {path}")
                total_failure += 1

        else:
            log_warn(f"Unknown source type: {source_type}")

        print()

    return total_success, total_failure


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
        success, failure = import_from_config(config_file)
        print()
        print("=" * 40)
        print(f"Import complete! ({success} succeeded, {failure} failed)")
        print("=" * 40)
        if failure > 0:
            sys.exit(1)
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

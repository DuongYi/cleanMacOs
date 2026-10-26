"""Configuration and ignore rules for mclean."""

import json
from pathlib import Path
from typing import Set

CONFIG_DIR = Path.home() / ".config" / "mclean"
CONFIG_FILE = CONFIG_DIR / "config.json"
IGNORE_FILE = CONFIG_DIR / "ignore.json"

DEFAULT_PROJECT_ROOTS = [
    Path.home() / "Projects",
    Path.home() / "Code",
    Path.home() / "dev",
    Path.home() / "development",
    Path.home() / "Workspace",
    Path.home() / "GitHub",
    Path.home() / "Desktop",
]

# Blacklisted paths that mclean will NEVER delete
PERMANENT_BLACKLIST = {
    Path.home() / ".pub-cache" / "hosted",
    Path.home() / ".gradle" / "caches" / "modules-2",
    Path.home() / "Library" / "Developer" / "CoreSimulator" / "Devices",
    Path.home() / ".android" / "avd",
    Path.home() / ".ssh",
    Path.home() / ".gnupg",
    Path("/System"),
    Path("/Applications"),
    Path("/Library"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
}

DEFAULT_INACTIVE_DAYS = 14


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_ignored_paths() -> Set[Path]:
    """Load user-defined ignore paths from ~/.config/mclean/ignore.json."""
    if not IGNORE_FILE.exists():
        return set()
    try:
        with open(IGNORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {Path(p).expanduser().resolve() for p in data.get("ignored", [])}
    except Exception:
        return set()


def save_ignored_paths(ignored: Set[Path]):
    """Save user-defined ignore paths to ~/.config/mclean/ignore.json."""
    ensure_config_dir()
    with open(IGNORE_FILE, "w", encoding="utf-8") as f:
        json.dump({"ignored": [str(p) for p in sorted(ignored)]}, f, indent=2)


def is_path_protected(path: Path) -> bool:
    """Check if a path is blacklisted or in the user's ignore list."""
    resolved = path.expanduser().resolve()

    # Check permanent blacklist
    for bl in PERMANENT_BLACKLIST:
        if resolved == bl or bl in resolved.parents:
            return True

    # Check user ignore list
    user_ignored = load_ignored_paths()
    for ig in user_ignored:
        if resolved == ig or ig in resolved.parents:
            return True

    return False

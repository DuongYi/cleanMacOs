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


# Directories that must never be removed as a whole (their contents may be)
CRITICAL_ROOTS = {
    Path("/"),
    Path("/Users"),
    Path.home(),
    Path.home() / "Library",
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Developer",
}

# Inside ~/.android/avd only these entries are disposable; everything else is device data
AVD_DISPOSABLE_NAMES = {"snapshots"}
AVD_DISPOSABLE_PREFIXES = ("cache.img",)


def _is_avd_disposable(resolved: Path) -> bool:
    """True for snapshots/ and cache.img* directly inside an *.avd folder."""
    parent = resolved.parent
    if not parent.name.endswith(".avd") or parent.parent != (Path.home() / ".android" / "avd").resolve():
        return False
    return resolved.name in AVD_DISPOSABLE_NAMES or resolved.name.startswith(AVD_DISPOSABLE_PREFIXES)


def _matches_guard(resolved: Path, guarded: Path) -> bool:
    """A path is guarded if it is the guarded path, inside it, or one of its ancestors."""
    guarded = guarded.expanduser().resolve()
    return resolved == guarded or guarded in resolved.parents or resolved in guarded.parents


def is_path_ignored(path: Path) -> bool:
    """True if the path is on, or inside, the user's ignore list. Used to decide what to scan at all."""
    resolved = path.expanduser().resolve()
    return any(resolved == ig or ig in resolved.parents for ig in load_ignored_paths())


def is_path_protected(path: Path) -> bool:
    """Check if a path is blacklisted or in the user's ignore list.

    Deleting an ancestor of a protected path would delete the protected path too,
    so ancestors are protected as well.
    """
    resolved = path.expanduser().resolve()

    if resolved in {r.resolve() for r in CRITICAL_ROOTS}:
        return True

    # Check user ignore list
    for ig in load_ignored_paths():
        if _matches_guard(resolved, ig):
            return True

    if _is_avd_disposable(resolved):
        return False

    # Check permanent blacklist
    for bl in PERMANENT_BLACKLIST:
        if _matches_guard(resolved, bl):
            return True

    return False

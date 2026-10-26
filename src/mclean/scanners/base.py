"""Abstract base class for all mclean scanners."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple

from mclean.models import Category, CleanTarget
from mclean.utils.disk import safe_delete_path
import subprocess


class BaseScanner(ABC):
    """Abstract scanner defining discovery and cleanup interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scanner."""
        pass

    @property
    @abstractmethod
    def category(self) -> Category:
        """Category this scanner belongs to."""
        pass

    @abstractmethod
    def scan(self) -> List[CleanTarget]:
        """Perform discovery and return clean targets."""
        pass

    def clean(self, target: CleanTarget, dry_run: bool = False) -> Tuple[bool, str]:
        """Execute cleanup for a specific target."""
        return clean_target(target, dry_run=dry_run)


def clean_target(target: CleanTarget, dry_run: bool = False) -> Tuple[bool, str]:
    """Execute cleanup for a target produced by any scanner."""
    if target.item_type == "command" and target.clean_command:
        if dry_run:
            return True, f"[Dry-run] Would execute: {' '.join(target.clean_command)}"
        try:
            res = subprocess.run(target.clean_command, capture_output=True, text=True, timeout=600)
            if res.returncode == 0:
                return True, f"Command succeeded: {' '.join(target.clean_command)}"
            else:
                return False, f"Command failed: {res.stderr.strip() or res.stdout.strip()}"
        except Exception as e:
            return False, f"Error executing command: {e}"

    # Several paths belonging to one target (e.g. build/ and .dart_tool/flutter_build/)
    if target.item_type == "paths":
        return _delete_all(target.metadata.get("paths", [target.path]), dry_run)

    # Everything inside a folder that must itself stay (e.g. ~/.Trash, ~/Library/Logs)
    if target.item_type == "contents":
        excluded = set(target.metadata.get("exclude", []))
        try:
            children = [c for c in target.path.iterdir() if c.name not in excluded]
        except PermissionError:
            return False, f"Permission denied reading {target.path}. Grant Full Disk Access to your terminal."
        except OSError as e:
            return False, f"Error reading {target.path}: {e}"
        return _delete_all(children, dry_run)

    # Standard file or directory removal
    return safe_delete_path(target.path, dry_run=dry_run)


def _delete_all(paths: List[Path], dry_run: bool) -> Tuple[bool, str]:
    """Delete each path; succeed only if every deletion succeeded."""
    failures = []
    for p in paths:
        ok, msg = safe_delete_path(p, dry_run=dry_run)
        if not ok:
            failures.append(msg)
    if failures:
        return False, "; ".join(failures[:3])
    return True, f"Deleted {len(paths)} item(s)"

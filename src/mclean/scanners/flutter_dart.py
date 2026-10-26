"""Flutter & Dart project artifacts and pub-cache scanner."""

import os
import time
from pathlib import Path
from typing import List, Optional

from mclean.config import DEFAULT_INACTIVE_DAYS, DEFAULT_PROJECT_ROOTS, is_path_protected
from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_path_size
from mclean.utils.formatters import format_timestamp

IGNORED_DIR_NAMES = {
    ".git", ".pub-cache", ".dart_tool", "Pods", "node_modules",
    "build", "DerivedData", ".gradle", "flutter", "cache", "sdk",
    "Library", ".Trash", "Caches", "Application Support",
}


class FlutterDartScanner(BaseScanner):
    """Scans inactive Flutter projects (>14 days) and safe pub-cache components."""

    def __init__(self, workspace_roots: Optional[List[Path]] = None, inactive_days: int = DEFAULT_INACTIVE_DAYS):
        self.workspace_roots = workspace_roots or [r for r in DEFAULT_PROJECT_ROOTS if r.exists()]
        self.inactive_days = inactive_days

    @property
    def name(self) -> str:
        return "Flutter & Dart"

    @property
    def category(self) -> Category:
        return Category.FLUTTER

    def scan(self) -> List[CleanTarget]:
        targets: List[CleanTarget] = []
        home = Path.home()

        # 1. Safe Pub Cache components (TIER 1)
        # We NEVER touch ~/.pub-cache/hosted/pub.dev to avoid re-downloading packages!
        git_cache = home / ".pub-cache" / "git" / "cache"
        if git_cache.exists():
            git_size = get_path_size(git_cache)
            if git_size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name="Dart Pub Git Cache",
                    category=self.category,
                    path=git_cache,
                    size_bytes=git_size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description="Cached git clones for pub dependencies. Hosted packages remain intact.",
                ))

        # 2. Inactive Flutter projects build/ and .dart_tool/ folders
        for root in self.workspace_roots:
            targets.extend(self.scan_workspace_for_inactive_projects(root, self.inactive_days))

        return targets

    def scan_workspace_for_inactive_projects(self, root: Path, inactive_days: int) -> List[CleanTarget]:
        """Scan a workspace root for Flutter projects inactive for > inactive_days with fast pruning."""
        results: List[CleanTarget] = []
        if not root.exists() or is_path_protected(root):
            return results

        cutoff_time = time.time() - (inactive_days * 86400)

        try:
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                # In-place directory pruning so os.walk skips descending into them
                dirnames[:] = [
                    d for d in dirnames
                    if d not in IGNORED_DIR_NAMES and not d.startswith(".")
                ]

                if "pubspec.yaml" in filenames:
                    proj_dir = Path(dirpath)
                    # Once a Flutter project root is found, do not recurse into its subfolders
                    dirnames.clear()

                    if is_path_protected(proj_dir):
                        continue

                    build_dir = proj_dir / "build"
                    dart_tool_dir = proj_dir / ".dart_tool"
                    lib_dir = proj_dir / "lib"

                    if not (build_dir.exists() or dart_tool_dir.exists()):
                        continue

                    # Determine latest edit in lib/
                    latest_mtime = 0.0
                    if lib_dir.exists():
                        try:
                            for entry in os.scandir(lib_dir):
                                if entry.is_file() and entry.name.endswith(".dart"):
                                    mtime = entry.stat().st_mtime
                                    if mtime > latest_mtime:
                                        latest_mtime = mtime
                        except OSError:
                            pass

                    # If project inactive > inactive_days
                    if 0 < latest_mtime < cutoff_time:
                        size = 0
                        if build_dir.exists():
                            size += get_path_size(build_dir)
                        if dart_tool_dir.exists():
                            size += get_path_size(dart_tool_dir)

                        if size > 50 * 1024 * 1024:  # > 50MB
                            target_path = build_dir if build_dir.exists() else dart_tool_dir
                            results.append(CleanTarget(
                                name=f"Inactive Flutter Project: {proj_dir.name}",
                                category=self.category,
                                path=target_path,
                                size_bytes=size,
                                risk_tier=RiskTier.TIER1_SAFE,
                                description=f"Inactive since {format_timestamp(latest_mtime)}. Safe to clean; re-created only when opened.",
                                metadata={"project_path": proj_dir, "last_active": latest_mtime},
                            ))
        except Exception:
            pass

        return results


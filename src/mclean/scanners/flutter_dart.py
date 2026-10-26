"""Flutter & Dart project artifacts and pub-cache scanner."""

import time
from pathlib import Path
from typing import List, Optional

from mclean.config import is_path_ignored, is_path_protected, project_roots, setting
from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_path_size
from mclean.utils.formatters import format_timestamp
from mclean.utils.projects import latest_activity, walk_workspace

# Heavy build output that Flutter regenerates locally. .dart_tool/package_config.json is
# kept on purpose so the project does not even need `pub get` when reopened.
DISPOSABLE_BUILD_PATHS = ["build", ".dart_tool/flutter_build"]


class FlutterDartScanner(BaseScanner):
    """Scans inactive Flutter projects and safe pub-cache components."""

    def __init__(self, workspace_roots: Optional[List[Path]] = None, inactive_days: Optional[int] = None):
        self.workspace_roots = workspace_roots or project_roots()
        self.inactive_days = inactive_days or setting("inactive_days")

    @property
    def name(self) -> str:
        return "Flutter & Dart"

    @property
    def category(self) -> Category:
        return Category.FLUTTER

    def scan(self) -> List[CleanTarget]:
        targets: List[CleanTarget] = []
        home = Path.home()

        # 1. Pub git cache (TIER 2): git dependencies are re-cloned by the next `pub get` that needs them.
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
                    risk_tier=RiskTier.TIER2_REVIEW,
                    description="Cached git clones for pub dependencies. Re-cloned on the next pub get that needs them.",
                ))

        # 2. Inactive Flutter projects build/ and .dart_tool/flutter_build/ folders
        for root in self.workspace_roots:
            targets.extend(self.scan_workspace_for_inactive_projects(root, self.inactive_days))

        return targets

    def scan_workspace_for_inactive_projects(self, root: Path, inactive_days: int) -> List[CleanTarget]:
        """Scan a workspace root for Flutter projects with no activity for > inactive_days."""
        results: List[CleanTarget] = []
        # Workspace roots like ~/Desktop may never be deleted themselves, but they are scanned
        if not root.exists() or is_path_ignored(root):
            return results

        cutoff_time = time.time() - (inactive_days * 86400)

        try:
            for proj_dir, dirnames, filenames in walk_workspace(root):
                if "pubspec.yaml" not in filenames:
                    continue
                # Once a Flutter project root is found, do not recurse into its subfolders
                dirnames.clear()

                if is_path_protected(proj_dir):
                    continue

                paths = [proj_dir / rel for rel in DISPOSABLE_BUILD_PATHS if (proj_dir / rel).exists()]
                if not paths:
                    continue

                # Any edit to sources, a build, a pub get or a git operation counts as activity
                latest_mtime = latest_activity(proj_dir)
                if not (0 < latest_mtime < cutoff_time):
                    continue

                size = sum(get_path_size(p) for p in paths)
                if size > setting("min_project_size_mb") * 1024 * 1024:
                    results.append(CleanTarget(
                        name=f"Inactive Flutter Project: {proj_dir.name}",
                        category=self.category,
                        path=paths[0],
                        size_bytes=size,
                        risk_tier=RiskTier.TIER1_SAFE,
                        description=f"Inactive since {format_timestamp(latest_mtime)}. Build output only; packages stay resolved, so reopening needs no download.",
                        item_type="paths",
                        metadata={"project_path": proj_dir, "last_active": latest_mtime, "paths": paths, "guard": []},
                    ))
        except Exception:
            pass

        return results

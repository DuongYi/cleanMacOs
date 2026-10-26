"""Installed dependencies (node_modules, CocoaPods Pods) of projects nobody has touched for a while."""

import time
from pathlib import Path
from typing import List, Optional

from mclean.config import is_path_ignored, is_path_protected, setting
from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_path_size
from mclean.utils.formatters import format_timestamp
from mclean.utils.projects import default_roots, latest_activity, walk_workspace


def _project_root(podfile_dir: Path) -> Path:
    """ios/ or macos/ inside a Flutter or React Native project belongs to the parent project."""
    parent = podfile_dir.parent
    if podfile_dir.name in ("ios", "macos") and any((parent / f).exists() for f in ("pubspec.yaml", "package.json")):
        return parent
    return podfile_dir


class ProjectDepsScanner(BaseScanner):
    """Offers node_modules and Pods of inactive projects for review. Reinstalling them may download packages."""

    def __init__(self, workspace_roots: Optional[List[Path]] = None, inactive_days: Optional[int] = None):
        self.workspace_roots = workspace_roots or default_roots()
        self.inactive_days = inactive_days or setting("inactive_days")

    @property
    def name(self) -> str:
        return "Project Dependencies"

    @property
    def category(self) -> Category:
        return Category.DEV

    def scan(self) -> List[CleanTarget]:
        targets: List[CleanTarget] = []
        for root in self.workspace_roots:
            targets.extend(self.scan_root(root))
        return targets

    def scan_root(self, root: Path) -> List[CleanTarget]:
        results: List[CleanTarget] = []
        # Workspace roots like ~/Desktop may never be deleted themselves, but they are scanned
        if not root.exists() or is_path_ignored(root):
            return results
        cutoff = time.time() - self.inactive_days * 86400
        activity_cache = {}

        def last_active(project: Path) -> float:
            if project not in activity_cache:
                activity_cache[project] = latest_activity(project)
            return activity_cache[project]

        try:
            for current, dirnames, filenames in walk_workspace(root):
                if "package.json" in filenames and (current / "node_modules").is_dir():
                    target = self._target(current / "node_modules", current, last_active(current), cutoff,
                                          "node_modules", "npm/pnpm/yarn install")
                    if target:
                        results.append(target)
                    # Nested packages of a monorepo share the root's activity; don't descend
                    dirnames.clear()
                    continue

                if "Podfile" in filenames and (current / "Pods").is_dir():
                    project = _project_root(current)
                    target = self._target(current / "Pods", project, last_active(project), cutoff,
                                          "Pods", "pod install")
                    if target:
                        results.append(target)
        except Exception:
            pass
        return results

    def _target(self, deps_dir: Path, project: Path, active: float, cutoff: float, kind: str, reinstall: str) -> Optional[CleanTarget]:
        if not (0 < active < cutoff) or is_path_protected(deps_dir):
            return None
        size = get_path_size(deps_dir)
        if size < setting("min_project_size_mb") * 1024 * 1024:
            return None
        return CleanTarget(
            name=f"{kind} of inactive project: {project.name}",
            category=self.category,
            path=deps_dir,
            size_bytes=size,
            risk_tier=RiskTier.TIER2_REVIEW,
            description=f"Inactive since {format_timestamp(active)}. Restore with '{reinstall}', which downloads anything missing from the package cache.",
            metadata={"project_path": project, "last_active": active, "guard": []},
        )

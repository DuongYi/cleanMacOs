"""System junk, package managers, and trash scanner."""

from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import find_tool, get_batch_sizes, get_path_size

# Subfolders of ~/Library/Logs that have their own target
LOGS_LISTED_ELSEWHERE = {"DiagnosticReports", "CoreSimulator", "OrbStack"}


class SystemJunkScanner(BaseScanner):
    """Scans npm, Homebrew, pnpm, app logs, system diagnostic reports, and Trash."""

    @property
    def name(self) -> str:
        return "System Junk & Developer Tools"

    @property
    def category(self) -> Category:
        return Category.SYSTEM

    def scan(self) -> List[CleanTarget]:
        home = Path.home()
        targets: List[CleanTarget] = []

        # 1. Package manager download caches (TIER 2): existing installs keep working,
        # but the next install that needs these packages downloads them again.
        pkg_caches = [
            ("npm Cache", home / ".npm" / "_cacache", "npm download cache. Re-downloaded on the next install that needs it."),
            ("Yarn Cache", home / "Library" / "Caches" / "Yarn", "Yarn download cache. Re-downloaded on the next install that needs it."),
            ("Bun Install Cache", home / ".bun" / "install" / "cache", "Bun download cache. Re-downloaded on the next install that needs it."),
        ]
        # 2. Logs (TIER 1)
        log_paths = [
            ("npm Logs", home / ".npm" / "_logs", "Debug log files from past npm runs", Category.DEV),
            ("OrbStack Logs", home / "Library" / "Logs" / "OrbStack", "OrbStack virtualization logs", Category.DEV),
            ("macOS Crash Reports", home / "Library" / "Logs" / "DiagnosticReports", "Old app crash dumps and diagnostic traces", Category.SYSTEM),
        ]

        sizes = get_batch_sizes([p for _, p, _ in pkg_caches] + [p for _, p, _, _ in log_paths])

        for name, path, desc in pkg_caches:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name=name, category=Category.DEV, path=path, size_bytes=size,
                    risk_tier=RiskTier.TIER2_REVIEW, description=desc,
                ))

        for name, path, desc, cat in log_paths:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name=name, category=cat, path=path, size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE, description=desc,
                ))

        # Remaining app logs, excluding folders listed separately above or by other scanners
        logs_root = home / "Library" / "Logs"
        if logs_root.is_dir():
            other_logs = [c for c in _children(logs_root) if c.name not in LOGS_LISTED_ELSEWHERE]
            other_size = sum(get_batch_sizes(other_logs).values())
            if other_size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name="macOS App Logs",
                    category=Category.SYSTEM,
                    path=logs_root,
                    size_bytes=other_size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description="Application execution logs in ~/Library/Logs",
                    item_type="contents",
                    metadata={"exclude": sorted(LOGS_LISTED_ELSEWHERE)},
                ))

        # 3. Homebrew: its own cleanup keeps every installed version's files
        brew = find_tool("brew")
        if brew:
            targets.append(CleanTarget(
                name="Homebrew: Cleanup Outdated",
                category=Category.DEV,
                path=home / "Library" / "Caches" / "Homebrew",
                size_bytes=0,
                risk_tier=RiskTier.TIER1_SAFE,
                description="Runs 'brew cleanup': removes old versions and stale downloads only.",
                item_type="command",
                clean_command=[brew, "cleanup"],
            ))

        # 4. pnpm: its own prune removes only packages no project references
        pnpm = find_tool("pnpm")
        if pnpm:
            targets.append(CleanTarget(
                name="pnpm Store: Prune Unreferenced",
                category=Category.DEV,
                path=home / "Library" / "pnpm" / "store",
                size_bytes=0,
                risk_tier=RiskTier.TIER1_SAFE,
                description="Runs 'pnpm store prune': removes only packages no project references.",
                item_type="command",
                clean_command=[pnpm, "store", "prune"],
            ))

        # 5. macOS Trash (TIER 1 - the user already chose to throw these away)
        trash = home / ".Trash"
        if trash.exists():
            trash_size = get_path_size(trash)
            if trash_size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name="macOS Trash",
                    category=Category.TRASH,
                    path=trash,
                    size_bytes=trash_size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description="Files moved to the Trash bin.",
                    item_type="contents",
                ))

        return targets


def _children(path: Path) -> List[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []

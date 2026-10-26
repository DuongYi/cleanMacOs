"""System junk, package managers, and trash scanner."""

import os
import subprocess
from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size


class SystemJunkScanner(BaseScanner):
    """Scans npm, Homebrew, Docker logs, system diagnostic reports, and Trash."""

    @property
    def name(self) -> str:
        return "System Junk & Developer Tools"

    @property
    def category(self) -> Category:
        return Category.SYSTEM

    def scan(self) -> List[CleanTarget]:
        home = Path.home()
        targets: List[CleanTarget] = []

        # 1. Package Manager Caches (TIER 1 - 100% Safe)
        pkg_caches = [
            ("Homebrew Download Cache", home / "Library" / "Caches" / "Homebrew", "Downloaded formula and bottle tarballs", Category.DEV),
            ("npm Cache", home / ".npm" / "_cacache", "Content-addressable download tarballs cache", Category.DEV),
            ("npm Logs", home / ".npm" / "_logs", "Debug log files from past npm runs", Category.DEV),
            ("Yarn Cache", home / "Library" / "Caches" / "Yarn", "Yarn downloaded package tarballs", Category.DEV),
            ("pnpm Store Cache", home / ".pnpm-store", "Cached pnpm package tarballs", Category.DEV),
            ("Bun Install Cache", home / ".bun" / "install" / "cache", "Bun package manager download cache", Category.DEV),
            ("Docker Desktop Logs", home / "Library" / "Containers" / "com.docker.docker" / "Data" / "log", "Docker VM and engine log files", Category.DEV),
            ("OrbStack Logs", home / "Library" / "Logs" / "OrbStack", "OrbStack virtualization logs", Category.DEV),
        ]

        # 2. System Logs and Crash Dumps (TIER 1 - Safe)
        system_caches = [
            ("macOS Crash Reports", home / "Library" / "Logs" / "DiagnosticReports", "Old app crash dumps and diagnostic traces", Category.SYSTEM),
            ("macOS User Logs", home / "Library" / "Logs", "Application execution logs", Category.SYSTEM),
        ]

        # Check all candidate paths concurrently
        all_candidates = pkg_caches + system_caches
        sizes = get_batch_sizes([p for _, p, _, _ in all_candidates])

        for name, path, desc, cat in all_candidates:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:  # > 10MB
                targets.append(CleanTarget(
                    name=name,
                    category=cat,
                    path=path,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description=desc,
                ))

        # 3. macOS Trash (TIER 1 - Safe)
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
                    item_type="command",
                    clean_command=["rm", "-rf", str(trash / "*")],
                ))

        return targets

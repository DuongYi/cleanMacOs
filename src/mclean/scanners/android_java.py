"""Android SDK, Gradle, and Android Virtual Device (AVD) Scanner."""

import re
from pathlib import Path
from typing import List
from packaging import version

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size


class AndroidJavaScanner(BaseScanner):
    """Scans Gradle caches, wrappers, and Android AVD snapshots."""

    @property
    def name(self) -> str:
        return "Android & Gradle"

    @property
    def category(self) -> Category:
        return Category.ANDROID

    def scan(self) -> List[CleanTarget]:
        home = Path.home()
        targets: List[CleanTarget] = []

        # 1. Gradle Daemons and log files (TIER 1 - Safe)
        gradle_daemon = home / ".gradle" / "daemon"
        if gradle_daemon.exists():
            daemon_size = get_path_size(gradle_daemon)
            if daemon_size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name="Gradle Daemons & Logs",
                    category=self.category,
                    path=gradle_daemon,
                    size_bytes=daemon_size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description="Stopped Gradle daemon instances and execution logs",
                ))

        # 2. Smart Gradle Wrapper distributions pruning (Keep top 2 newest versions)
        gradle_wrapper_dists = home / ".gradle" / "wrapper" / "dists"
        if gradle_wrapper_dists.exists():
            targets.extend(self._scan_old_gradle_wrappers(gradle_wrapper_dists))

        # 3. Smart Gradle Versioned Caches (Keep top 2 newest version caches)
        gradle_caches = home / ".gradle" / "caches"
        if gradle_caches.exists():
            targets.extend(self._scan_old_gradle_caches(gradle_caches))

        # 4. Android AVD Snapshots and Caches (TIER 1 - Safe, won't delete user data)
        avd_root = home / ".android" / "avd"
        if avd_root.exists():
            targets.extend(self._scan_avds(avd_root))

        return targets

    def _scan_old_gradle_wrappers(self, dists_dir: Path) -> List[CleanTarget]:
        """Keep the 2 newest Gradle wrappers, flag older ones for cleanup."""
        results: List[CleanTarget] = []
        found_versions = []

        for item in dists_dir.iterdir():
            if item.is_dir() and item.name.startswith("gradle-"):
                # Extract version string e.g. "gradle-8.9-bin" -> "8.9"
                match = re.search(r"gradle-([0-9\.]+)", item.name)
                if match:
                    try:
                        v = version.parse(match.group(1))
                        found_versions.append((v, item))
                    except Exception:
                        pass

        # Sort versions ascending: oldest first, newest last
        found_versions.sort(key=lambda x: x[0])

        # If more than 2 versions, flag older ones for removal
        if len(found_versions) > 2:
            obsolete = found_versions[:-2]  # Keep the newest 2
            sizes = get_batch_sizes([item for _, item in obsolete])
            for v, item in obsolete:
                size = sizes.get(item, 0)
                if size > 10 * 1024 * 1024:
                    results.append(CleanTarget(
                        name=f"Old Gradle Wrapper: {item.name}",
                        category=self.category,
                        path=item,
                        size_bytes=size,
                        risk_tier=RiskTier.TIER1_SAFE,
                        description=f"Outdated Gradle distribution (version {v}). Newest 2 versions are preserved.",
                    ))

        return results

    def _scan_old_gradle_caches(self, caches_dir: Path) -> List[CleanTarget]:
        """Prune older Gradle execution caches (e.g., 8.9, 8.13) while keeping top 2 and modules-2."""
        results: List[CleanTarget] = []
        version_dirs = []

        # Find folders named like '8.9', '8.14', '9.1.0'
        for item in caches_dir.iterdir():
            if item.is_dir() and re.match(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$", item.name):
                try:
                    v = version.parse(item.name)
                    version_dirs.append((v, item))
                except Exception:
                    pass

        version_dirs.sort(key=lambda x: x[0])
        if len(version_dirs) > 2:
            obsolete = version_dirs[:-2]  # Keep 2 newest
            sizes = get_batch_sizes([item for _, item in obsolete])
            for v, item in obsolete:
                size = sizes.get(item, 0)
                if size > 50 * 1024 * 1024:
                    results.append(CleanTarget(
                        name=f"Old Gradle Cache: {item.name}",
                        category=self.category,
                        path=item,
                        size_bytes=size,
                        risk_tier=RiskTier.TIER1_SAFE,
                        description=f"Execution cache for Gradle {v}. Dependencies in modules-2 are safe.",
                    ))

        return results

    def _scan_avds(self, avd_root: Path) -> List[CleanTarget]:
        """Scan Android AVDs for snapshots (TIER 1) and inspect disk image size (TIER 2)."""
        results: List[CleanTarget] = []

        for avd_dir in avd_root.glob("*.avd"):
            if not avd_dir.is_dir():
                continue
            avd_name = avd_dir.stem

            # 1. Snapshots folder (TIER 1 - safe to wipe, triggers cold boot next time)
            snapshots_dir = avd_dir / "snapshots"
            if snapshots_dir.exists():
                snap_size = get_path_size(snapshots_dir)
                if snap_size > 50 * 1024 * 1024:
                    results.append(CleanTarget(
                        name=f"AVD Snapshots: {avd_name}",
                        category=self.category,
                        path=snapshots_dir,
                        size_bytes=snap_size,
                        risk_tier=RiskTier.TIER1_SAFE,
                        description="Quick-boot memory snapshots. Deleting forces cold boot without losing apps or data.",
                    ))

            # 2. Temporary cache img files
            for cache_file in avd_dir.glob("cache.img*"):
                if cache_file.is_file():
                    c_size = cache_file.stat().st_size
                    if c_size > 10 * 1024 * 1024:
                        results.append(CleanTarget(
                            name=f"AVD Temp Cache: {avd_name}/{cache_file.name}",
                            category=self.category,
                            path=cache_file,
                            size_bytes=c_size,
                            risk_tier=RiskTier.TIER1_SAFE,
                            description="Temporary Android emulator partition cache.",
                            item_type="file",
                        ))

            # 3. Informational check on userdata-qemu.img.qcow2 (TIER 2 - Review only)
            qcow2 = avd_dir / "userdata-qemu.img.qcow2"
            if qcow2.exists():
                img_size = qcow2.stat().st_size
                if img_size > 2 * 1024 * 1024 * 1024:  # > 2GB
                    results.append(CleanTarget(
                        name=f"AVD Storage Image: {avd_name}",
                        category=self.category,
                        path=qcow2,
                        size_bytes=img_size,
                        risk_tier=RiskTier.TIER2_REVIEW,
                        description=f"AVD disk image containing installed test apps. Wipe only if resetting AVD.",
                        item_type="file",
                    ))

        return results

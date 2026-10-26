"""Android SDK, Gradle, and Android Virtual Device (AVD) Scanner."""

import os
import platform
import re
import time
from pathlib import Path
from typing import List, Optional
from packaging import version

from mclean.config import setting
from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size
from mclean.utils.formatters import format_timestamp
from mclean.utils.guard import running_gradle_dists
from mclean.utils.projects import referenced_gradle_dists, referenced_gradle_versions, referenced_ndk_versions

# A Gradle version is only offered after gradle_idle_days without any daemon or wrapper activity.
# IDE extensions (e.g. VS Code Java/Gradle) silently download wrappers of every project they
# import, so "not referenced by my projects" alone would cause a delete/re-download loop.
DAEMON_LOG_DAYS = 7


def android_sdk_root() -> Optional[Path]:
    """Android SDK location from the environment, else Android Studio's default."""
    for candidate in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"), str(Path.home() / "Library" / "Android" / "sdk")):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return None


def _children(path: Path) -> List[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def _gradle_idle_days(gradle_version: str, dist_dir: Optional[Path] = None) -> int:
    """Days since Gradle <version> last ran, from daemon registry and wrapper lock timestamps."""
    # ~/.gradle/daemon/<version>/ (registry.bin is rewritten whenever a daemon starts or stops)
    # and <dist>/<hash>/ (holds the .zip.lck / .zip.ok markers the wrapper touches)
    roots = [Path.home() / ".gradle" / "daemon" / gradle_version]
    if dist_dir:
        roots += [dist_dir, *(d for d in _children(dist_dir) if d.is_dir())]
    newest = 0.0
    for p in roots + [c for r in roots for c in _children(r)]:
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            continue
    return int((time.time() - newest) / 86400) if newest else 10_000

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

        # 1. Old Gradle daemon logs (TIER 1). The daemon folders themselves are kept:
        # their timestamps are how we know which Gradle versions are still in use.
        old_logs = self._old_daemon_logs(home / ".gradle" / "daemon")
        logs_size = sum(f.stat().st_size for f in old_logs)
        if logs_size > 10 * 1024 * 1024:
            targets.append(CleanTarget(
                name="Gradle Daemon Logs",
                category=self.category,
                path=home / ".gradle" / "daemon",
                size_bytes=logs_size,
                risk_tier=RiskTier.TIER1_SAFE,
                description=f"Daemon log files older than {DAEMON_LOG_DAYS} days",
                item_type="paths",
                metadata={"paths": old_logs, "guard": []},
            ))

        # 2. Smart Gradle Wrapper distributions pruning (Keep top 2 newest versions)
        gradle_wrapper_dists = home / ".gradle" / "wrapper" / "dists"
        if gradle_wrapper_dists.exists():
            targets.extend(self._scan_old_gradle_wrappers(gradle_wrapper_dists))

        # 3. Smart Gradle Versioned Caches (Keep top 2 newest version caches)
        gradle_caches = home / ".gradle" / "caches"
        if gradle_caches.exists():
            targets.extend(self._scan_old_gradle_caches(gradle_caches))

        # 4. Snapshots and caches of idle AVDs (TIER 1 - user data is never touched)
        avd_root = home / ".android" / "avd"
        if avd_root.exists():
            targets.extend(self._scan_avds(avd_root))

        # 5. Android SDK packages nothing uses (TIER 2: downloaded again if you need them later)
        sdk = android_sdk_root()
        if sdk:
            targets.extend(self._scan_unused_system_images(sdk, avd_root))
            targets.extend(self._scan_unused_ndks(sdk))

        return targets

    def _scan_unused_system_images(self, sdk: Path, avd_root: Path) -> List[CleanTarget]:
        """System images (system-images/<api>/<tag>/<abi>) that no AVD boots from."""
        results: List[CleanTarget] = []
        used = set()
        for config in avd_root.glob("*.avd/config.ini"):
            try:
                for line in config.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("image.sysdir."):
                        used.add((sdk / line.split("=", 1)[1].strip()).resolve())
            except OSError:
                continue

        for abi_dir in sdk.glob("system-images/*/*/*"):
            if not abi_dir.is_dir() or abi_dir.resolve() in used:
                continue
            size = get_path_size(abi_dir)
            if size > 100 * 1024 * 1024:
                api, tag, abi = abi_dir.relative_to(sdk / "system-images").parts
                # The emulator on Apple Silicon cannot boot x86 images at all
                unbootable = platform.machine() == "arm64" and abi.startswith("x86")
                results.append(CleanTarget(
                    name=f"Unused System Image: {api} {tag} ({abi})",
                    category=self.category,
                    path=abi_dir,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE if unbootable else RiskTier.TIER2_REVIEW,
                    description=(
                        "x86 image that the emulator cannot run on this Apple Silicon Mac."
                        if unbootable
                        else "No AVD uses this emulator image. Android Studio downloads it again only if you create an AVD with it."
                    ),
                    metadata={"guard": ["Android Studio / Emulator"]},  # Gradle never reads system images
                ))
        return results

    def _scan_unused_ndks(self, sdk: Path) -> List[CleanTarget]:
        """Side-by-side NDKs that no project, Flutter SDK default or pub plugin asks for. The newest is always kept."""
        results: List[CleanTarget] = []
        ndk_dirs = []
        for d in (sdk / "ndk").glob("*"):
            try:
                ndk_dirs.append((version.parse(d.name), d))
            except Exception:
                continue
        ndk_dirs.sort(key=lambda x: x[0])
        if len(ndk_dirs) < 2:
            return results

        referenced = referenced_ndk_versions()
        for v, d in ndk_dirs[:-1]:
            if d.name in referenced:
                continue
            size = get_path_size(d)
            if size > 100 * 1024 * 1024:
                results.append(CleanTarget(
                    name=f"Unused NDK: {d.name}",
                    category=self.category,
                    path=d,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER2_REVIEW,
                    description="Not named by any project, Flutter SDK or plugin in your pub cache. Gradle downloads it again if a build asks for it.",
                ))
        return results

    def _scan_old_gradle_wrappers(self, dists_dir: Path) -> List[CleanTarget]:
        """Flag wrapper distributions no project references; always keep the 2 newest for new projects."""
        results: List[CleanTarget] = []
        found_versions = []
        referenced = referenced_gradle_dists()

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

        in_use = running_gradle_dists()
        obsolete = [
            (v, item) for v, item in found_versions[:-2]
            if item.name not in referenced | in_use and _gradle_idle_days(str(v), item) >= setting("gradle_idle_days")
        ]
        sizes = get_batch_sizes([item for _, item in obsolete])
        for v, item in obsolete:
            size = sizes.get(item, 0)
            if size > 10 * 1024 * 1024:
                results.append(CleanTarget(
                    name=f"Unused Gradle Wrapper: {item.name}",
                    category=self.category,
                    path=item,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description=f"Gradle {v}: no project references it and nothing has run it for {_gradle_idle_days(str(v), item)} days.",
                    metadata={"guard": []},  # versions used by running daemons are excluded above
                ))

        return results

    def _scan_old_gradle_caches(self, caches_dir: Path) -> List[CleanTarget]:
        """Prune execution caches of Gradle versions no project uses, keeping the 2 newest and modules-2."""
        results: List[CleanTarget] = []
        version_dirs = []
        referenced = referenced_gradle_versions()

        # Find folders named like '8.9', '8.14', '9.1.0'
        for item in caches_dir.iterdir():
            if item.is_dir() and re.match(r"^[0-9]+\.[0-9]+(\.[0-9]+)?$", item.name):
                try:
                    v = version.parse(item.name)
                    version_dirs.append((v, item))
                except Exception:
                    pass

        version_dirs.sort(key=lambda x: x[0])
        in_use = {re.sub(r"^gradle-|-(bin|all)$", "", d) for d in running_gradle_dists()}
        obsolete = [
            (v, item) for v, item in version_dirs[:-2]
            if item.name not in referenced | in_use and _gradle_idle_days(item.name) >= setting("gradle_idle_days")
        ]
        sizes = get_batch_sizes([item for _, item in obsolete])
        for v, item in obsolete:
            size = sizes.get(item, 0)
            if size > 50 * 1024 * 1024:
                results.append(CleanTarget(
                    name=f"Unused Gradle Cache: {item.name}",
                    category=self.category,
                    path=item,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description=f"Execution cache for Gradle {v}, unused for {_gradle_idle_days(item.name)} days. Dependencies in modules-2 are kept.",
                    metadata={"guard": []},  # versions used by running daemons are excluded above
                ))

        return results

    def _old_daemon_logs(self, daemon_root: Path) -> List[Path]:
        cutoff = time.time() - DAEMON_LOG_DAYS * 86400
        logs = []
        for log in daemon_root.glob("*/daemon-*.out.log"):
            try:
                if log.stat().st_mtime < cutoff:
                    logs.append(log)
            except OSError:
                continue
        return logs

    def _scan_avds(self, avd_root: Path) -> List[CleanTarget]:
        """Scan AVDs idle for a while: their snapshots and temp caches regenerate locally on next boot."""
        results: List[CleanTarget] = []
        cutoff = time.time() - setting("avd_idle_days") * 86400

        for avd_dir in avd_root.glob("*.avd"):
            if not avd_dir.is_dir():
                continue
            avd_name = avd_dir.stem

            # Emulator rewrites hardware-qemu.ini on every boot
            try:
                last_boot = max(
                    (avd_dir / f).stat().st_mtime
                    for f in ("hardware-qemu.ini", "emu-launch-params.txt", "config.ini")
                    if (avd_dir / f).exists()
                )
            except ValueError:
                last_boot = 0.0
            if last_boot > cutoff:
                continue  # Used recently: a cold boot would slow you down, so leave it alone

            # 1. Snapshots folder (forces one cold boot next time, apps and data are kept)
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
                        description=f"Quick-boot snapshots of an emulator idle since {format_timestamp(last_boot)}. Apps and data are kept.",
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
                            description="Temporary Android emulator partition cache, recreated on boot.",
                            item_type="file",
                        ))

            # userdata-qemu.img* holds installed apps and data: never offered (Tier 3)

        return results

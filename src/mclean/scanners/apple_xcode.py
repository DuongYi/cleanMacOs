"""Xcode, iOS Simulator, and Apple Developer Cache Scanner."""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size
from mclean.utils.formatters import format_timestamp

DERIVED_DATA_IDLE_DAYS = 14
SIMULATOR_IDLE_DAYS = 30
RUNTIME_IDLE_DAYS = 30


def _safe_children(path: Path) -> List[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def _newest_mtime(paths: Iterable[Path]) -> float:
    newest = 0.0
    for p in paths:
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            continue
    return newest


class AppleXcodeScanner(BaseScanner):
    """Scans Xcode caches, iOS Simulators, DeviceSupport, and CocoaPods."""

    @property
    def name(self) -> str:
        return "Xcode & Apple Developer"

    @property
    def category(self) -> Category:
        return Category.XCODE

    def scan(self) -> List[CleanTarget]:
        home = Path.home()
        targets: List[CleanTarget] = []

        # 1. Caches Xcode and the Simulator regenerate locally (TIER 1, skipped while Xcode runs)
        standard_paths = [
            ("CoreSimulator Caches", home / "Library/Developer/CoreSimulator/Caches", "iOS Simulator system caches, rebuilt locally on next boot", RiskTier.TIER1_SAFE),
            ("SwiftUI Previews Cache", home / "Library/Developer/Xcode/UserData/Previews", "Cached SwiftUI canvas preview snapshots, rebuilt locally", RiskTier.TIER1_SAFE),
            ("Xcode App Cache", home / "Library/Caches/com.apple.dt.Xcode", "Xcode IDE temporary caches", RiskTier.TIER1_SAFE),
            ("CoreSimulator Logs", home / "Library/Logs/CoreSimulator", "Simulator crash logs and diagnostics", RiskTier.TIER1_SAFE),
            # Download caches: deleting them means fetching again on the next `pod install` / package resolve
            ("CocoaPods Cache", home / "Library/Caches/CocoaPods", "Downloaded pod archives. Re-downloaded on the next pod install that needs them.", RiskTier.TIER2_REVIEW),
            ("Swift Package Manager Cache", home / "Library/Caches/org.swift.swiftpm", "SwiftPM clone cache. Re-cloned on the next package resolve that needs it.", RiskTier.TIER2_REVIEW),
        ]

        sizes = get_batch_sizes([p for _, p, _, _ in standard_paths])
        for name, path, desc, tier in standard_paths:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:  # Only show if > 10MB
                targets.append(CleanTarget(
                    name=name,
                    category=self.category,
                    path=path,
                    size_bytes=size,
                    risk_tier=tier,
                    description=desc,
                ))

        # 1b. DerivedData of projects not built recently (active projects are left untouched)
        targets.extend(self._scan_derived_data(home / "Library/Developer/Xcode/DerivedData"))

        # 1c. Device symbols per OS version: Xcode copies them again from the device when it reconnects
        for platform in ("iOS", "watchOS", "tvOS", "visionOS"):
            targets.extend(self._scan_device_support(home / f"Library/Developer/Xcode/{platform} DeviceSupport", platform))

        # 2. Simulator unavailable cleanup command
        targets.append(CleanTarget(
            name="iOS Simulators: Delete Unavailable",
            category=self.category,
            path=home / "Library/Developer/CoreSimulator/Caches",
            size_bytes=0,  # Command-based, dynamically recovers space
            risk_tier=RiskTier.TIER1_SAFE,
            description="Calls 'xcrun simctl delete unavailable' to safely remove obsolete runtimes",
            item_type="command",
            clean_command=["xcrun", "simctl", "delete", "unavailable"],
            metadata={"guard": []},  # unavailable simulators cannot be running
        ))

        # 2b. Simulator runtimes not used for a while (TIER 2: re-downloaded from Xcode if needed)
        targets.extend(self._scan_runtimes())

        # 3. Detailed Inspection of individual iOS Simulators
        simulators_detail = self._scan_simulators(home)
        targets.extend(simulators_detail)

        return targets

    def _scan_derived_data(self, root: Path) -> List[CleanTarget]:
        """One target per project folder whose last build is older than DERIVED_DATA_IDLE_DAYS."""
        results: List[CleanTarget] = []
        if not root.is_dir():
            return results
        cutoff = time.time() - DERIVED_DATA_IDLE_DAYS * 86400
        for item in root.iterdir():
            if not item.is_dir():
                continue
            last_used = _newest_mtime([item, *_safe_children(item), item / "Logs" / "Build"])
            if last_used > cutoff:
                continue
            size = get_path_size(item)
            if size > 50 * 1024 * 1024:
                project = item.name.rsplit("-", 1)[0]
                results.append(CleanTarget(
                    name=f"DerivedData: {project}",
                    category=self.category,
                    path=item,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description=f"Build intermediates of a project last built {format_timestamp(last_used)}. Rebuilt locally if reopened.",
                ))
        return results

    def _scan_device_support(self, root: Path, platform: str) -> List[CleanTarget]:
        """Debug symbols per OS version, offered for review only."""
        results: List[CleanTarget] = []
        if not root.is_dir():
            return results
        for item in root.iterdir():
            if not item.is_dir():
                continue
            size = get_path_size(item)
            if size > 100 * 1024 * 1024:
                last_used = _newest_mtime([item, *_safe_children(item)])
                results.append(CleanTarget(
                    name=f"{platform} DeviceSupport: {item.name}",
                    category=self.category,
                    path=item,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER2_REVIEW,
                    description=f"Device debug symbols, last used {format_timestamp(last_used)}. Xcode copies them again (several minutes) if a device on this OS reconnects.",
                    metadata={"last_used": last_used},
                ))
        return results

    def _scan_runtimes(self) -> List[CleanTarget]:
        """Simulator runtime disk images, offered only when unused for RUNTIME_IDLE_DAYS."""
        results: List[CleanTarget] = []
        try:
            res = subprocess.run(["xcrun", "simctl", "runtime", "list", "-j"], capture_output=True, text=True, timeout=20)
            if res.returncode != 0:
                return results
            runtimes = json.loads(res.stdout)
        except Exception:
            return results

        for rid, rt in runtimes.items():
            idle = self._idle_days(rt.get("lastUsedAt"))
            if not rt.get("deletable") or idle < RUNTIME_IDLE_DAYS:
                continue
            platform = rt.get("runtimeIdentifier", "").rsplit(".", 1)[-1].split("-")[0] or "Simulator"
            results.append(CleanTarget(
                name=f"Simulator Runtime: {platform} {rt.get('version', '?')} ({rt.get('build', '')})",
                category=self.category,
                path=Path(rt.get("path") or "/Library/Developer/CoreSimulator"),
                size_bytes=int(rt.get("sizeBytes", 0)),
                risk_tier=RiskTier.TIER2_REVIEW,
                description=f"Not used for {idle}+ days. Simulators on this OS version stop working; Xcode downloads it again (several GB) if needed.",
                item_type="command",
                clean_command=["xcrun", "simctl", "runtime", "delete", rid],
            ))
        return results

    @staticmethod
    def _idle_days(last_booted: Optional[str]) -> int:
        if not last_booted:
            return 10_000  # Never booted
        try:
            booted = datetime.fromisoformat(last_booted.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - booted).days
        except ValueError:
            return 0

    def _scan_simulators(self, home: Path) -> List[CleanTarget]:
        """Scan individual iOS Simulator devices via simctl JSON output."""
        results: List[CleanTarget] = []
        try:
            res = subprocess.run(
                ["xcrun", "simctl", "list", "devices", "-j"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return results

            data = json.loads(res.stdout)
            device_sections = data.get("devices", {})

            for runtime_name, dev_list in device_sections.items():
                for dev in dev_list:
                    data_path_str = dev.get("dataPath")
                    is_available = dev.get("isAvailable", True)
                    state = dev.get("state", "Unknown")
                    name = dev.get("name", "Unknown Simulator")
                    udid = dev.get("udid", "")

                    if not data_path_str:
                        continue

                    data_path = Path(data_path_str)
                    if not data_path.exists():
                        continue

                    # Unavailable simulators -> TIER 1
                    if not is_available:
                        size = get_path_size(data_path)
                        if size > 50 * 1024 * 1024:
                            results.append(CleanTarget(
                                name=f"Unavailable Simulator: {name}",
                                category=self.category,
                                path=data_path,
                                size_bytes=size,
                                risk_tier=RiskTier.TIER1_SAFE,
                                description=f"Obsolete simulator runtime ({runtime_name}), UDID: {udid}",
                                item_type="command",
                                clean_command=["xcrun", "simctl", "delete", udid],
                                metadata={"guard": []},
                            ))
                    else:
                        # Heavy shutdown simulators (> 1.5 GB) -> TIER 2 Review
                        if state == "Shutdown" and self._idle_days(dev.get("lastBootedAt")) >= SIMULATOR_IDLE_DAYS:
                            size = get_path_size(data_path)
                            if size > 1500 * 1024 * 1024:  # > 1.5 GB
                                results.append(CleanTarget(
                                    name=f"Heavy Simulator: {name} ({state})",
                                    category=self.category,
                                    path=data_path,
                                    size_bytes=size,
                                    risk_tier=RiskTier.TIER2_REVIEW,
                                    description=f"Not booted for {self._idle_days(dev.get('lastBootedAt'))}+ days. Erase resets installed apps. Runtime: {runtime_name.split('.')[-1]}",
                                    item_type="command",
                                    clean_command=["xcrun", "simctl", "erase", udid],
                                    metadata={"udid": udid, "action": "erase"},
                                ))
        except Exception:
            pass

        return results

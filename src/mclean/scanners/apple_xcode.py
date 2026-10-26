"""Xcode, iOS Simulator, and Apple Developer Cache Scanner."""

import json
import subprocess
from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size


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

        # 1. Standard Apple Developer and Xcode Caches (TIER 1 - 100% Safe)
        standard_paths = [
            ("Xcode DerivedData", home / "Library/Developer/Xcode/DerivedData", "Intermediate build files and indexing caches", RiskTier.TIER1_SAFE),
            ("CoreSimulator Caches", home / "Library/Developer/CoreSimulator/Caches", "iOS Simulator system caches and runtime buffers", RiskTier.TIER1_SAFE),
            ("iOS DeviceSupport", home / "Library/Developer/Xcode/iOS DeviceSupport", "Debug symbols for physical devices previously connected", RiskTier.TIER1_SAFE),
            ("watchOS DeviceSupport", home / "Library/Developer/Xcode/watchOS DeviceSupport", "Old watchOS device debug symbols", RiskTier.TIER1_SAFE),
            ("tvOS DeviceSupport", home / "Library/Developer/Xcode/tvOS DeviceSupport", "Old tvOS device debug symbols", RiskTier.TIER1_SAFE),
            ("SwiftUI Previews Cache", home / "Library/Developer/Xcode/UserData/Previews", "Cached SwiftUI canvas preview snapshots", RiskTier.TIER1_SAFE),
            ("Xcode App Cache", home / "Library/Caches/com.apple.dt.Xcode", "Xcode IDE temporary caches", RiskTier.TIER1_SAFE),
            ("CocoaPods Cache", home / "Library/Caches/CocoaPods", "Downloaded pod tarball archive cache", RiskTier.TIER1_SAFE),
            ("Swift Package Manager Cache", home / "Library/Caches/org.swift.swiftpm", "SwiftPM git repository and clone cache", RiskTier.TIER1_SAFE),
            ("CoreSimulator Logs", home / "Library/Logs/CoreSimulator", "Simulator crash logs and diagnostics", RiskTier.TIER1_SAFE),
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
        ))

        # 3. Detailed Inspection of individual iOS Simulators
        simulators_detail = self._scan_simulators(home)
        targets.extend(simulators_detail)

        return targets

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
                            ))
                    else:
                        # Heavy shutdown simulators (> 1.5 GB) -> TIER 2 Review
                        if state == "Shutdown":
                            size = get_path_size(data_path)
                            if size > 1500 * 1024 * 1024:  # > 1.5 GB
                                results.append(CleanTarget(
                                    name=f"Heavy Simulator: {name} ({state})",
                                    category=self.category,
                                    path=data_path,
                                    size_bytes=size,
                                    risk_tier=RiskTier.TIER2_REVIEW,
                                    description=f"Runtime: {runtime_name.split('.')[-1]}, UDID: {udid}",
                                    item_type="command",
                                    clean_command=["xcrun", "simctl", "erase", udid],
                                    metadata={"udid": udid, "action": "erase"},
                                ))
        except Exception:
            pass

        return results

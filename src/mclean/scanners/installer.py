"""Scanner for leftover installers, mobile builds, and large archives in Downloads."""

import time
from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.utils.formatters import format_timestamp


INSTALLER_EXTENSIONS = {
    ".dmg", ".pkg", ".iso",         # macOS Installers
    ".apk", ".ipa", ".aab",         # Mobile Builds
}
ARCHIVE_EXTENSIONS = {".zip", ".tar.gz", ".tgz", ".rar", ".7z"}


def scan_installers(downloads_dir: Path = Path.home() / "Downloads", older_than_days: int = 7) -> List[CleanTarget]:
    """Scan Downloads for old installers and heavy mobile build files."""
    targets: List[CleanTarget] = []
    if not downloads_dir.exists():
        return targets

    cutoff = time.time() - (older_than_days * 86400)

    try:
        for item in downloads_dir.iterdir():
            if not item.is_file():
                continue

            ext = item.suffix.lower()
            if item.name.endswith(".tar.gz"):
                ext = ".tar.gz"

            is_installer = ext in INSTALLER_EXTENSIONS
            is_large_archive = ext in ARCHIVE_EXTENSIONS

            if is_installer or is_large_archive:
                try:
                    stat = item.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime

                    # Only show if > 20MB for installers, or > 50MB for archives
                    min_size = 20 * 1024 * 1024 if is_installer else 50 * 1024 * 1024
                    if size >= min_size:
                        # Archives may be backups or deliverables, so they are never pre-selected
                        tier = RiskTier.TIER1_SAFE if is_installer and mtime < cutoff else RiskTier.TIER2_REVIEW
                        type_label = "Tệp cài đặt macOS" if ext in {".dmg", ".pkg", ".iso"} else "Mobile Build" if ext in {".apk", ".ipa", ".aab"} else "Tệp nén lớn"
                        targets.append(CleanTarget(
                            name=f"{type_label}: {item.name}",
                            category=Category.DEV,
                            path=item,
                            size_bytes=size,
                            risk_tier=tier,
                            description=f"Tải về từ {format_timestamp(mtime)} trong Downloads.",
                            item_type="file",
                        ))
                except OSError:
                    continue
    except Exception:
        pass

    targets.sort(key=lambda t: t.size_bytes, reverse=True)
    return targets

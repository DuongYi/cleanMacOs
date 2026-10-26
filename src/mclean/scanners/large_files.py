"""High-speed large file finder across user directory (inspired by DaisyDisk)."""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple

from mclean.utils.formatters import format_size, format_timestamp

# Directory names to skip for speed and system integrity
EXCLUDED_SCAN_DIRS = {
    "Library", ".git", ".pub-cache", "node_modules", ".cache",
    ".gradle", "Pods", "DerivedData", ".Trash", "Application Support",
    "flutter", "build", ".dart_tool", "venv", ".venv",
}


class LargeFileItem:
    """Represents a discovered large file."""
    def __init__(self, path: Path, size_bytes: int, mtime: float):
        self.path = path
        self.size_bytes = size_bytes
        self.mtime = mtime

    @property
    def file_type(self) -> str:
        ext = self.path.suffix.lower()
        if ext in {".safetensors", ".bin", ".pth", ".onnx", ".pt", ".ckpt", ".gguf"}:
            return "AI / Model Weights"
        elif ext in {".mp4", ".mov", ".mkv", ".avi"}:
            return "Video / Media"
        elif ext in {".dmg", ".iso", ".pkg"}:
            return "Installer / Disk Image"
        elif ext in {".apk", ".ipa", ".aab"}:
            return "Mobile Build"
        elif ext in {".zip", ".tar.gz", ".tgz", ".rar", ".7z"}:
            return "Archive / Backup"
        return "Tệp dữ liệu lớn"


def find_large_files(
    root: Path = Path.home(),
    min_size_mb: int = 500,
    max_results: int = 25,
) -> List[LargeFileItem]:
    """Scan root directory for files larger than min_size_mb."""
    results: List[LargeFileItem] = []
    min_size_bytes = min_size_mb * 1024 * 1024

    if not root.exists():
        return results

    try:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            # Prune noisy directories in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in EXCLUDED_SCAN_DIRS and not d.startswith(".")
            ]

            for fname in filenames:
                try:
                    fpath = Path(dirpath) / fname
                    # Avoid symlinks
                    if fpath.is_symlink():
                        continue

                    stat = fpath.stat()
                    if stat.st_size >= min_size_bytes:
                        results.append(LargeFileItem(
                            path=fpath,
                            size_bytes=stat.st_size,
                            mtime=stat.st_mtime,
                        ))
                except OSError:
                    continue
    except Exception:
        pass

    results.sort(key=lambda x: x.size_bytes, reverse=True)
    return results[:max_results]


def reveal_in_finder(path: Path) -> None:
    """Open macOS Finder and highlight the file."""
    try:
        subprocess.run(["open", "-R", str(path)], check=False)
    except Exception:
        pass

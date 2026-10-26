"""High-performance multi-threaded disk operations for macOS."""

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Iterable, Tuple

from mclean.config import is_path_protected


def get_path_size(path: Path) -> int:
    """Calculate size of file or folder using native macOS `du -sk` for instant APFS speed."""
    if not path.exists():
        return 0

    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    try:
        # du -sk returns size in 1024-byte blocks
        res = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            return int(res.stdout.split()[0]) * 1024
    except Exception:
        pass

    # Fallback to python file walker if du fails
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_path_size(Path(entry.path))
            except OSError:
                continue
    except OSError:
        pass
    return total


def get_batch_sizes(paths: Iterable[Path], max_workers: int = 8) -> Dict[Path, int]:
    """Calculate directory sizes concurrently using a ThreadPoolExecutor."""
    results: Dict[Path, int] = {}
    valid_paths = [p for p in paths if p.exists()]
    if not valid_paths:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(get_path_size, p): p for p in valid_paths}
        for future in future_to_path:
            p = future_to_path[future]
            try:
                results[p] = future.result()
            except Exception:
                results[p] = 0
    return results


def safe_delete_path(path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """Safely remove a file or directory with blacklist guards."""
    if is_path_protected(path):
        return False, f"Path is protected by safety blacklist: {path}"

    if not path.exists():
        return True, "Path does not exist (already clean)"

    if dry_run:
        return True, f"[Dry-run] Would delete: {path}"

    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
            return True, f"Deleted file: {path.name}"
        elif path.is_dir():
            shutil.rmtree(path)
            return True, f"Deleted directory: {path.name}"
    except PermissionError:
        return False, f"Permission denied deleting {path}. You may need elevated rights."
    except Exception as e:
        return False, f"Error deleting {path}: {e}"

    return True, "Deleted successfully"


def get_disk_space() -> Tuple[int, int, int]:
    """Returns (total_bytes, used_bytes, free_bytes) on root volume."""
    total, used, free = shutil.disk_usage("/")
    return total, used, free

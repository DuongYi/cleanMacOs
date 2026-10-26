"""macOS System Optimization and Maintenance Tasks (inspired by tw93/Mole)."""

import subprocess
from typing import List, Tuple
from rich.console import Console

console = Console()


def flush_dns() -> Tuple[bool, str]:
    """Flush DNS cache and restart mDNSResponder."""
    try:
        subprocess.run(["dscacheutil", "-flushcache"], check=True, timeout=5)
        subprocess.run(["killall", "-HUP", "mDNSResponder"], check=False, timeout=5)
        return True, "Đã làm mới bộ nhớ đệm DNS (DNS Cache flushed)"
    except Exception as e:
        return False, f"Lỗi làm mới DNS: {e}"


def refresh_quicklook_and_icons() -> Tuple[bool, str]:
    """Reset QuickLook thumbnails and icon services cache."""
    try:
        subprocess.run(["qlmanage", "-r"], capture_output=True, timeout=5)
        subprocess.run(["qlmanage", "-r", "cache"], capture_output=True, timeout=5)
        return True, "Đã khởi động lại dịch vụ QuickLook & Icon thumbnails"
    except Exception as e:
        return False, f"Lỗi làm mới QuickLook: {e}"


def prevent_ds_store_on_external() -> Tuple[bool, str]:
    """Configure macOS Finder to stop creating .DS_Store files on network and USB drives."""
    try:
        subprocess.run(
            ["defaults", "write", "com.apple.desktopservices", "DSDontWriteNetworkStores", "-bool", "true"],
            check=True,
            timeout=5,
        )
        subprocess.run(
            ["defaults", "write", "com.apple.desktopservices", "DSDontWriteUSBStores", "-bool", "true"],
            check=True,
            timeout=5,
        )
        return True, "Đã bật tính năng chặn tự động tạo .DS_Store trên USB và ổ đĩa mạng"
    except Exception as e:
        return False, f"Lỗi cấu hình .DS_Store: {e}"


def clear_quarantine_history() -> Tuple[bool, str]:
    """Clear macOS Gatekeeper download history database."""
    cmd = (
        'sqlite3 ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV* '
        '"DELETE FROM QuarantineEvents;" 2>/dev/null || true'
    )
    try:
        subprocess.run(cmd, shell=True, check=True, timeout=5)
        return True, "Đã dọn dẹp lịch sử theo dõi Quarantine của Gatekeeper"
    except Exception as e:
        return False, f"Lỗi xoá Quarantine: {e}"


def run_all_optimizations() -> List[Tuple[str, bool, str]]:
    """Execute all system maintenance and optimization tasks."""
    tasks = [
        ("Chặn tạo rác .DS_Store trên USB & Mạng", prevent_ds_store_on_external),
        ("Làm mới bộ nhớ đệm DNS", flush_dns),
        ("Làm mới QuickLook & Icon Thumbnails", refresh_quicklook_and_icons),
        ("Dọn dẹp lịch sử Quarantine", clear_quarantine_history),
    ]

    results = []
    for title, func in tasks:
        ok, msg = func()
        results.append((title, ok, msg))
    return results

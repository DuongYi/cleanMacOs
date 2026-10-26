"""macOS LaunchAgent scheduler for automated background maintenance."""

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape

from mclean.utils.disk import TOOL_DIRS

LABEL = "com.mclean.autoclean"
ALERT_LABEL = "com.mclean.diskalert"
ALERT_INTERVAL_HOURS = 3
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"
ALERT_PLIST_PATH = LAUNCH_AGENTS_DIR / f"{ALERT_LABEL}.plist"
LOG_OUT = Path.home() / ".config" / "mclean" / "autoclean.log"
LOG_ERR = Path.home() / ".config" / "mclean" / "autoclean_err.log"


def get_mclean_executable_path() -> Path:
    """Find the full path to mclean executable."""
    local_bin = Path.home() / ".local" / "bin" / "mclean"
    if local_bin.exists():
        return local_bin

    which_path = shutil.which("mclean")
    if which_path:
        return Path(which_path)

    # Fallback to current project root wrapper
    current_root = Path(__file__).resolve().parents[3] / "mclean"
    return current_root


def _plist_xml(label: str, args: List[str], timing_xml: str) -> str:
    """launchd agent plist with escaped arguments and a PATH that finds brew, uv, docker…"""
    args_xml = "\n".join(f"        <string>{escape(a)}</string>" for a in args)
    path_env = ":".join(TOOL_DIRS + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{escape(label)}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{escape(path_env)}</string>
    </dict>
{timing_xml}
    <key>StandardOutPath</key>
    <string>{escape(str(LOG_OUT))}</string>
    <key>StandardErrorPath</key>
    <string>{escape(str(LOG_ERR))}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def generate_plist_content(mclean_path: Path, weekday: int = 1, hour: int = 9, minute: int = 0) -> str:
    """Weekly auto-clean. mclean itself sends the notification with the real result."""
    timing = f"""    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>{weekday}</integer>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>"""
    return _plist_xml(LABEL, [str(mclean_path), "clean", "--force", "--notify"], timing)


def generate_alert_plist_content(mclean_path: Path, interval_hours: int = ALERT_INTERVAL_HOURS) -> str:
    """Periodic low-disk check. It only notifies, it never deletes anything."""
    timing = f"""    <key>StartInterval</key>
    <integer>{interval_hours * 3600}</integer>"""
    return _plist_xml(ALERT_LABEL, [str(mclean_path), "check-space", "--notify"], timing)


def _load_agent(plist_path: Path, plist_xml: str) -> Tuple[bool, str]:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist_xml)
    res = subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, text=True)
    return res.returncode == 0, res.stderr.strip()


def _unload_agent(plist_path: Path) -> None:
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    plist_path.unlink(missing_ok=True)


def _agent_status(plist_path: Path, label: str) -> Dict[str, str]:
    if not plist_path.exists():
        return {"installed": "Chưa cài đặt", "status": "Không hoạt động", "path": str(plist_path)}
    try:
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        loaded = label in res.stdout
        return {
            "installed": "Đã cài đặt",
            "status": "Đã nạp vào launchd (chờ tới giờ chạy)" if loaded else "Có file plist nhưng chưa nạp",
            "path": str(plist_path),
        }
    except Exception:
        return {"installed": "Đã cài đặt", "status": "Không rõ trạng thái", "path": str(plist_path)}


def install_disk_alert(interval_hours: int = ALERT_INTERVAL_HOURS) -> Tuple[bool, str]:
    try:
        ok, err = _load_agent(ALERT_PLIST_PATH, generate_alert_plist_content(get_mclean_executable_path(), interval_hours))
    except Exception as e:
        return False, f"Lỗi cài cảnh báo ổ đầy: {e}"
    if ok:
        return True, f"Đã bật cảnh báo ổ đầy: kiểm tra mỗi {interval_hours} giờ, báo tối đa 1 lần/ngày."
    return False, f"Lỗi nạp launchctl: {err}"


def remove_disk_alert() -> Tuple[bool, str]:
    if not ALERT_PLIST_PATH.exists():
        return True, "Cảnh báo ổ đầy chưa được bật."
    try:
        _unload_agent(ALERT_PLIST_PATH)
        return True, "Đã tắt cảnh báo ổ đầy."
    except Exception as e:
        return False, f"Lỗi tắt cảnh báo: {e}"


def get_disk_alert_status() -> Dict[str, str]:
    return _agent_status(ALERT_PLIST_PATH, ALERT_LABEL)


def install_schedule(weekday: int = 1, hour: int = 9, minute: int = 0) -> Tuple[bool, str]:
    """Install and load the weekly auto-clean agent."""
    try:
        ok, err = _load_agent(PLIST_PATH, generate_plist_content(get_mclean_executable_path(), weekday, hour, minute))
    except Exception as e:
        return False, f"Lỗi cài đặt lịch: {e}"
    if ok:
        days = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]
        return True, f"Đã kích hoạt lịch dọn tự động ngầm: Mỗi {days[weekday % 7]} lúc {hour:02d}:{minute:02d}."
    return False, f"Lỗi nạp launchctl: {err}"


def remove_schedule() -> Tuple[bool, str]:
    """Unload and delete the weekly auto-clean agent."""
    if not PLIST_PATH.exists():
        return True, "Chưa có lịch dọn dẹp nào được thiết lập."
    try:
        _unload_agent(PLIST_PATH)
        return True, "Đã huỷ bỏ lịch dọn dẹp ngầm thành công."
    except Exception as e:
        return False, f"Lỗi huỷ lịch: {e}"


def get_schedule_status() -> Dict[str, str]:
    """Check if the weekly auto-clean agent is installed and loaded."""
    return _agent_status(PLIST_PATH, LABEL)

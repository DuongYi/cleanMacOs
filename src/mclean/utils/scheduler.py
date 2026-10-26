"""macOS LaunchAgent scheduler for automated background maintenance."""

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Tuple
from xml.sax.saxutils import escape

from mclean.utils.disk import TOOL_DIRS

PLIST_NAME = "com.mclean.autoclean.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_NAME
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


def generate_plist_content(mclean_path: Path, weekday: int = 1, hour: int = 9, minute: int = 0) -> str:
    """Generate launchd XML plist content. mclean itself sends the notification with the real result."""
    args = [str(mclean_path), "clean", "--force", "--notify"]
    args_xml = "\n".join(f"        <string>{escape(a)}</string>" for a in args)
    path_env = ":".join(TOOL_DIRS + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mclean.autoclean</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{escape(path_env)}</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>{weekday}</integer>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{escape(str(LOG_OUT))}</string>
    <key>StandardErrorPath</key>
    <string>{escape(str(LOG_ERR))}</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def install_schedule(weekday: int = 1, hour: int = 9, minute: int = 0) -> Tuple[bool, str]:
    """Install and load the launchd agent."""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)

    mclean_path = get_mclean_executable_path()
    plist_xml = generate_plist_content(mclean_path, weekday=weekday, hour=hour, minute=minute)

    try:
        # Unload old plist if present
        if PLIST_PATH.exists():
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)

        with open(PLIST_PATH, "w", encoding="utf-8") as f:
            f.write(plist_xml)

        res = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
        if res.returncode == 0:
            days = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"]
            day_name = days[weekday % 7]
            return True, f"Đã kích hoạt lịch dọn tự động ngầm: Mỗi {day_name} lúc {hour:02d}:{minute:02d}."
        else:
            return False, f"Lỗi nạp launchctl: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Lỗi cài đặt lịch: {e}"


def remove_schedule() -> Tuple[bool, str]:
    """Unload and delete launchd agent."""
    if not PLIST_PATH.exists():
        return True, "Chưa có lịch dọn dẹp nào được thiết lập."

    try:
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
        PLIST_PATH.unlink(missing_ok=True)
        return True, "Đã huỷ bỏ lịch dọn dẹp ngầm thành công."
    except Exception as e:
        return False, f"Lỗi huỷ lịch: {e}"


def get_schedule_status() -> Dict[str, str]:
    """Check if the LaunchAgent is currently installed and active."""
    if not PLIST_PATH.exists():
        return {"installed": "Chưa cài đặt", "status": "Không hoạt động", "path": str(PLIST_PATH)}

    try:
        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        is_active = "com.mclean.autoclean" in res.stdout
        status_text = "Đang chạy định kỳ (Đã kích hoạt)" if is_active else "Đã cài đặt (Chờ tới giờ chạy)"
        return {"installed": "Đã cài đặt", "status": status_text, "path": str(PLIST_PATH)}
    except Exception:
        return {"installed": "Đã cài đặt", "status": "Không rõ trạng thái", "path": str(PLIST_PATH)}

"""`mclean doctor`: health checks for mclean itself and for things that make caches come back."""

import json
import os
import plistlib
import re
import subprocess
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from mclean import config
from mclean.utils.disk import find_tool, get_disk_space
from mclean.utils.formatters import format_size, format_timestamp
from mclean.utils.projects import referenced_gradle_dists
from mclean.utils.scheduler import ALERT_PLIST_PATH, PLIST_PATH
from mclean.utils.state import load_state

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"

# (extensions folder, settings folder name under ~/Library/Application Support, display name)
VSCODE_FAMILY = [
    (".vscode", "Code", "VS Code"),
    (".cursor", "Cursor", "Cursor"),
    (".windsurf", "Windsurf", "Windsurf"),
    (".antigravity", "Antigravity", "Antigravity"),
    (".antigravity-ide", "Antigravity IDE", "Antigravity IDE"),
]
# Defaults of redhat.java's java.import.exclusions; a user value replaces them, so keep them
JAVA_IMPORT_DEFAULT_EXCLUSIONS = ["**/node_modules/**", "**/.metadata/**", "**/archetype-resources/**", "**/META-INF/maven/**"]
FLUTTER_EXCLUSIONS = ["**/.symlinks/**", "**/.pub-cache/**"]
RECENT_DAYS = 14


@dataclass
class Check:
    status: str
    title: str
    detail: str
    fix: str = ""


def load_jsonc(path: Path) -> Optional[Dict[str, Any]]:
    """Parse a VS Code settings.json (comments and trailing commas allowed)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    out, i, in_str = [], 0, False
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        else:
            out.append(ch)
        i += 1
    cleaned = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    try:
        data = json.loads(cleaned or "{}")
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _real_executable(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return path


# --- individual checks -------------------------------------------------------

def check_config() -> List[Check]:
    if config.CONFIG_FILE.exists():
        try:
            json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))
        except ValueError:
            return [Check(FAIL, "File cấu hình", f"{config.CONFIG_FILE} không phải JSON hợp lệ, đang dùng giá trị mặc định.",
                          "mclean config reset")]
    roots = config.project_roots()
    if not roots:
        return [Check(WARN, "Thư mục dự án", "Không thư mục dự án nào trong cấu hình tồn tại, nên không dự án nào được quét.",
                      "mclean config add-root ~/đường/dẫn/tới/dự-án")]
    return [Check(OK, "Thư mục dự án", f"Quét {len(roots)} thư mục: " + ", ".join(str(r).replace(str(Path.home()), "~") for r in roots))]


def _plist_check(path: Path, label: str, title: str, expected_arg: str, install_cmd: str, required: bool) -> Check:
    if not path.exists():
        status = WARN if required else INFO
        return Check(status, title, "Chưa bật.", install_cmd)
    try:
        plist = plistlib.loads(path.read_bytes())
    except Exception:
        return Check(FAIL, title, "File plist sai cú pháp (bản cũ của mclean).", install_cmd)
    args = plist.get("ProgramArguments", [])
    if not args or not Path(args[0]).exists():
        return Check(FAIL, title, f"Trỏ tới chương trình không tồn tại: {args[0] if args else '(trống)'}", install_cmd)
    if expected_arg not in args:
        return Check(WARN, title, "Plist được tạo bởi phiên bản mclean cũ.", install_cmd)
    loaded = label in subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    if not loaded:
        return Check(WARN, title, "Có file plist nhưng chưa nạp vào launchd.", install_cmd)
    return Check(OK, title, "Đã bật và nạp vào launchd.")


def check_schedules() -> List[Check]:
    return [
        _plist_check(PLIST_PATH, "com.mclean.autoclean", "Lịch dọn hàng tuần", "--notify",
                     "mclean schedule --install", required=False),
        _plist_check(ALERT_PLIST_PATH, "com.mclean.diskalert", "Cảnh báo ổ đầy", "check-space",
                     "mclean schedule --alert-on", required=False),
    ]


def check_last_auto_clean() -> List[Check]:
    last = load_state().get("last_auto_clean")
    if not last:
        return [Check(INFO, "Lần dọn tự động gần nhất", "Chưa có lần chạy nào được ghi lại.")]
    checks = [Check(
        OK if not last.get("failed") else WARN,
        "Lần dọn tự động gần nhất",
        f"{last.get('time', '?').replace('T', ' ')}: giải phóng {format_size(last.get('reclaimed_bytes', 0))}, "
        f"{last.get('failed', 0)} lỗi, {last.get('blocked', 0)} mục bỏ qua vì ứng dụng đang mở.",
    )]
    blocked_dirs = [p.replace(str(Path.home()), "~") for p, ok in last.get("readable", {}).items() if not ok]
    if blocked_dirs:
        exe = _real_executable(last.get("executable", ""))
        checks.append(Check(
            WARN,
            "Quyền truy cập của job chạy nền",
            f"Job không đọc được {', '.join(blocked_dirs)}, nên dự án và Thùng rác ở đó bị bỏ qua.",
            "Cài đặt hệ thống → Quyền riêng tư & Bảo mật → Truy cập toàn bộ ổ đĩa → nút + → "
            f"Cmd+Shift+G, dán: {exe}",
        ))
    return checks


def check_terminal_access() -> List[Check]:
    try:
        next(os.scandir(Path.home() / ".Trash"), None)
        return [Check(OK, "Quyền của Terminal", "Đọc được Thùng rác và thư mục người dùng.")]
    except PermissionError:
        return [Check(WARN, "Quyền của Terminal", "Terminal không đọc được ~/.Trash, nên không dọn được Thùng rác.",
                      "Cấp \"Truy cập toàn bộ ổ đĩa\" cho ứng dụng Terminal bạn đang dùng.")]
    except OSError:
        return []


def _pub_cache_projects_opened_by_gradle() -> List[str]:
    """Plugin projects inside ~/.pub-cache that a Gradle daemon opened recently (IDE import)."""
    cutoff = time.time() - RECENT_DAYS * 86400
    found = set()
    pattern = re.compile(r"\.pub-cache/hosted/[^/]+/([^/\s']+)/(?:example/)?android")
    for log in (Path.home() / ".gradle" / "daemon").glob("*/daemon-*.out.log"):
        try:
            if log.stat().st_mtime < cutoff:
                continue
            with open(log, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if ".pub-cache/hosted/" in line:
                        found.update(pattern.findall(line))
        except OSError:
            continue
    return sorted(found)


def _recently_downloaded_unreferenced_gradle() -> List[str]:
    cutoff = time.time() - RECENT_DAYS * 86400
    referenced = referenced_gradle_dists()
    fresh = []
    for marker in (Path.home() / ".gradle" / "wrapper" / "dists").glob("gradle-*/*/*.zip.ok"):
        dist = marker.parent.parent.name
        try:
            if marker.stat().st_mtime > cutoff and dist not in referenced:
                fresh.append(dist)
        except OSError:
            continue
    return sorted(set(fresh))


def check_ide_gradle_import() -> List[Check]:
    checks = []
    plugin_projects = _pub_cache_projects_opened_by_gradle()
    fresh_dists = _recently_downloaded_unreferenced_gradle()
    evidence = []
    if plugin_projects:
        shown = ", ".join(plugin_projects[:5]) + ("…" if len(plugin_projects) > 5 else "")
        evidence.append(f"Gradle đã mở {len(plugin_projects)} plugin trong ~/.pub-cache như project riêng ({shown})")
    if fresh_dists:
        evidence.append(f"đã tải {len(fresh_dists)} bản Gradle không dự án nào của bạn dùng ({', '.join(fresh_dists)})")
    if evidence:
        checks.append(Check(
            FAIL,
            "Gradle bị tải lại ngầm",
            f"Trong {RECENT_DAYS} ngày qua: " + "; ".join(evidence) + ". Thủ phạm thường là extension Java/Gradle của IDE (xem dòng dưới).",
        ))

    for ext_dir, support_name, display in VSCODE_FAMILY:
        extensions = Path.home() / ext_dir / "extensions"
        has_java = any(extensions.glob("redhat.java-*"))
        has_gradle = any(extensions.glob("vscjava.vscode-gradle-*"))
        if not (has_java or has_gradle):
            continue
        settings_path = Path.home() / "Library" / "Application Support" / support_name / "User" / "settings.json"
        settings = load_jsonc(settings_path) if settings_path.exists() else {}
        if settings is None:
            checks.append(Check(INFO, f"Import Gradle của {display}", f"Không đọc được {settings_path}."))
            continue

        exclusions = settings.get("java.import.exclusions", JAVA_IMPORT_DEFAULT_EXCLUSIONS)
        java_safe = (not has_java) or settings.get("java.import.gradle.enabled") is False or all(
            pattern in exclusions for pattern in FLUTTER_EXCLUSIONS
        )
        gradle_safe = (not has_gradle) or settings.get("gradle.autoDetect") == "off"
        if java_safe and gradle_safe:
            checks.append(Check(OK, f"Import Gradle của {display}", "Không import plugin trong ~/.pub-cache."))
            continue

        snippet = {}
        if not java_safe:
            snippet["java.import.exclusions"] = list(dict.fromkeys([*exclusions, *FLUTTER_EXCLUSIONS]))
        if not gradle_safe:
            snippet["gradle.autoDetect"] = "off"
        body = textwrap.dedent("\n".join(json.dumps(snippet, indent=2, ensure_ascii=False).splitlines()[1:-1]))
        checks.append(Check(
            FAIL if evidence else WARN,
            f"Import Gradle của {display}",
            "Extension Java/Gradle đi theo symlink ios/.symlinks/plugins vào ~/.pub-cache, mở từng plugin như project "
            "Android riêng và tải Gradle wrapper của plugin đó.",
            f"Thêm vào {str(settings_path).replace(str(Path.home()), '~')} (nhớ thêm dấu phẩy nếu cần):\n{body}",
        ))
    return checks


def check_tools() -> List[Check]:
    tools = ["xcrun", "brew", "docker", "ollama", "uv", "pnpm"]
    found = [t for t in tools if find_tool(t)]
    missing = [t for t in tools if t not in found]
    detail = "Tìm thấy: " + (", ".join(found) or "không có")
    if missing:
        detail += f". Không có (các mục liên quan được bỏ qua): {', '.join(missing)}"
    return [Check(INFO, "Công cụ dòng lệnh", detail)]


def check_disk() -> List[Check]:
    total, _used, free = get_disk_space()
    pct = free / total * 100
    threshold = config.setting("low_disk_percent")
    if pct < threshold:
        return [Check(WARN, "Dung lượng trống", f"Còn {format_size(free)} ({pct:.1f}%), dưới ngưỡng {threshold}%.", "mclean")]
    return [Check(OK, "Dung lượng trống", f"Còn {format_size(free)} ({pct:.1f}%), ngưỡng cảnh báo {threshold}%.")]


ALL_CHECKS = [check_disk, check_config, check_schedules, check_last_auto_clean, check_terminal_access,
              check_ide_gradle_import, check_tools]


def run_checks() -> List[Check]:
    results: List[Check] = []
    for fn in ALL_CHECKS:
        try:
            results.extend(fn())
        except Exception as e:  # a broken check must not hide the others
            results.append(Check(INFO, fn.__name__, f"Không kiểm tra được: {e}"))
    return results

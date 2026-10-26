"""Process guard to prevent deleting caches while applications are running."""

from typing import List, Tuple
import psutil

# Map of friendly name to process binary substrings
DEV_PROCESS_PATTERNS = {
    "Xcode": ["Xcode", "xcodebuild", "ibtool"],
    "iOS Simulator": ["Simulator", "launchd_sim"],
    "Android Studio / Emulator": ["studio", "emulator", "qemu-system-aarch64", "qemu-system-x86_64"],
    "Flutter / Dart": ["flutter_tools", "dart"],
    "Gradle Daemon": ["GradleDaemon"],
    "Ollama": ["ollama"],
    "LM Studio": ["LM Studio"],
    "Docker": ["Docker", "com.docker.backend"],
}


def get_active_dev_processes() -> List[Tuple[str, int]]:
    """Scan running processes and return list of (friendly_name, pid)."""
    running: List[Tuple[str, int]] = []
    seen_names = set()

    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info["name"] or ""
                pid = proc.info["pid"]
                for friendly, patterns in DEV_PROCESS_PATTERNS.items():
                    if friendly not in seen_names and any(pat.lower() in pname.lower() for pat in patterns):
                        running.append((friendly, pid))
                        seen_names.add(friendly)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass

    return running


def check_conflicts_for_category(category_name: str) -> List[str]:
    """Check if any running process conflicts with a cleaning category."""
    running = get_active_dev_processes()
    conflicts = []
    cat_lower = category_name.lower()

    for name, pid in running:
        if "xcode" in cat_lower and name in ("Xcode", "iOS Simulator"):
            conflicts.append(f"{name} (PID: {pid})")
        elif "android" in cat_lower and name in ("Android Studio / Emulator", "Gradle Daemon"):
            conflicts.append(f"{name} (PID: {pid})")
        elif "flutter" in cat_lower and name in ("Flutter / Dart", "Xcode", "Android Studio / Emulator"):
            conflicts.append(f"{name} (PID: {pid})")
        elif "ai" in cat_lower and name in ("Ollama", "LM Studio"):
            conflicts.append(f"{name} (PID: {pid})")

    return conflicts

"""Process guard to prevent deleting caches while applications are running."""

import re
from typing import Dict, List, Set, Tuple

import psutil

from mclean.models import Category, CleanTarget

# Friendly name -> (process field, regex). Name rules are anchored so that e.g.
# "LM Studio" is not mistaken for Android Studio.
DEV_PROCESS_RULES: Dict[str, List[Tuple[str, str]]] = {
    "Xcode": [("name", r"^(Xcode|xcodebuild|ibtool)$")],
    "iOS Simulator": [("name", r"^(Simulator|launchd_sim)$")],
    "Android Studio / Emulator": [("name", r"^(studio|emulator|qemu-system-.+)$")],
    "Flutter / Dart": [("name", r"^(dart|dartvm|flutter)$"), ("cmdline", r"flutter_tools")],
    "Gradle Daemon": [("cmdline", r"GradleDaemon|GradleWrapperMain")],
    "Ollama": [("name", r"^ollama")],
    "LM Studio": [("name", r"^LM Studio")],
    "Docker": [("name", r"^(Docker|Docker Desktop|com\.docker\.backend)$")],
    "VS Code": [("exe", r"/Visual Studio Code\.app/")],
    "Cursor": [("exe", r"/Cursor\.app/")],
    "Google Chrome": [("exe", r"/Google Chrome\.app/")],
    "Cốc Cốc": [("exe", r"/(CocCoc|Cốc Cốc)\.app/")],
    "Brave": [("exe", r"/Brave Browser\.app/")],
    "Microsoft Edge": [("exe", r"/Microsoft Edge\.app/")],
    "Firefox": [("exe", r"/Firefox\.app/")],
}

# Apps that use the caches of each category while running
CATEGORY_GUARDS: Dict[Category, Tuple[str, ...]] = {
    Category.XCODE: ("Xcode", "iOS Simulator"),
    Category.ANDROID: ("Android Studio / Emulator", "Gradle Daemon"),
    Category.FLUTTER: ("Flutter / Dart",),
    Category.AI: ("Ollama", "LM Studio"),
}


def _matches(proc_info: dict, field: str, pattern: str) -> bool:
    value = proc_info.get(field)
    if field == "cmdline":
        value = " ".join(value or [])
    return bool(value) and re.search(pattern, value) is not None


def get_active_dev_processes() -> List[Tuple[str, int]]:
    """Scan running processes and return list of (friendly_name, pid)."""
    running: List[Tuple[str, int]] = []
    seen_names = set()

    try:
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                info = proc.info
                for friendly, rules in DEV_PROCESS_RULES.items():
                    if friendly not in seen_names and any(_matches(info, f, p) for f, p in rules):
                        running.append((friendly, info["pid"]))
                        seen_names.add(friendly)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass

    return running


def guard_apps_for_target(target: CleanTarget) -> Tuple[str, ...]:
    """Apps that must be closed before this target is cleaned (scanner override, else by category)."""
    if "guard" in target.metadata:
        return tuple(target.metadata["guard"])
    return CATEGORY_GUARDS.get(target.category, ())


def conflicts_for_target(target: CleanTarget, running: List[Tuple[str, int]]) -> List[str]:
    """Running apps (with PID) that conflict with cleaning this target."""
    guards = guard_apps_for_target(target)
    return [f"{name} (PID: {pid})" for name, pid in running if name in guards]


def running_gradle_dists() -> Set[str]:
    """Wrapper distributions (e.g. 'gradle-9.7.1-bin') that a running Gradle daemon was started from."""
    dists: Set[str] = set()
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        if "GradleDaemon" in cmd:
            dists.update(re.findall(r"wrapper/dists/(gradle-[^/\s]+)", cmd))
    return dists

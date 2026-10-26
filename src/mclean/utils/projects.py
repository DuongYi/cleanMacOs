"""Workspace discovery helpers: which projects exist, what they use, and when they were last touched."""

import os
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from mclean.config import project_roots

# Heavy or generated directories that never contain project sources worth inspecting
PRUNED_DIR_NAMES = {
    ".git", ".dart_tool", ".gradle", ".idea", ".vscode", ".pub-cache", ".symlinks",
    "build", "Pods", "node_modules", "DerivedData", "ephemeral", "Library", ".Trash",
    "Caches", "Application Support", "venv", ".venv", "__pycache__",
}

# Directories that hold activity signals rather than sources
ACTIVITY_MARKERS = [
    ".git/index",                         # touched by commit, checkout, status
    ".git/HEAD",
    ".dart_tool/package_config.json",     # rewritten by every `pub get` / `flutter run`
    ".dart_tool/flutter_build",           # touched by every Flutter build
    "build",
]

GRADLE_DIST_RE = re.compile(r"distributionUrl\s*=.*?/(gradle-[0-9][^/\s]*?-(?:bin|all))\.zip")


def default_roots() -> List[Path]:
    return project_roots()


def is_flutter_sdk(path: Path) -> bool:
    """Flutter SDK checkouts have a pubspec.yaml too; they are not user projects."""
    return (path / "bin" / "flutter").exists() and (path / "packages" / "flutter").is_dir()


def walk_workspace(root: Path):
    """os.walk over a workspace root, skipping generated folders, hidden folders and Flutter SDKs."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        if is_flutter_sdk(current):
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in PRUNED_DIR_NAMES and not d.startswith(".")]
        yield current, dirnames, filenames


def latest_activity(project: Path) -> float:
    """Newest mtime across the project's sources (recursive) and its build/git activity markers."""
    latest = 0.0
    for marker in ACTIVITY_MARKERS:
        try:
            latest = max(latest, (project / marker).stat().st_mtime)
        except OSError:
            pass

    for dirpath, dirnames, filenames in os.walk(project, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in PRUNED_DIR_NAMES and not d.startswith(".")]
        for fname in filenames:
            try:
                latest = max(latest, os.stat(os.path.join(dirpath, fname)).st_mtime)
            except OSError:
                continue
    return latest


@lru_cache(maxsize=8)
def _referenced_gradle_dists(roots: Tuple[Path, ...]) -> frozenset:
    found: Set[str] = set()
    for root in roots:
        for current, dirnames, filenames in walk_workspace(root):
            props = current / "gradle" / "wrapper" / "gradle-wrapper.properties"
            if props.is_file():
                try:
                    m = GRADLE_DIST_RE.search(props.read_text(encoding="utf-8", errors="ignore"))
                    if m:
                        found.add(m.group(1))
                except OSError:
                    pass
    return frozenset(found)


def referenced_gradle_dists(roots: Iterable[Path] = ()) -> Set[str]:
    """Wrapper distributions (e.g. 'gradle-8.10.2-all') referenced by any project under the roots."""
    roots = tuple(sorted(roots)) or tuple(default_roots())
    return set(_referenced_gradle_dists(roots))


def referenced_gradle_versions(roots: Iterable[Path] = ()) -> Set[str]:
    """Bare Gradle versions (e.g. '8.10.2') referenced by any project under the roots."""
    out = set()
    for dist in referenced_gradle_dists(roots):
        m = re.match(r"gradle-(.+)-(?:bin|all)$", dist)
        if m:
            out.add(m.group(1))
    return out


NDK_VERSION_RE = re.compile(r"""ndkVersion\w*\s*[:=]?[^"'\n]*["']([0-9]+\.[0-9]+\.[0-9]+)["']""")
NDK_DIR_RE = re.compile(r"ndk\.dir\s*=.*?/ndk/([0-9]+\.[0-9]+\.[0-9]+)")


def flutter_sdks(roots: Iterable[Path] = ()) -> List[Path]:
    """Flutter SDK checkouts: the one on PATH, fvm versions, and any directly inside the usual folders."""
    home = Path.home()
    candidates: List[Path] = []
    flutter_bin = shutil.which("flutter")
    if flutter_bin:
        candidates.append(Path(flutter_bin).resolve().parents[1])
    for parent in [home / "development", home / "fvm" / "versions", home / "sdk", home, *(roots or default_roots())]:
        try:
            candidates.extend(p for p in parent.iterdir() if p.is_dir())
        except OSError:
            continue
    seen, sdks = set(), []
    for c in candidates:
        if c not in seen and is_flutter_sdk(c):
            seen.add(c)
            sdks.append(c)
    return sdks


def _ndk_refs_in_file(path: Path) -> Set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    return set(NDK_VERSION_RE.findall(text)) | set(NDK_DIR_RE.findall(text))


def referenced_ndk_versions(roots: Iterable[Path] = ()) -> Set[str]:
    """NDK versions named by projects, by Flutter SDK defaults, or by plugins in the pub cache."""
    roots = list(roots) or default_roots()
    found: Set[str] = set()
    for root in roots:
        for current, _dirnames, filenames in walk_workspace(root):
            for fname in filenames:
                if fname.endswith((".gradle", ".gradle.kts")) or fname == "local.properties":
                    found |= _ndk_refs_in_file(current / fname)
    # Flutter projects usually say `ndkVersion = flutter.ndkVersion`, defined inside the SDK
    for sdk in flutter_sdks(roots):
        gradle_src = sdk / "packages" / "flutter_tools" / "gradle" / "src" / "main"
        for f in gradle_src.rglob("*.kt*"):
            found |= _ndk_refs_in_file(f)
        for f in gradle_src.rglob("*.groovy"):
            found |= _ndk_refs_in_file(f)
    # Plugins compile with their own ndkVersion when they declare one
    for f in (Path.home() / ".pub-cache" / "hosted").glob("*/*/android/build.gradle*"):
        found |= _ndk_refs_in_file(f)
    return found

"""Shared cleanup engine: process guard, deletion, measured reclaim and history."""

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from mclean.models import CleanTarget
from mclean.scanners.base import clean_target
from mclean.utils.disk import get_disk_space
from mclean.utils.guard import conflicts_for_target, get_active_dev_processes
from mclean.utils.history import record_cleanup


@dataclass
class CleanReport:
    reclaimed: int = 0
    cleaned: List[CleanTarget] = field(default_factory=list)
    failed: List[Tuple[CleanTarget, str]] = field(default_factory=list)


def split_by_running_apps(targets: List[CleanTarget]) -> Tuple[List[CleanTarget], List[Tuple[CleanTarget, List[str]]]]:
    """Separate targets that an open app is using right now from the ones that are free to clean."""
    running = get_active_dev_processes()
    free: List[CleanTarget] = []
    blocked: List[Tuple[CleanTarget, List[str]]] = []
    for t in targets:
        conflicts = conflicts_for_target(t, running)
        if conflicts:
            blocked.append((t, conflicts))
        else:
            free.append(t)
    return free, blocked


def _measured_bytes(target: CleanTarget, existed: bool, free_before: int) -> int:
    """Bytes actually freed: disk delta for commands, scanned size only if the path is really gone."""
    if target.item_type == "command":
        return max(0, get_disk_space()[2] - free_before)
    if target.item_type in ("paths", "contents"):
        return target.size_bytes
    if existed and not target.path.exists():
        return target.size_bytes
    return 0


def execute_clean(
    targets: List[CleanTarget],
    on_start: Optional[Callable[[CleanTarget], None]] = None,
) -> CleanReport:
    """Clean targets in order, measure what was freed and record it in history."""
    report = CleanReport()
    for t in targets:
        if on_start:
            on_start(t)
        existed = t.path.exists()
        free_before = get_disk_space()[2]
        ok, msg = clean_target(t)
        if ok:
            report.reclaimed += _measured_bytes(t, existed, free_before)
            report.cleaned.append(t)
        else:
            report.failed.append((t, msg))

    if report.reclaimed > 0:
        record_cleanup(report.reclaimed, [t.name for t in report.cleaned])
    return report

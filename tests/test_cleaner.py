from mclean.cleaner import execute_clean, split_by_running_apps
from mclean.models import Category, CleanTarget
from mclean.scanners.base import clean_target
from mclean.utils.history import load_history

from conftest import MB, write


def test_trash_contents_are_really_deleted(tmp_path):
    trash = tmp_path / "Trash"
    write(trash / "a.bin")
    write(trash / "folder" / "b.bin")
    ok, _ = clean_target(CleanTarget("Trash", Category.TRASH, trash, 1, item_type="contents"))
    assert ok
    assert trash.is_dir() and not any(trash.iterdir())


def test_contents_respects_exclusions(tmp_path):
    logs = tmp_path / "Logs"
    write(logs / "App" / "x.log")
    write(logs / "DiagnosticReports" / "crash.ips")
    target = CleanTarget("Logs", Category.SYSTEM, logs, 1, item_type="contents", metadata={"exclude": ["DiagnosticReports"]})
    assert clean_target(target)[0]
    assert sorted(p.name for p in logs.iterdir()) == ["DiagnosticReports"]


def test_missing_path_frees_nothing_and_is_not_recorded(tmp_path, no_running_apps):
    ghost = CleanTarget("ghost", Category.SYSTEM, tmp_path / "gone", 5 * MB)
    report = execute_clean([ghost])
    assert report.reclaimed == 0
    assert load_history() == []


def test_deleted_path_is_measured_and_recorded(tmp_path, no_running_apps):
    folder = tmp_path / "cache"
    write(folder / "blob", b"0" * 1024)
    report = execute_clean([CleanTarget("cache", Category.SYSTEM, folder, 3 * MB)])
    assert report.reclaimed == 3 * MB and not folder.exists()
    assert load_history()[0]["reclaimed_bytes"] == 3 * MB


def test_targets_in_use_by_running_apps_are_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr("mclean.cleaner.get_active_dev_processes", lambda: [("Xcode", 42), ("VS Code", 7)])
    xcode_cache = CleanTarget("Xcode App Cache", Category.XCODE, tmp_path / "a", 1)
    vscode_cache = CleanTarget("VS Code Cache", Category.AI, tmp_path / "b", 1, metadata={"guard": ["VS Code"]})
    flutter_build = CleanTarget("Inactive project", Category.FLUTTER, tmp_path / "c", 1, metadata={"guard": []})
    free, blocked = split_by_running_apps([xcode_cache, vscode_cache, flutter_build])
    assert free == [flutter_build]
    assert [t.name for t, _ in blocked] == ["Xcode App Cache", "VS Code Cache"]

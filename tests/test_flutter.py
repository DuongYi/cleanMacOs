import os
import time

import pytest

from mclean.cleaner import execute_clean
from mclean.scanners import flutter_dart
from mclean.scanners.flutter_dart import FlutterDartScanner

from conftest import MB, write

OLD = time.time() - 60 * 86400


def make_project(path, edited_today=False):
    write(path / "pubspec.yaml", b"name: app")
    write(path / "lib" / "main.dart")
    write(path / "lib" / "src" / "feature.dart")
    write(path / "build" / "app.apk")
    write(path / ".dart_tool" / "flutter_build" / "kernel.dill")
    write(path / ".dart_tool" / "package_config.json", b"{}")
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            os.utime(os.path.join(root, name), (OLD, OLD))
    if edited_today:
        (path / "lib" / "src" / "feature.dart").write_text("edited today")
    return path


@pytest.fixture
def scan(monkeypatch):
    monkeypatch.setattr(flutter_dart, "get_path_size", lambda p: 40 * MB)

    def run(root):
        targets = FlutterDartScanner(workspace_roots=[root]).scan_workspace_for_inactive_projects(root, 14)
        return {t.metadata["project_path"].name: t for t in targets}

    return run


def test_edit_in_nested_lib_folder_keeps_project_active(tmp_path, scan):
    make_project(tmp_path / "busy_app", edited_today=True)
    assert "busy_app" not in scan(tmp_path)


def test_inactive_project_inside_folder_named_flutter_is_found(tmp_path, scan):
    make_project(tmp_path / "flutter" / "old_app")
    assert "old_app" in scan(tmp_path)


def test_flutter_sdk_checkout_is_not_treated_as_project(tmp_path, scan):
    sdk = tmp_path / "flutter344"
    write(sdk / "bin" / "flutter")
    (sdk / "packages" / "flutter").mkdir(parents=True)
    make_project(sdk)
    assert scan(tmp_path) == {}


def test_cleanup_keeps_package_config_so_no_pub_get_is_needed(tmp_path, scan, no_running_apps):
    project = make_project(tmp_path / "old_app")
    target = scan(tmp_path)["old_app"]
    assert target.size_bytes == 80 * MB  # build/ + .dart_tool/flutter_build/, exactly what gets deleted

    execute_clean([target])
    assert not (project / "build").exists()
    assert not (project / ".dart_tool" / "flutter_build").exists()
    assert (project / ".dart_tool" / "package_config.json").exists()
    assert (project / "lib" / "main.dart").exists()


def test_workspace_root_that_cannot_be_deleted_is_still_scanned(tmp_path, scan, monkeypatch):
    # ~/Desktop is a critical root (never deleted as a whole) but holds most projects
    from mclean import config
    monkeypatch.setattr(config, "CRITICAL_ROOTS", {tmp_path})
    make_project(tmp_path / "old_app")
    assert "old_app" in scan(tmp_path)


def test_ignored_workspace_is_not_scanned(tmp_path, scan):
    from mclean.config import save_ignored_paths
    make_project(tmp_path / "old_app")
    save_ignored_paths({tmp_path})
    assert scan(tmp_path) == {}

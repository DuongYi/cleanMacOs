"""node_modules, Pods and browser caches are offered for review only, never cleaned automatically."""

import os
import time

import pytest

from mclean.cleaner import split_by_running_apps
from mclean.models import RiskTier
from mclean.scanners import browsers, project_deps
from mclean.scanners.browsers import BrowserScanner
from mclean.scanners.project_deps import ProjectDepsScanner

from conftest import MB, write

OLD = time.time() - 60 * 86400


def age(path):
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            os.utime(os.path.join(root, name), (OLD, OLD))
    os.utime(path, (OLD, OLD))


@pytest.fixture
def deps(monkeypatch):
    monkeypatch.setattr(project_deps, "get_path_size", lambda p: 300 * MB)

    def run(root):
        return {t.path.relative_to(root).as_posix(): t for t in ProjectDepsScanner(workspace_roots=[root]).scan_root(root)}

    return run


def test_inactive_node_and_pods_are_review(tmp_path, deps):
    write(tmp_path / "web" / "package.json", b"{}")
    write(tmp_path / "web" / "node_modules" / "react" / "index.js")
    write(tmp_path / "mobile" / "pubspec.yaml", b"name: app")
    write(tmp_path / "mobile" / "ios" / "Podfile")
    write(tmp_path / "mobile" / "ios" / "Pods" / "Firebase" / "a.h")
    age(tmp_path)

    found = deps(tmp_path)
    assert set(found) == {"web/node_modules", "mobile/ios/Pods"}
    assert all(t.risk_tier == RiskTier.TIER2_REVIEW for t in found.values())
    # Pods belong to the Flutter project, not to ios/
    assert found["mobile/ios/Pods"].metadata["project_path"] == tmp_path / "mobile"


def test_active_projects_keep_their_dependencies(tmp_path, deps):
    write(tmp_path / "web" / "package.json", b"{}")
    write(tmp_path / "web" / "node_modules" / "react" / "index.js")
    age(tmp_path)
    write(tmp_path / "web" / "src" / "App.tsx", b"edited today")
    assert deps(tmp_path) == {}


def test_browser_cache_is_review_and_skipped_while_browser_runs(tmp_path, monkeypatch):
    cache = tmp_path / "Google" / "Chrome"
    cache.mkdir(parents=True)
    monkeypatch.setattr(browsers, "BROWSER_CACHES", [("Google Chrome", str(cache), "Google Chrome")])
    monkeypatch.setattr(browsers, "get_batch_sizes", lambda paths: {p: 500 * MB for p in paths})

    [target] = BrowserScanner().scan()
    assert target.risk_tier == RiskTier.TIER2_REVIEW

    monkeypatch.setattr("mclean.cleaner.get_active_dev_processes", lambda: [("Google Chrome", 99)])
    free, blocked = split_by_running_apps([target])
    assert free == [] and blocked[0][0] is target

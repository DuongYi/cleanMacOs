"""config.json settings, grouped choices, low-disk alert and doctor."""

import json
import plistlib
import time
from pathlib import Path

import questionary
from typer.testing import CliRunner

from mclean import cli, config, doctor
from mclean.config import load_settings, project_roots, save_settings, setting
from mclean.models import Category, CleanTarget, RiskTier
from mclean.utils.scheduler import generate_alert_plist_content
from mclean.utils.state import load_state

from conftest import MB, write

runner = CliRunner()


# --- 4. config.json ------------------------------------------------------------

def test_defaults_without_config_file():
    assert setting("inactive_days") == 14
    assert setting("low_disk_percent") == 15


def test_saved_settings_override_defaults_and_bad_values_are_ignored(isolated_config):
    config.CONFIG_FILE.write_text(json.dumps({"inactive_days": 30, "gradle_idle_days": -5, "bogus": 1}))
    s = load_settings()
    assert s["inactive_days"] == 30
    assert s["gradle_idle_days"] == 30  # negative value ignored, default kept
    assert "bogus" not in s


def test_only_changed_values_are_written():
    s = load_settings()
    s["inactive_days"] = 21
    save_settings(s)
    assert json.loads(config.CONFIG_FILE.read_text()) == {"inactive_days": 21}


def test_config_cli_set_and_roots(tmp_path):
    assert runner.invoke(cli.app, ["config", "set", "inactive_days", "30"]).exit_code == 0
    assert setting("inactive_days") == 30
    assert runner.invoke(cli.app, ["config", "set", "inactive_days", "abc"]).exit_code == 2
    assert runner.invoke(cli.app, ["config", "set", "low_disk_percent", "150"]).exit_code == 2

    projects = tmp_path / "MyProjects"
    projects.mkdir()
    assert runner.invoke(cli.app, ["config", "add-root", str(projects)]).exit_code == 0
    assert projects.resolve() in [p.resolve() for p in project_roots()]
    assert runner.invoke(cli.app, ["config", "remove-root", str(projects)]).exit_code == 0
    assert projects.resolve() not in [p.resolve() for p in project_roots()]

    assert runner.invoke(cli.app, ["config", "reset"]).exit_code == 0
    assert setting("inactive_days") == 14


def test_scanners_follow_configured_inactive_days(tmp_path):
    from mclean.scanners.flutter_dart import FlutterDartScanner
    save_settings({**load_settings(), "inactive_days": 45})
    assert FlutterDartScanner(workspace_roots=[tmp_path]).inactive_days == 45


# --- 5. grouped choices -----------------------------------------------------------

def test_choices_grouped_by_category_largest_first_safe_checked():
    targets = [
        CleanTarget("Chrome Cache", Category.BROWSER, Path("/x"), 900 * MB, RiskTier.TIER2_REVIEW),
        CleanTarget("Old NDK", Category.ANDROID, Path("/y"), 3000 * MB, RiskTier.TIER2_REVIEW),
        CleanTarget("x86 image", Category.ANDROID, Path("/z"), 100 * MB, RiskTier.TIER1_SAFE),
        CleanTarget("node_modules of web", Category.DEV, Path("/w"), 50 * MB, RiskTier.TIER2_REVIEW,
                    metadata={"last_active": time.time() - 30 * 86400}),
    ]
    choices = cli.build_target_choices(targets)
    headers = [c.line for c in choices if isinstance(c, questionary.Separator)]
    assert [h.split("(")[0].strip("─ \n") for h in headers] == ["Android & Gradle", "Browser Caches", "Developer Tools"]

    items = [c for c in choices if not isinstance(c, questionary.Separator)]
    assert [c.value.name for c in items][:2] == ["x86 image", "Old NDK"]  # SAFE first inside a group
    assert [c.checked for c in items] == [True, False, False, False]
    assert "dùng lần cuối" in items[-1].title


# --- 6. low-disk alert ------------------------------------------------------------

def fake_disk(monkeypatch, free_pct):
    total = 1000 * 1024 * MB
    monkeypatch.setattr(cli, "get_disk_space", lambda: (total, total * (100 - free_pct) // 100, total * free_pct // 100))


def test_no_alert_above_threshold(monkeypatch):
    fake_disk(monkeypatch, 40)
    sent = []
    monkeypatch.setattr(cli, "notify_macos", lambda *a: sent.append(a))
    result = runner.invoke(cli.app, ["check-space", "--notify"])
    assert result.exit_code == 0 and sent == []


def test_alert_below_threshold_once_per_day(monkeypatch):
    fake_disk(monkeypatch, 5)
    monkeypatch.setattr(cli, "run_all_scanners", lambda: [
        CleanTarget("a", Category.SYSTEM, Path("/a"), 2048 * MB, RiskTier.TIER1_SAFE),
        CleanTarget("b", Category.BROWSER, Path("/b"), 1024 * MB, RiskTier.TIER2_REVIEW),
    ])
    sent = []
    monkeypatch.setattr(cli, "notify_macos", lambda title, msg: sent.append(msg))

    runner.invoke(cli.app, ["check-space", "--notify"])
    runner.invoke(cli.app, ["check-space", "--notify"])
    assert len(sent) == 1
    assert "2.00 GB an toàn" in sent[0] and "1.00 GB cần bạn chọn" in sent[0]
    assert load_state()["last_disk_alert"] > 0

    runner.invoke(cli.app, ["check-space", "--notify", "--force"])
    assert len(sent) == 2


def test_alert_plist_only_checks_space():
    plist = plistlib.loads(generate_alert_plist_content(Path("/opt/mclean"), interval_hours=3).encode())
    assert plist["Label"] == "com.mclean.diskalert"
    assert plist["ProgramArguments"] == ["/opt/mclean", "check-space", "--notify"]
    assert plist["StartInterval"] == 3 * 3600


# --- 2. doctor ----------------------------------------------------------------------

def test_jsonc_settings_with_comments_and_trailing_commas(tmp_path):
    path = write(tmp_path / "settings.json", b'{\n  // comment\n  "url": "https://x.dev/a",  /* block */\n  "n": [1, 2,],\n}\n')
    assert doctor.load_jsonc(path) == {"url": "https://x.dev/a", "n": [1, 2]}


def test_doctor_flags_ide_that_imports_pub_cache_plugins(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".antigravity-ide" / "extensions" / "redhat.java-1.58.0").mkdir(parents=True)
    settings = tmp_path / "Library" / "Application Support" / "Antigravity IDE" / "User" / "settings.json"
    write(settings, b'{"editor.fontSize": 14}')
    write(tmp_path / ".gradle" / "daemon" / "8.4" / "daemon-1.out.log",
          b"Settings file '/Users/x/.pub-cache/hosted/pub.dev/firebase_core-4.15.0/android/settings.gradle'\n")
    monkeypatch.setattr(doctor, "referenced_gradle_dists", lambda: set())

    checks = {c.title: c for c in doctor.check_ide_gradle_import()}
    assert checks["Gradle bị tải lại ngầm"].status == doctor.FAIL
    assert "firebase_core-4.15.0" in checks["Gradle bị tải lại ngầm"].detail
    ide = checks["Import Gradle của Antigravity IDE"]
    assert ide.status == doctor.FAIL and "**/.symlinks/**" in ide.fix

    # After applying the suggested exclusions the IDE check passes
    write(settings, json.dumps({"java.import.exclusions": ["**/.symlinks/**", "**/.pub-cache/**"]}).encode())
    checks = {c.title: c for c in doctor.check_ide_gradle_import()}
    assert checks["Import Gradle của Antigravity IDE"].status == doctor.OK


def test_doctor_reports_background_job_without_folder_access(monkeypatch):
    from mclean.utils.state import update_state
    update_state(last_auto_clean={"time": "2026-10-27T09:00:00", "reclaimed_bytes": 0, "failed": 0, "blocked": 0,
                                  "readable": {str(Path.home() / "Desktop"): False}, "executable": "/usr/bin/python3"})
    checks = {c.title: c for c in doctor.check_last_auto_clean()}
    access = checks["Quyền truy cập của job chạy nền"]
    assert access.status == doctor.WARN and "/usr/bin/python3" in access.fix


def test_doctor_runs_every_check_without_crashing():
    assert doctor.run_checks()

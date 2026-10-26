import json
import os
import plistlib
import time
from pathlib import Path

from mclean.cli import CATEGORY_KEYS
from mclean.models import Category, RiskTier
from mclean.scanners import android_java
from mclean.scanners.ai_python import AiPythonScanner
from mclean.scanners.android_java import AndroidJavaScanner
from mclean.scanners.installer import scan_installers
from mclean.utils.projects import referenced_gradle_dists, referenced_ndk_versions
from mclean.utils.scheduler import generate_plist_content

from conftest import MB, write

OLD = time.time() - 60 * 86400


def sized_file(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)
    return path


def test_installer_tiers(tmp_path):
    for name in ["fresh.dmg", "old.dmg", "backup.zip"]:
        sized_file(tmp_path / name, 60 * MB)
    os.utime(tmp_path / "old.dmg", (OLD, OLD))
    os.utime(tmp_path / "backup.zip", (OLD, OLD))
    tiers = {t.path.name: t.risk_tier for t in scan_installers(tmp_path, 7)}
    assert tiers == {
        "old.dmg": RiskTier.TIER1_SAFE,
        "fresh.dmg": RiskTier.TIER2_REVIEW,
        "backup.zip": RiskTier.TIER2_REVIEW,  # may be a backup, never pre-selected
    }


def test_ollama_model_tags_keep_namespace(tmp_path):
    for parts in [
        ("registry.ollama.ai", "library", "llama3", "latest"),
        ("registry.ollama.ai", "bob", "coder", "7b"),
        ("hf.co", "org", "model-GGUF", "Q4_K_M"),
    ]:
        write(tmp_path.joinpath(*parts), json.dumps({"layers": [{"size": 5}, {"size": 7}]}).encode())
    targets = AiPythonScanner()._scan_ollama_models(tmp_path)
    assert sorted(t.metadata["model_tag"] for t in targets) == ["bob/coder:7b", "hf.co/org/model-GGUF:Q4_K_M", "llama3:latest"]
    assert all(t.size_bytes == 12 for t in targets)


def test_referenced_gradle_dists_read_from_wrapper_properties(tmp_path):
    props = tmp_path / "app" / "android" / "gradle" / "wrapper" / "gradle-wrapper.properties"
    write(props, b"distributionUrl=https\\://services.gradle.org/distributions/gradle-8.4-bin.zip\n")
    assert referenced_gradle_dists([tmp_path]) == {"gradle-8.4-bin"}


def test_gradle_wrappers_kept_when_referenced_running_recent_or_newest(tmp_path, monkeypatch):
    dists = tmp_path / "dists"
    for name in ["gradle-7.0-bin", "gradle-8.0-bin", "gradle-8.4-bin", "gradle-8.9-bin", "gradle-9.0-bin", "gradle-9.1-bin"]:
        (dists / name / "hash").mkdir(parents=True)
    monkeypatch.setattr(android_java, "referenced_gradle_dists", lambda: {"gradle-8.4-bin"})
    monkeypatch.setattr(android_java, "running_gradle_dists", lambda: {"gradle-8.0-bin"})
    monkeypatch.setattr(android_java, "_gradle_idle_days", lambda v, d=None: 1 if v == "8.9" else 90)
    monkeypatch.setattr(android_java, "get_batch_sizes", lambda paths: {p: 100 * MB for p in paths})

    offered = [t.path.name for t in AndroidJavaScanner()._scan_old_gradle_wrappers(dists)]
    # 8.0 running, 8.4 referenced, 8.9 used yesterday, 9.0/9.1 newest two
    assert offered == ["gradle-7.0-bin"]


def test_gradle_idle_days_follows_daemon_activity(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    registry = write(tmp_path / ".gradle" / "daemon" / "8.4" / "registry.bin")
    for p in [registry, registry.parent]:
        os.utime(p, (OLD, OLD))
    assert android_java._gradle_idle_days("8.4") >= 59
    registry.write_bytes(b"daemon started now")
    assert android_java._gradle_idle_days("8.4") == 0


def test_system_images_used_by_an_avd_are_kept(tmp_path, monkeypatch):
    sdk, avd_root = tmp_path / "sdk", tmp_path / "avd"
    for rel in ["android-34/google_apis/arm64-v8a", "android-36/google_apis/arm64-v8a", "android-36/google_apis/x86_64"]:
        (sdk / "system-images" / rel).mkdir(parents=True)
    write(avd_root / "Pixel.avd" / "config.ini", b"image.sysdir.1=system-images/android-36/google_apis/arm64-v8a/\n")
    monkeypatch.setattr(android_java, "get_path_size", lambda p: 3000 * MB)
    monkeypatch.setattr(android_java.platform, "machine", lambda: "arm64")

    found = {t.path.relative_to(sdk / "system-images").as_posix(): t.risk_tier for t in
             AndroidJavaScanner()._scan_unused_system_images(sdk, avd_root)}
    assert found == {
        "android-34/google_apis/arm64-v8a": RiskTier.TIER2_REVIEW,
        "android-36/google_apis/x86_64": RiskTier.TIER1_SAFE,  # cannot boot on Apple Silicon
    }


def test_ndk_versions_referenced_by_projects(tmp_path):
    write(tmp_path / "app" / "android" / "app" / "build.gradle.kts", b'android {\n    ndkVersion = "25.1.8937393"\n}\n')
    write(tmp_path / "legacy" / "android" / "app" / "build.gradle", b"android { ndkVersion '23.1.7779620' }\n")
    found = referenced_ndk_versions([tmp_path])
    assert {"25.1.8937393", "23.1.7779620"} <= found


def test_unused_ndk_offered_newest_always_kept(tmp_path, monkeypatch):
    for v in ["21.4.7075529", "23.1.7779620", "28.2.13676358"]:
        (tmp_path / "ndk" / v).mkdir(parents=True)
    monkeypatch.setattr(android_java, "referenced_ndk_versions", lambda: {"23.1.7779620"})
    monkeypatch.setattr(android_java, "get_path_size", lambda p: 3000 * MB)
    offered = [t.path.name for t in AndroidJavaScanner()._scan_unused_ndks(tmp_path)]
    assert offered == ["21.4.7075529"]


def test_category_filter_uses_exact_keys():
    assert CATEGORY_KEYS["ai"] == Category.AI
    assert set(CATEGORY_KEYS) == {"xcode", "android", "flutter", "ai", "dev", "system", "trash", "browser"}


def test_schedule_plist_is_valid_xml_with_awkward_paths():
    xml = generate_plist_content(Path("/Users/a b/&tools/mclean"), weekday=1, hour=9, minute=0)
    plist = plistlib.loads(xml.encode())
    assert plist["ProgramArguments"] == ["/Users/a b/&tools/mclean", "clean", "--force", "--notify"]
    assert plist["StartCalendarInterval"] == {"Weekday": 1, "Hour": 9, "Minute": 0}
    assert "/opt/homebrew/bin" in plist["EnvironmentVariables"]["PATH"]

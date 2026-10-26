from pathlib import Path

from mclean.config import is_path_protected, save_ignored_paths

HOME = Path.home()
AVD = HOME / ".android" / "avd" / "Pixel.avd"


def test_avd_snapshots_and_cache_are_deletable():
    assert not is_path_protected(AVD / "snapshots")
    assert not is_path_protected(AVD / "cache.img.qcow2")


def test_avd_user_data_is_protected():
    for name in ["userdata-qemu.img", "userdata-qemu.img.qcow2", "sdcard.img", "encryptionkey.img", "config.ini"]:
        assert is_path_protected(AVD / name), name


def test_ancestors_of_protected_paths_are_protected():
    assert is_path_protected(HOME / ".gradle" / "caches")  # contains modules-2
    assert is_path_protected(HOME / ".pub-cache")          # contains hosted/
    assert is_path_protected(HOME)
    assert is_path_protected(HOME / "Desktop")


def test_regular_caches_are_not_protected():
    assert not is_path_protected(HOME / "Library" / "Caches" / "com.apple.dt.Xcode")
    assert not is_path_protected(HOME / ".gradle" / "caches" / "8.7")


def test_user_ignore_list_protects_path_and_its_parents(tmp_path):
    project = tmp_path / "work" / "secret_app"
    save_ignored_paths({project})
    assert is_path_protected(project / "build")
    assert is_path_protected(tmp_path / "work")
    assert not is_path_protected(tmp_path / "other")

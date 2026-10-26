"""Keep every test away from the user's real mclean config and history."""

from pathlib import Path

import pytest

from mclean import config
from mclean.utils import history

MB = 1024 * 1024


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(config, "IGNORE_FILE", tmp_path / "config" / "ignore.json")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config" / "config.json")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "config")  # state.json lives here
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "config" / "history.json")
    return tmp_path / "config"


@pytest.fixture
def no_running_apps(monkeypatch):
    monkeypatch.setattr("mclean.cleaner.get_active_dev_processes", lambda: [])


def write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path

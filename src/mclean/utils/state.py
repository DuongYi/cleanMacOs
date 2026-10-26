"""Small persistent state for background jobs (last alert, last auto-clean result)."""

import json
from typing import Any, Dict

from mclean import config


def _state_file():
    # Resolved on each call so tests can point CONFIG_DIR elsewhere
    return config.CONFIG_DIR / "state.json"


def load_state() -> Dict[str, Any]:
    try:
        with open(_state_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def update_state(**values: Any) -> None:
    state = load_state()
    state.update(values)
    try:
        config.ensure_config_dir()
        with open(_state_file(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except OSError:
        pass

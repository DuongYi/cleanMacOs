"""Cleanup history and lifetime savings tracker for mclean."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from mclean.config import CONFIG_DIR, ensure_config_dir

HISTORY_FILE = CONFIG_DIR / "history.json"


def load_history() -> List[Dict[str, Any]]:
    """Load cleanup history list from disk."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("records", [])
    except Exception:
        return []


def record_cleanup(reclaimed_bytes: int, item_names: List[str]) -> None:
    """Record a cleanup session into history."""
    if reclaimed_bytes <= 0:
        return

    ensure_config_dir()
    records = load_history()
    records.append({
        "timestamp": datetime.now().isoformat(),
        "reclaimed_bytes": reclaimed_bytes,
        "items_count": len(item_names),
        "items": item_names[:10],  # Save up to 10 top items
    })

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"records": records}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_total_lifetime_savings() -> int:
    """Calculate total bytes reclaimed across all recorded sessions."""
    records = load_history()
    return sum(r.get("reclaimed_bytes", 0) for r in records)


def clear_history() -> bool:
    """Clear history file."""
    if HISTORY_FILE.exists():
        try:
            HISTORY_FILE.unlink()
            return True
        except OSError:
            return False
    return True

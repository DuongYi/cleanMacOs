"""Data models and risk definitions for mclean."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class RiskTier(str, Enum):
    """Safety classification for disk cleaning."""
    TIER1_SAFE = "SAFE"        # 100% safe, disposable logs/caches, zero re-download penalty
    TIER2_REVIEW = "REVIEW"    # Re-creatable or heavy item (models, dormant AVDs, old builds)
    TIER3_PROTECTED = "LOCKED" # Core dependencies (pub.dev packages, active AVD userdata)


class Category(str, Enum):
    """High-level category for clean targets."""
    XCODE = "Xcode & Apple"
    ANDROID = "Android & Gradle"
    FLUTTER = "Flutter & Dart"
    AI = "AI & Machine Learning"
    DEV = "Developer Tools"
    SYSTEM = "macOS System Junk"
    TRASH = "Trash & Volumes"


@dataclass
class CleanTarget:
    """Represents a cleanable file, directory, or cleanup command."""
    name: str
    category: Category
    path: Path
    size_bytes: int
    risk_tier: RiskTier = RiskTier.TIER1_SAFE
    description: str = ""
    item_type: str = "directory"  # "directory", "file", or "command"
    clean_command: Optional[list[str]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        return self.risk_tier == RiskTier.TIER1_SAFE

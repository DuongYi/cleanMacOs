"""Abstract base class for all mclean scanners."""

from abc import ABC, abstractmethod
from typing import List, Tuple

from mclean.models import Category, CleanTarget
from mclean.utils.disk import safe_delete_path
import subprocess


class BaseScanner(ABC):
    """Abstract scanner defining discovery and cleanup interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scanner."""
        pass

    @property
    @abstractmethod
    def category(self) -> Category:
        """Category this scanner belongs to."""
        pass

    @abstractmethod
    def scan(self) -> List[CleanTarget]:
        """Perform discovery and return clean targets."""
        pass

    def clean(self, target: CleanTarget, dry_run: bool = False) -> Tuple[bool, str]:
        """Execute cleanup for a specific target."""
        if target.item_type == "command" and target.clean_command:
            if dry_run:
                return True, f"[Dry-run] Would execute: {' '.join(target.clean_command)}"
            try:
                res = subprocess.run(target.clean_command, capture_output=True, text=True, timeout=60)
                if res.returncode == 0:
                    return True, f"Command succeeded: {' '.join(target.clean_command)}"
                else:
                    return False, f"Command failed: {res.stderr.strip() or res.stdout.strip()}"
            except Exception as e:
                return False, f"Error executing command: {e}"

        # Standard file or directory removal
        return safe_delete_path(target.path, dry_run=dry_run)

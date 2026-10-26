"""Web browser disk caches (Chrome, Cốc Cốc, Brave, Edge, Firefox)."""

from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes

# (browser, cache folder under ~/Library/Caches, guard name in utils.guard.DEV_PROCESS_RULES)
BROWSER_CACHES = [
    ("Google Chrome", "Google/Chrome", "Google Chrome"),
    ("Cốc Cốc", "CocCoc/Browser", "Cốc Cốc"),
    ("Brave", "BraveSoftware/Brave-Browser", "Brave"),
    ("Microsoft Edge", "Microsoft Edge", "Microsoft Edge"),
    ("Firefox", "Firefox", "Firefox"),
]


class BrowserScanner(BaseScanner):
    """Scans browser caches. Profiles, history, passwords and logins live elsewhere and are never touched."""

    @property
    def name(self) -> str:
        return "Browser Caches"

    @property
    def category(self) -> Category:
        return Category.BROWSER

    def scan(self) -> List[CleanTarget]:
        caches_root = Path.home() / "Library" / "Caches"
        candidates = [(browser, caches_root / rel, guard) for browser, rel, guard in BROWSER_CACHES]
        sizes = get_batch_sizes([path for _, path, _ in candidates])

        targets: List[CleanTarget] = []
        for browser, path, guard in candidates:
            size = sizes.get(path, 0)
            if size > 100 * 1024 * 1024:
                targets.append(CleanTarget(
                    name=f"Cache {browser}",
                    category=self.category,
                    path=path,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER2_REVIEW,
                    description="Trang, ảnh và script đã cache của mọi profile. Đăng nhập và lịch sử được giữ; web tải chậm hơn một chút cho tới khi cache đầy lại.",
                    metadata={"guard": [guard]},
                ))
        return targets

"""Docker, OrbStack, and Container storage scanner and cleaner."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_path_size


class DockerScanner(BaseScanner):
    """Scans Docker / OrbStack caches, dangling images, stopped containers, and buildx cache."""

    @property
    def name(self) -> str:
        return "Docker & Containers"

    @property
    def category(self) -> Category:
        return Category.DEV

    def is_docker_running(self) -> bool:
        """Check if docker CLI is installed and daemon is responsive."""
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=3)
            return res.returncode == 0
        except Exception:
            return False

    def scan(self) -> List[CleanTarget]:
        targets: List[CleanTarget] = []
        home = Path.home()

        # 1. Check local Docker logs and temporary files on disk
        docker_data = home / "Library" / "Containers" / "com.docker.docker" / "Data"
        if docker_data.exists():
            for sub in ["log", "tmp", "cache"]:
                p = docker_data / sub
                if p.exists():
                    sz = get_path_size(p)
                    if sz > 10 * 1024 * 1024:
                        targets.append(CleanTarget(
                            name=f"Docker Desktop {sub.capitalize()} Files",
                            category=self.category,
                            path=p,
                            size_bytes=sz,
                            risk_tier=RiskTier.TIER1_SAFE,
                            description=f"Temporary {sub} files from Docker Desktop VM.",
                        ))

        # 2. If Docker engine is running, inspect live Docker objects
        if self.is_docker_running():
            targets.extend(self._scan_docker_engine())

        return targets

    def _scan_docker_engine(self) -> List[CleanTarget]:
        results: List[CleanTarget] = []
        try:
            # Parse `docker system df --format json`
            res = subprocess.run(["docker", "system", "df", "--format", "{{json .}}"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                        obj_type = data.get("Type", "")
                        reclaimable_str = data.get("Reclaimable", "0B")

                        # If reclaimable space exists
                        if "Build Cache" in obj_type:
                            results.append(CleanTarget(
                                name="Docker BuildKit Cache",
                                category=self.category,
                                path=Path.home() / ".docker" / "buildx",
                                size_bytes=0,
                                risk_tier=RiskTier.TIER1_SAFE,
                                description=f"Unused Docker build cache (Reclaimable: {reclaimable_str})",
                                item_type="command",
                                clean_command=["docker", "builder", "prune", "-f"],
                            ))
                        elif "Images" in obj_type:
                            results.append(CleanTarget(
                                name="Docker Dangling Images",
                                category=self.category,
                                path=Path.home() / ".docker",
                                size_bytes=0,
                                risk_tier=RiskTier.TIER1_SAFE,
                                description=f"Untagged dangling container images (Reclaimable: {reclaimable_str})",
                                item_type="command",
                                clean_command=["docker", "image", "prune", "-f"],
                            ))
                        elif "Containers" in obj_type:
                            results.append(CleanTarget(
                                name="Docker Stopped Containers",
                                category=self.category,
                                path=Path.home() / ".docker",
                                size_bytes=0,
                                risk_tier=RiskTier.TIER1_SAFE,
                                description=f"Exited/stopped containers (Reclaimable: {reclaimable_str})",
                                item_type="command",
                                clean_command=["docker", "container", "prune", "-f"],
                            ))
                    except Exception:
                        continue
        except Exception:
            pass

        return results


def run_docker_prune(all_unused: bool = False) -> Tuple[bool, str]:
    """Execute docker prune commands."""
    if not shutil.which("docker"):
        return False, "Docker CLI không được cài đặt trên máy."

    try:
        check = subprocess.run(["docker", "info"], capture_output=True, timeout=4)
        if check.returncode != 0:
            return False, "Docker daemon đang tắt. Hãy mở Docker Desktop lên trước."

        cmd = ["docker", "system", "prune", "-f"]
        if all_unused:
            cmd.append("--all")

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            return True, res.stdout.strip()
        else:
            return False, res.stderr.strip()
    except Exception as e:
        return False, f"Lỗi chạy docker prune: {e}"

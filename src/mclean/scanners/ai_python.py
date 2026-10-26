"""AI & Machine Learning Models and Python Caches Scanner."""

import os
from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import get_batch_sizes, get_path_size
from mclean.utils.formatters import format_timestamp


class AiPythonScanner(BaseScanner):
    """Scans HuggingFace, Ollama, PyTorch, Pip, uv, and AI editor caches."""

    @property
    def name(self) -> str:
        return "AI & Machine Learning"

    @property
    def category(self) -> Category:
        return Category.AI

    def scan(self) -> List[CleanTarget]:
        home = Path.home()
        targets: List[CleanTarget] = []

        # 1. Pure Caches and Logs (TIER 1 - 100% Safe)
        safe_caches = [
            ("Pip Wheel Cache", home / ".cache" / "pip", "Downloaded Python wheel archives. Virtualenvs remain unaffected."),
            ("Pip Library Cache", home / "Library" / "Caches" / "pip", "Legacy pip wheel archive cache."),
            ("PyTorch Kernels Cache", home / ".cache" / "torch" / "kernels", "Compiled JIT PyTorch CUDA/Metal shader kernels."),
            ("uv Package Cache", home / ".cache" / "uv", "uv build artifacts and downloaded archives."),
            ("Cursor IDE Cache", home / "Library" / "Application Support" / "Cursor" / "Cache", "Editor cache and indexing."),
            ("Cursor CachedData", home / "Library" / "Application Support" / "Cursor" / "CachedData", "V8 compiled bytecode cache."),
            ("VS Code Cache", home / "Library" / "Application Support" / "Code" / "Cache", "VS Code IDE cache."),
            ("Ollama Logs", home / ".ollama" / "logs", "Ollama daemon execution and runtime logs."),
            ("LM Studio Server Logs", home / ".lmstudio" / "server-logs", "LM Studio local API server logs."),
        ]

        sizes = get_batch_sizes([p for _, p, _ in safe_caches])
        for name, path, desc in safe_caches:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name=name,
                    category=self.category,
                    path=path,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER1_SAFE,
                    description=desc,
                ))

        # 2. Hugging Face Hub Individual Models (TIER 2 - Review)
        # We parse individual models so user never accidentally wipes models they are actively using!
        hf_hub = home / ".cache" / "huggingface" / "hub"
        if hf_hub.exists():
            targets.extend(self._scan_huggingface_models(hf_hub))

        # 3. Ollama Individual Models (TIER 2 - Review)
        ollama_manifests = home / ".ollama" / "models" / "manifests"
        if ollama_manifests.exists():
            targets.extend(self._scan_ollama_models(ollama_manifests))

        return targets

    def _scan_huggingface_models(self, hf_hub: Path) -> List[CleanTarget]:
        """Scan and format individual HuggingFace model directories."""
        results: List[CleanTarget] = []

        for item in hf_hub.iterdir():
            if item.is_dir() and item.name.startswith("models--"):
                # Format: models--organization--model_name -> organization/model_name
                parts = item.name.split("--")
                if len(parts) >= 3:
                    model_name = f"{parts[1]}/{'/'.join(parts[2:])}"
                else:
                    model_name = item.name

                size = get_path_size(item)
                try:
                    atime = item.stat().st_atime
                except OSError:
                    atime = 0.0

                if size > 10 * 1024 * 1024:
                    results.append(CleanTarget(
                        name=f"HF Model: {model_name}",
                        category=self.category,
                        path=item,
                        size_bytes=size,
                        risk_tier=RiskTier.TIER2_REVIEW,
                        description=f"Hugging Face weights. Last accessed {format_timestamp(atime)}.",
                        metadata={"model_name": model_name, "last_accessed": atime},
                    ))

        return results

    def _scan_ollama_models(self, manifests_dir: Path) -> List[CleanTarget]:
        """Scan Ollama models manifests."""
        results: List[CleanTarget] = []
        try:
            for manifest_file in manifests_dir.rglob("*"):
                if manifest_file.is_file():
                    # Rel path gives model:tag e.g. registry.ollama.ai/library/llama3/latest
                    parts = manifest_file.relative_to(manifests_dir).parts
                    if len(parts) >= 2:
                        model_tag = f"{parts[-2]}:{parts[-1]}"
                    else:
                        model_tag = manifest_file.name

                    results.append(CleanTarget(
                        name=f"Ollama Model: {model_tag}",
                        category=self.category,
                        path=manifest_file,
                        size_bytes=0,
                        risk_tier=RiskTier.TIER2_REVIEW,
                        description=f"Ollama local model. Remove using 'ollama rm {model_tag}'",
                        item_type="command",
                        clean_command=["ollama", "rm", model_tag],
                        metadata={"model_tag": model_tag},
                    ))
        except Exception:
            pass

        return results

"""AI & Machine Learning Models and Python Caches Scanner."""

import json
from pathlib import Path
from typing import List

from mclean.models import Category, CleanTarget, RiskTier
from mclean.scanners.base import BaseScanner
from mclean.utils.disk import find_tool, get_batch_sizes, get_path_size
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

        # 1. Caches rebuilt locally and logs (TIER 1), plus download caches (TIER 2)
        # (name, path, description, tier, apps that must be closed)
        caches = [
            ("Cache kernel PyTorch", home / ".cache" / "torch" / "kernels", "Kernel CUDA/Metal do PyTorch biên dịch, tự biên dịch lại tại máy.", RiskTier.TIER1_SAFE, []),
            ("Cache Cursor", home / "Library" / "Application Support" / "Cursor" / "Cache", "Cache web của trình soạn thảo, tự tạo lại tại máy.", RiskTier.TIER1_SAFE, ["Cursor"]),
            ("Cursor CachedData", home / "Library" / "Application Support" / "Cursor" / "CachedData", "Bytecode V8 đã biên dịch, tự tạo lại tại máy.", RiskTier.TIER1_SAFE, ["Cursor"]),
            ("Cache VS Code", home / "Library" / "Application Support" / "Code" / "Cache", "Cache web của VS Code, tự tạo lại tại máy.", RiskTier.TIER1_SAFE, ["VS Code"]),
            ("VS Code CachedData", home / "Library" / "Application Support" / "Code" / "CachedData", "Bytecode V8 đã biên dịch, tự tạo lại tại máy.", RiskTier.TIER1_SAFE, ["VS Code"]),
            ("Log Ollama", home / ".ollama" / "logs", "Log chạy của Ollama.", RiskTier.TIER1_SAFE, ["Ollama"]),
            ("Log server LM Studio", home / ".lmstudio" / "server-logs", "Log của server API cục bộ LM Studio.", RiskTier.TIER1_SAFE, ["LM Studio"]),
            ("Cache pip", home / ".cache" / "pip", "Wheel đã tải. Virtualenv không bị ảnh hưởng, nhưng lần cài sau phải tải lại các gói này.", RiskTier.TIER2_REVIEW, []),
            ("Cache pip (Library)", home / "Library" / "Caches" / "pip", "Wheel đã tải. Lần cài sau phải tải lại các gói này.", RiskTier.TIER2_REVIEW, []),
            ("Cache uv (toàn bộ)", home / ".cache" / "uv", "Mọi thứ uv đã tải. Lần uv sync sau phải tải lại; nên dùng mục 'uv cache prune'.", RiskTier.TIER2_REVIEW, []),
        ]

        sizes = get_batch_sizes([c[1] for c in caches])
        for name, path, desc, tier, guard in caches:
            size = sizes.get(path, 0)
            if size > 10 * 1024 * 1024:
                targets.append(CleanTarget(
                    name=name,
                    category=self.category,
                    path=path,
                    size_bytes=size,
                    risk_tier=tier,
                    description=desc,
                    metadata={"guard": guard},
                ))

        # uv's own prune removes only entries no environment uses
        uv = find_tool("uv")
        if uv and (home / ".cache" / "uv").exists():
            targets.append(CleanTarget(
                name="uv: dọn cache không dùng",
                category=self.category,
                path=home / ".cache" / "uv",
                size_bytes=0,
                risk_tier=RiskTier.TIER1_SAFE,
                description="Chạy 'uv cache prune': chỉ xoá phần cache không dự án nào dùng.",
                item_type="command",
                clean_command=[uv, "cache", "prune"],
                metadata={"guard": []},
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
                        name=f"Model Hugging Face: {model_name}",
                        category=self.category,
                        path=item,
                        size_bytes=size,
                        risk_tier=RiskTier.TIER2_REVIEW,
                        description=f"Trọng số Hugging Face, phải tải lại khi dùng lần sau. Truy cập lần cuối {format_timestamp(atime)}.",
                        metadata={"model_name": model_name, "last_accessed": atime},
                    ))

        return results

    def _scan_ollama_models(self, manifests_dir: Path) -> List[CleanTarget]:
        """Scan Ollama model manifests (manifests/<registry>/<namespace>/<model>/<tag>)."""
        results: List[CleanTarget] = []
        try:
            for manifest_file in manifests_dir.rglob("*"):
                if not manifest_file.is_file():
                    continue
                parts = manifest_file.relative_to(manifests_dir).parts
                if len(parts) != 4:
                    continue
                registry, namespace, model, tag = parts
                if registry == "registry.ollama.ai":
                    model_name = model if namespace == "library" else f"{namespace}/{model}"
                else:
                    model_name = f"{registry}/{namespace}/{model}"
                model_tag = f"{model_name}:{tag}"

                # Layers are shared between tags, so this is the model's size, not necessarily what rm frees
                size = 0
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    size = sum(layer.get("size", 0) for layer in manifest.get("layers", []))
                except (OSError, ValueError):
                    pass

                results.append(CleanTarget(
                    name=f"Model Ollama: {model_tag}",
                    category=self.category,
                    path=manifest_file,
                    size_bytes=size,
                    risk_tier=RiskTier.TIER2_REVIEW,
                    description=f"Model Ollama cục bộ, phải tải lại nếu muốn dùng. Xoá bằng 'ollama rm {model_tag}'.",
                    item_type="command",
                    clean_command=[find_tool("ollama") or "ollama", "rm", model_tag],
                    metadata={"model_tag": model_tag},
                ))
        except Exception:
            pass

        return results

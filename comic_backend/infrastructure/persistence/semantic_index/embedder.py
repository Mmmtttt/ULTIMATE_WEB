from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.storage_layout import get_cache_root_dir

DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
# bge 中文系列的检索式前缀：查询侧加，文档侧不加
QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
MODEL_CACHE_SUBDIR = "semantic_model"

_ENV_MODE = "ULTIMATE_SEMANTIC_EMBEDDING"
_ENV_MODEL = "ULTIMATE_SEMANTIC_MODEL"

_lock = threading.Lock()
_provider: Optional["EmbeddingProvider"] = None


class EmbeddingProvider:
    """可选的本地向量编码器。

    依赖 fastembed + onnxruntime（仅桌面端可用；安卓端不会安装，也不会加载）。
    缺失时 `available` 为 False，语义检索自动退化为「标签 + 关键词」两路。
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: Any = None
        self._dim: int = 0
        self._reason: str = ""
        self._load_attempted = False

    # ---------- 能力探测 ----------
    @property
    def loaded(self) -> bool:
        """模型是否已经在内存里（不触发加载，供状态接口低成本探测）。"""
        return self._model is not None

    @staticmethod
    def installed() -> bool:
        """依赖是否安装（不 import、不加载模型；import onnxruntime 本身要好几秒）。"""
        try:
            import importlib.util

            return importlib.util.find_spec("fastembed") is not None
        except Exception:
            return False

    @property
    def failed_reason(self) -> str:
        return self._reason or ""

    @property
    def available(self) -> bool:
        return self._load() is not None

    @property
    def reason(self) -> str:
        if self.available:
            return ""
        return self._reason

    @property
    def dim(self) -> int:
        if self._dim:
            return self._dim
        meta = self.model_meta()
        return int(meta.get("dim") or 0)

    @staticmethod
    def model_meta() -> Dict[str, Any]:
        try:
            from fastembed import TextEmbedding  # noqa: F401

            package = "fastembed"
        except Exception:
            return {"installed": False, "dim": 0}
        return {"installed": True, "package": package, "dim": 0}

    def cache_dir(self) -> str:
        root = ""
        try:
            root = get_cache_root_dir()
        except Exception:
            root = ""
        if not root:
            root = os.path.join(os.path.expanduser("~"), ".cache", "ultimate-web")
        target = os.path.join(root, MODEL_CACHE_SUBDIR)
        try:
            os.makedirs(target, exist_ok=True)
        except Exception:
            pass
        return target

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_attempted:
            return None
        with _lock:
            if self._model is not None:
                return self._model
            if self._load_attempted:
                return None
            self._load_attempted = True

            mode = str(os.environ.get(_ENV_MODE, "auto")).strip().lower()
            if mode in {"0", "off", "false", "disabled", "disable"}:
                self._reason = "向量检索已通过环境变量禁用"
                return None

            try:
                from fastembed import TextEmbedding
            except Exception as exc:
                # 常见原因是没装 fastembed；也可能是 onnxruntime 在该平台不可用
                self._reason = f"无法加载 fastembed: {exc}"
                return None

            cache_dir = self.cache_dir()
            os.environ.setdefault("FASTEMBED_CACHE_PATH", cache_dir)
            try:
                self._model = TextEmbedding(model_name=self.model_name, cache_dir=cache_dir)
            except TypeError:
                try:
                    self._model = TextEmbedding(self.model_name)
                except Exception as exc:  # pragma: no cover - 依赖缺失/离线
                    self._reason = f"加载向量模型失败: {exc}"
                    return None
            except Exception as exc:  # pragma: no cover - 依赖缺失/离线
                self._reason = f"加载向量模型失败: {exc}"
                return None
            return self._model

    # ---------- 编码 ----------
    @staticmethod
    def _pack(values: Sequence[float]) -> bytes:
        import struct

        return struct.pack(f"<{len(values)}f", *[float(v) for v in values])

    @staticmethod
    def _norm(values: Sequence[float]) -> float:
        return sum(float(v) * float(v) for v in values) ** 0.5

    def embed_documents(self, texts: Sequence[str], batch_size: int = 64) -> List[Tuple[bytes, float]]:
        """把文档批量编码成 (float32 blob, 向量模长)；不可用时返回空列表。"""
        model = self._load()
        cleaned = [str(text or "") for text in texts]
        if model is None or not cleaned:
            return []
        vectors = list(model.embed(cleaned, batch_size=batch_size))
        if vectors and not self._dim:
            self._dim = len(vectors[0])
        packed: List[Tuple[bytes, float]] = []
        for vector in vectors:
            values = [float(v) for v in vector]
            packed.append((self._pack(values), self._norm(values) or 1.0))
        return packed

    def embed_query(self, text: str) -> Optional[List[float]]:
        model = self._load()
        if model is None:
            return None
        payload = f"{QUERY_PREFIX}{text}"
        try:
            vectors = list(model.embed([payload]))
        except Exception:
            return None
        if not vectors:
            return None
        values = [float(v) for v in vectors[0]]
        if not self._dim:
            self._dim = len(values)
        return values


def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is None:
        with _lock:
            if _provider is None:
                _provider = EmbeddingProvider(os.environ.get(_ENV_MODEL, DEFAULT_MODEL_NAME))
    return _provider

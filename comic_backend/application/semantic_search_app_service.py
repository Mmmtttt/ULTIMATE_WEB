from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.runtime_profile import is_mobile_core_profile
from core.storage_layout import get_current_space_mode, set_current_space_mode
from domain.config import ConfigRepository
from domain.config.entity import SEARCH_ENGINE_SEMANTIC
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories import ConfigJsonRepository
from infrastructure.persistence.semantic_index import (
    EmbeddingProvider,
    get_embedding_provider,
    index_status,
    rebuild_index,
    search as semantic_search,
    semantic_index_connection,
)

AUTO_REBUILD_COOLDOWN_SECONDS = 30


class SemanticSearchAppService:
    """语义检索（可选检索引擎）。

    - 平台：仅桌面端可用；Android（mobile_core）不提供，直接返回不可用。
    - 开关：user_config.search_engine == "semantic" 时生效，默认仍走 catalog index。
    - 降级：索引缺失/过期/构建失败时一律返回 None，调用方回落到原有关键词匹配。
    """

    def __init__(
        self,
        config_repo: Optional[ConfigRepository] = None,
        embedder: Optional[EmbeddingProvider] = None,
    ) -> None:
        self._config_repo = config_repo or ConfigJsonRepository()
        self._embedder = embedder or get_embedding_provider()
        self._rebuild_lock = threading.Lock()
        self._last_auto_rebuild = 0.0
        self._rebuild_state: Dict[str, Any] = {
            "running": False,
            "started_at": "",
            "finished_at": "",
            "error": "",
            "stats": None,
        }

    # ---------- 能力与开关 ----------
    @staticmethod
    def platform_supported() -> bool:
        return not is_mobile_core_profile()

    def _configured_engine(self) -> str:
        try:
            return str(self._config_repo.get().search_engine or "").strip().lower()
        except Exception:
            return ""

    def is_enabled(self) -> bool:
        return self.platform_supported() and self._configured_engine() == SEARCH_ENGINE_SEMANTIC

    # ---------- 状态 ----------
    def get_status(self) -> Dict[str, Any]:
        supported = self.platform_supported()
        configured = self._configured_engine()
        payload: Dict[str, Any] = {
            "supported": supported,
            "configured_engine": configured or "catalog",
            "enabled": supported and configured == SEARCH_ENGINE_SEMANTIC,
            "index": {},
        }
        if not supported:
            payload["reason"] = "当前平台不支持语义检索（仅桌面端可用）"
            return payload

        try:
            with semantic_index_connection() as conn:
                payload["index"] = index_status(conn, self._embedder)
        except Exception as exc:
            error_logger.warning(f"读取语义索引状态失败: {exc}")
            payload["index"] = {"indexed": False, "error": str(exc)}
            payload["reason"] = "读取语义索引状态失败"
        payload["rebuild"] = dict(self._rebuild_state)
        return payload

    # ---------- 构建 ----------
    def rebuild(self, *, build_embeddings: bool = True) -> ServiceResult:
        """同步构建（内部/测试用）；HTTP 入口请用 start_rebuild 避免请求超时。"""
        if not self.platform_supported():
            return ServiceResult.error("当前平台不支持语义检索（仅桌面端可用）")
        if not self._rebuild_lock.acquire(blocking=False):
            return ServiceResult.error("语义索引正在构建中，请稍候再试")
        try:
            stats = self._build_locked(build_embeddings=build_embeddings)
            return ServiceResult.ok(stats, "语义索引构建完成")
        except Exception as exc:
            error_logger.exception(f"构建语义索引失败: {exc}")
            return ServiceResult.error("构建语义索引失败")
        finally:
            self._rebuild_lock.release()

    def start_rebuild(self, *, build_embeddings: bool = True) -> ServiceResult:
        """异步构建：首次带向量构建可能要下载模型，不能占着 HTTP 请求。"""
        if not self.platform_supported():
            return ServiceResult.error("当前平台不支持语义检索（仅桌面端可用）")
        if self._rebuild_state.get("running"):
            return ServiceResult.ok(dict(self._rebuild_state), "语义索引正在构建中")
        if not self._rebuild_lock.acquire(blocking=False):
            return ServiceResult.ok(dict(self._rebuild_state), "语义索引正在构建中")

        self._rebuild_state = {
            "running": True,
            "started_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "finished_at": "",
            "error": "",
            "stats": None,
        }
        space_mode = get_current_space_mode()

        def _worker() -> None:
            # 线程本地空间模式：隐私空间触发的重建必须落在隐私空间的数据目录里
            set_current_space_mode(space_mode)
            try:
                stats = self._build_locked(build_embeddings=build_embeddings)
                self._rebuild_state.update({
                    "running": False,
                    "finished_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "error": "",
                    "stats": stats,
                })
            except Exception as exc:  # pragma: no cover - 后台线程
                error_logger.exception(f"后台构建语义索引失败: {exc}")
                self._rebuild_state.update({
                    "running": False,
                    "finished_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "error": str(exc),
                })
            finally:
                self._rebuild_lock.release()

        threading.Thread(target=_worker, name="semantic-index-rebuild", daemon=True).start()
        return ServiceResult.ok(dict(self._rebuild_state), "语义索引开始构建")

    def _build_locked(self, *, build_embeddings: bool) -> Dict[str, Any]:
        started = time.perf_counter()
        with semantic_index_connection() as conn:
            opened = time.perf_counter()
            stats = rebuild_index(conn, self._embedder, build_embeddings=build_embeddings)
            finished = time.perf_counter()
        app_logger.info(
            "语义索引构建完成: %s 本 / 向量 %s 条 / 关键词 %s（打开 %.2fs，构建 %.2fs）",
            stats["doc_count"],
            stats["embedded_count"],
            stats["search_index"],
            opened - started,
            finished - opened,
        )
        return stats

    def _ensure_index_ready(self, conn) -> bool:
        """索引缺失时同步建（不下载模型）；过期时后台刷新，期间先读旧索引。"""
        try:
            status = index_status(conn, self._embedder)
        except Exception:
            return False
        indexed = bool(status.get("indexed"))
        if indexed and not status.get("stale"):
            return True

        if not indexed:
            if not self._rebuild_lock.acquire(blocking=False):
                return False
            try:
                self._last_auto_rebuild = time.time()
                rebuild_index(conn, self._embedder, build_embeddings=False)
                app_logger.info("语义索引缺失，已同步建立（未包含向量）")
                return True
            except Exception as exc:
                error_logger.warning(f"自动重建语义索引失败: {exc}")
                return False
            finally:
                self._rebuild_lock.release()

        # 已建立但过期：先继续用旧索引，后台重建（保留向量能力）
        now = time.time()
        if now - self._last_auto_rebuild >= AUTO_REBUILD_COOLDOWN_SECONDS:
            self._last_auto_rebuild = now
            want_vectors = bool(status.get("vector_enabled")) or bool(getattr(self._embedder, "loaded", False))
            threading.Thread(
                target=self._background_rebuild,
                args=(want_vectors,),
                name="semantic-index-refresh",
                daemon=True,
            ).start()
            app_logger.info("语义索引已过期，后台重建中（向量=%s）", "on" if want_vectors else "off")
        return True

    def _background_rebuild(self, build_embeddings: bool) -> None:
        if not self._rebuild_lock.acquire(blocking=False):
            return
        try:
            with semantic_index_connection() as conn:
                rebuild_index(conn, self._embedder, build_embeddings=build_embeddings)
            app_logger.info("语义索引后台重建完成（向量=%s）", "on" if build_embeddings else "off")
        except Exception as exc:  # pragma: no cover - 后台线程
            error_logger.warning(f"语义索引后台重建失败: {exc}")
        finally:
            self._rebuild_lock.release()

    # ---------- 检索 ----------
    def search(
        self,
        keyword: str,
        *,
        source: str = "local",
        media_type: str = "comic",
        limit: int = 200,
    ) -> Optional[List[str]]:
        """返回按语义相关度排序的 item_id 列表；不可用时返回 None。"""
        if not self.is_enabled():
            return None
        text = str(keyword or "").strip()
        if not text:
            return None
        try:
            with semantic_index_connection() as conn:
                if not self._ensure_index_ready(conn):
                    return None
                payload = semantic_search(
                    conn,
                    text,
                    source=source,
                    media_type=media_type,
                    limit=limit,
                    embedder=self._embedder,
                )
        except Exception as exc:
            error_logger.warning(f"语义检索失败，回落到关键词匹配: {exc}")
            return None

        item_ids = [item["item_id"] for item in payload.get("results") or [] if item.get("item_id")]
        return item_ids or None

    def search_with_debug(
        self,
        keyword: str,
        *,
        source: str = "local",
        media_type: str = "comic",
        limit: int = 50,
    ) -> Dict[str, Any]:
        if not self.platform_supported():
            return {"supported": False, "reason": "当前平台不支持语义检索（仅桌面端可用）", "results": []}
        try:
            with semantic_index_connection() as conn:
                if not self._ensure_index_ready(conn):
                    return {"supported": True, "ready": False, "reason": "语义索引不可用", "results": []}
                payload = semantic_search(
                    conn,
                    keyword,
                    source=source,
                    media_type=media_type,
                    limit=limit,
                    embedder=self._embedder,
                )
        except Exception as exc:
            error_logger.warning(f"语义检索失败: {exc}")
            return {"supported": True, "ready": False, "reason": str(exc), "results": []}
        return {"supported": True, "ready": True, **payload}


_semantic_search_service: Optional[SemanticSearchAppService] = None


def get_semantic_search_service() -> SemanticSearchAppService:
    global _semantic_search_service
    if _semantic_search_service is None:
        _semantic_search_service = SemanticSearchAppService()
    return _semantic_search_service

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from core.enums import ContentType
from core.runtime_profile import is_mobile_core_profile
from core.storage_layout import get_meta_dir
from domain.comic import ComicRepository
from domain.config import ConfigRepository
from domain.config.entity import VisionConfig
from domain.tag import TagRepository
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.repositories import (
    ComicJsonRepository,
    ConfigJsonRepository,
    TagJsonRepository,
)
from infrastructure.vision import (
    VisionClientError,
    call_vision_model_ex,
    fetch_model_ids,
)
from application.vision_providers import list_vision_providers

DRAFT_FILE_NAME = "semantic_vision_drafts.json"
FAILURE_FILE_NAME = "semantic_vision_failures.json"
CONTEXT_FILE_RELATIVE = os.path.join("prompts", "semantic_vision_context.md")
CONTEXT_TEXT_LIMIT = 120_000  # 上下文文件上限，避免误把超大文件塞进请求

DEFAULT_PROMPT = """你是一个成人漫画图书馆的编目助手。下面依次给你一本书的封面、目录页与均匀抽取的内页。
请只输出一个 JSON 对象，不要任何解释、不要 Markdown 代码块，格式如下：
{
  "title": "书名（尽量用作品原名，保留作者与社团信息）",
  "vibe": "整本的气质梗概，80~150 字。写整体的调性、题材走向、人物关系与情节特点，不要罗列篇名",
  "catalog": "收录速览：把目录里的篇名按顺序写成一段，用中文分号分隔，每篇可跟半句内容提示",
  "tags": [
    {"name": "标签名（中文，优先用业界通用说法）", "kind": "人物|关系|场景|玩法|题材"}
  ]
}
要求：
1. vibe 写给检索用的语义向量看，catalog 写给关键词搜索看，两者不要互相重复。
2. tags 给 20~40 个，覆盖人物、关系、场景、玩法、题材；同一概念只出现一次。
3. 看不清的篇名不要编造，可以省略。"""

_TAG_NAME_LIMIT = 40
BATCH_DELAY_SECONDS = 0.8


def sample_page_indexes(
    total_pages: int,
    *,
    max_gap: int = 8,
    max_images: int = 48,
    target_samples: int = 12,
) -> List[int]:
    """按「页数越多间隔越大、间隔不超过 max_gap」的规则抽样（返回 0 基下标）。"""
    total = int(total_pages or 0)
    if total <= 0:
        return []
    gap_limit = max(1, min(8, int(max_gap or 8)))
    target = max(1, int(target_samples or 12))
    gap = max(1, min(gap_limit, math.ceil(total / target)))
    while gap < total and math.ceil(total / gap) > max(1, int(max_images or 48)):
        gap += 1
    return list(range(0, total, gap))


def parse_draft_text(text: str) -> Dict[str, Any]:
    """从模型输出里抠出 JSON（容忍 ```json 包裹与前后废话）。"""
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("模型没有返回内容")
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if fenced:
        raw = fenced.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型返回里没有 JSON 对象")
    payload = json.loads(raw[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("模型返回的不是 JSON 对象")
    if payload.get("blocked"):
        raise ValueError(f"模型未生成描述：{payload.get('reason') or '内容受限'}")

    tags: List[Dict[str, str]] = []
    seen = set()
    for item in payload.get("tags") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            kind = str(item.get("kind") or "题材").strip() or "题材"
        else:
            name, kind = str(item or "").strip(), "题材"
        if not name or name in seen:
            continue
        seen.add(name)
        tags.append({"name": name, "kind": kind})
        if len(tags) >= _TAG_NAME_LIMIT:
            break

    return {
        "title": str(payload.get("title") or "").strip(),
        "vibe": str(payload.get("vibe") or "").strip(),
        "catalog": str(payload.get("catalog") or "").strip(),
        "tags": tags,
    }


class VisionMetadataService:
    """识图补全：读封面/目录页 → 调多模态模型 → 产出 vibe/catalog/tags 草稿 → 人工确认后写回。"""

    def __init__(
        self,
        config_repo: Optional[ConfigRepository] = None,
        comic_repo: Optional[ComicRepository] = None,
        tag_repo: Optional[TagRepository] = None,
    ) -> None:
        self._config_repo = config_repo or ConfigJsonRepository()
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
        self._lock = threading.Lock()
        self._running: Dict[str, Dict[str, Any]] = {}
        self._batch_stop = threading.Event()
        self._batch_state: Dict[str, Any] = {
            "running": False,
            "total": 0,
            "done": 0,
            "failed": 0,
            "current": "",
            "started_at": "",
            "finished_at": "",
            "error": "",
            "items": [],
        }

    # ---------- 配置 ----------
    def get_config(self) -> VisionConfig:
        try:
            return self._config_repo.get().vision_config or VisionConfig()
        except Exception:
            return VisionConfig()

    @staticmethod
    def default_context_path() -> str:
        """项目内置的识图上下文文件（prompts/semantic_vision_context.md）。"""
        bases: List[str] = []
        try:
            import sys

            meipass = getattr(sys, "_MEIPASS", "") or ""
            if meipass:
                bases.append(str(meipass))  # PyInstaller onefile 解包目录
            from core.config_paths import BACKEND_ROOT, PROJECT_ROOT

            bases.extend([BACKEND_ROOT, os.path.join(PROJECT_ROOT, "comic_backend"), PROJECT_ROOT])
        except Exception:
            pass
        bases.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        for base in bases:
            candidate = os.path.join(base, CONTEXT_FILE_RELATIVE)
            if os.path.exists(candidate):
                return os.path.abspath(candidate)
        return os.path.abspath(os.path.join(bases[-1], CONTEXT_FILE_RELATIVE))

    def resolve_context_file(self, config: Optional[VisionConfig] = None) -> str:
        config = config or self.get_config()
        custom = str(getattr(config, "prompt_file", "") or "").strip()
        return os.path.abspath(os.path.expanduser(custom)) if custom else self.default_context_path()

    def load_context_text(self, config: Optional[VisionConfig] = None) -> Dict[str, Any]:
        """读取要随识图请求一起发给模型的上下文文件。"""
        config = config or self.get_config()
        path = self.resolve_context_file(config)
        enabled = bool(getattr(config, "context_enabled", True))
        info = {"enabled": enabled, "path": path, "exists": os.path.exists(path), "chars": 0, "error": ""}
        if not enabled:
            return {**info, "text": ""}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fp:
                text = fp.read(CONTEXT_TEXT_LIMIT)
            info["chars"] = len(text)
            return {**info, "text": text}
        except OSError as exc:
            info["error"] = str(exc)
            return {**info, "text": ""}

    @staticmethod
    def platform_supported() -> bool:
        return not is_mobile_core_profile()

    # ---------- 模型列表 ----------
    def fetch_models(self, base_url: str = "", api_key: str = "") -> Dict[str, Any]:
        """用当前（或临时传入的）Key 拉取服务商模型列表；失败时退回预设模型名。"""
        config = self.get_config()
        url = str(base_url or config.base_url or "").strip()
        key = str(api_key or "").strip()
        if not key or "*" in key:
            key = str(config.api_key or "").strip()

        preset = next(
            (item for item in list_vision_providers() if item["base_url"].rstrip("/") == url.rstrip("/")),
            None,
        )
        preset_models = list((preset or {}).get("models") or [])
        payload: Dict[str, Any] = {
            "base_url": url,
            "models": preset_models,
            "preset_models": preset_models,
            "live": False,
            "error": "",
        }
        if not url or not key:
            payload["error"] = "缺少 Base URL 或 API Key"
            return payload

        try:
            models = fetch_model_ids(base_url=url, api_key=key)
        except VisionClientError as exc:
            payload["error"] = str(exc)
            return payload

        if models:
            payload["models"] = models
            payload["live"] = True
        else:
            payload["error"] = "接口返回的模型列表为空"
        return payload

    def status(self) -> Dict[str, Any]:
        config = self.get_config()
        drafts = self.list_drafts()
        context = self.load_context_text(config)
        return {
            "supported": self.platform_supported(),
            "configured": config.ready,
            "model": config.model,
            "base_url": config.base_url,
            "max_gap": config.max_gap,
            "max_images": config.max_images,
            "draft_count": len(drafts),
            "failure_count": len(self.list_failures()),
            "running": [comic_id for comic_id, state in self._running.items() if state.get("running")],
            "context": {
                "enabled": context["enabled"],
                "path": context["path"],
                "exists": context["exists"],
                "chars": context["chars"],
                "error": context["error"],
            },
            "providers": list_vision_providers(),
        }

    # ---------- 草稿存储 ----------
    def _draft_path(self) -> str:
        meta_dir = get_meta_dir()
        os.makedirs(meta_dir, exist_ok=True)
        return os.path.join(meta_dir, DRAFT_FILE_NAME)

    def _read_drafts(self) -> Dict[str, Dict[str, Any]]:
        path = self._draft_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_drafts(self, drafts: Dict[str, Dict[str, Any]]) -> None:
        path = self._draft_path()
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(drafts, fp, ensure_ascii=False, indent=2)

    def list_drafts(self) -> List[Dict[str, Any]]:
        drafts = self._read_drafts()
        items = list(drafts.values())
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return items

    def get_draft(self, comic_id: str) -> Optional[Dict[str, Any]]:
        return self._read_drafts().get(str(comic_id))

    def delete_draft(self, comic_id: str) -> bool:
        drafts = self._read_drafts()
        if str(comic_id) not in drafts:
            return False
        drafts.pop(str(comic_id), None)
        self._write_drafts(drafts)
        return True

    # ---------- 失败记录 ----------
    def _failure_path(self) -> str:
        meta_dir = get_meta_dir()
        os.makedirs(meta_dir, exist_ok=True)
        return os.path.join(meta_dir, FAILURE_FILE_NAME)

    def _read_failures(self) -> Dict[str, Dict[str, Any]]:
        path = self._failure_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                payload = json.load(fp)
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_failures(self, payload: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(self._failure_path(), "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
        except OSError as exc:
            error_logger.warning(f"写入识图失败记录失败: {exc}")

    def record_failure(self, comic_id: str, error: str) -> None:
        comic_id = str(comic_id or "").strip()
        if not comic_id:
            return
        title = comic_id
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if comic is not None:
                title = str(comic.title or comic_id)
        except Exception:
            pass
        failures = self._read_failures()
        failures[comic_id] = {
            "comic_id": comic_id,
            "title": title,
            "error": str(error or "未知错误"),
            "at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._write_failures(failures)

    def clear_failure(self, comic_id: str) -> bool:
        failures = self._read_failures()
        if str(comic_id) not in failures:
            return False
        failures.pop(str(comic_id), None)
        self._write_failures(failures)
        return True

    def list_failures(self) -> List[Dict[str, Any]]:
        items = list(self._read_failures().values())
        items.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
        return items

    # ---------- 生成草稿 ----------
    def start_draft(self, comic_id: str) -> Dict[str, Any]:
        comic_id = str(comic_id or "").strip()
        if not comic_id:
            raise ValueError("缺少 comic_id")
        if not self.platform_supported():
            raise ValueError("当前平台不支持识图补全（仅桌面端可用）")
        config = self.get_config()
        if not config.ready:
            raise ValueError("尚未配置识图模型（Base URL / API Key / 模型名）")
        if self._running.get(comic_id, {}).get("running"):
            return dict(self._running[comic_id])

        state = {"running": True, "started_at": time.time(), "error": "", "pages": []}
        self._running[comic_id] = state

        def _worker() -> None:
            try:
                draft = self._build_draft(comic_id, config, state)
                drafts = self._read_drafts()
                drafts[comic_id] = draft
                with self._lock:
                    self._write_drafts(drafts)
                self.clear_failure(comic_id)
                state.update({"running": False, "error": ""})
                app_logger.info(f"识图补全草稿已生成: {comic_id}")
            except Exception as exc:  # pragma: no cover - 后台线程
                error_logger.warning(f"识图补全失败: {comic_id} {exc}")
                state.update({"running": False, "error": str(exc)})
                self.record_failure(comic_id, str(exc))
            finally:
                self._running.pop(comic_id, None)

        threading.Thread(target=_worker, name=f"vision-draft-{comic_id}", daemon=True).start()
        return dict(state)

    def draft_state(self, comic_id: str) -> Dict[str, Any]:
        return dict(self._running.get(str(comic_id), {}))

    # ---------- 批量补全 ----------
    def list_missing_comics(self, *, only_missing: bool = True) -> List[Dict[str, Any]]:
        """列出缺梗概/缺速览的漫画（默认只要 vibe 或 catalog 为空的本）。"""
        try:
            comics = self._comic_repo.get_all() or []
        except Exception as exc:
            error_logger.warning(f"读取漫画列表失败: {exc}")
            return []

        drafts = self._read_drafts()
        items: List[Dict[str, Any]] = []
        for comic in comics:
            if getattr(comic, "is_deleted", False):
                continue
            vibe = str(getattr(comic, "vibe", "") or "").strip()
            catalog = str(getattr(comic, "catalog", "") or "").strip()
            if only_missing and vibe and catalog:
                continue
            items.append({
                "comic_id": str(comic.id),
                "title": str(comic.title or comic.id),
                "total_page": int(getattr(comic, "total_units", 0) or 0),
                "has_draft": str(comic.id) in drafts,
                "missing_vibe": not vibe,
                "missing_catalog": not catalog,
            })
        items.sort(key=lambda item: (not item["missing_vibe"], item["total_page"]))
        return items

    def batch_state(self) -> Dict[str, Any]:
        return dict(self._batch_state)

    def stop_batch(self) -> Dict[str, Any]:
        if self._batch_state.get("running"):
            self._batch_stop.set()
            self._batch_state["error"] = "已请求停止"
        return dict(self._batch_state)

    def start_batch(
        self,
        *,
        only_missing: bool = True,
        limit: int = 0,
        comic_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        if not self.platform_supported():
            raise ValueError("当前平台不支持识图补全（仅桌面端可用）")
        config = self.get_config()
        if not config.ready:
            raise ValueError("尚未配置识图模型（Base URL / API Key / 模型名）")
        if self._batch_state.get("running"):
            return dict(self._batch_state)

        if comic_ids:
            wanted = {str(item).strip() for item in comic_ids if str(item).strip()}
            queue = [item for item in self.list_missing_comics(only_missing=False) if item["comic_id"] in wanted]
        else:
            queue = self.list_missing_comics(only_missing=only_missing)
        limit = int(limit or 0)
        if limit > 0:
            queue = queue[:limit]

        self._batch_stop.clear()
        self._batch_state = {
            "running": bool(queue),
            "total": len(queue),
            "done": 0,
            "failed": 0,
            "current": "",
            "started_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "finished_at": "" if queue else datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "error": "" if queue else "没有需要补全的漫画",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0},
            "items": [
                {"comic_id": item["comic_id"], "title": item["title"], "status": "queued", "error": ""}
                for item in queue
            ],
        }
        if not queue:
            return dict(self._batch_state)

        threading.Thread(
            target=self._batch_worker,
            args=(queue, config, self._current_space_mode()),
            name="vision-batch",
            daemon=True,
        ).start()
        return dict(self._batch_state)

    @staticmethod
    def _current_space_mode():
        try:
            from core.storage_layout import get_current_space_mode

            return get_current_space_mode()
        except Exception:
            return None

    def _batch_worker(self, queue: List[Dict[str, Any]], config: VisionConfig, space_mode=None) -> None:
        if space_mode is not None:
            try:
                from core.storage_layout import set_current_space_mode

                set_current_space_mode(space_mode)
            except Exception:
                pass

        for index, entry in enumerate(queue):
            if self._batch_stop.is_set():
                for rest in queue[index:]:
                    self._mark_batch_item(rest["comic_id"], "cancelled", "")
                break
            comic_id = entry["comic_id"]
            self._batch_state["current"] = entry["title"]
            self._mark_batch_item(comic_id, "running", "")
            try:
                state: Dict[str, Any] = {"pages": []}
                draft = self._build_draft(comic_id, config, state)
                drafts = self._read_drafts()
                drafts[comic_id] = draft
                with self._lock:
                    self._write_drafts(drafts)
                self._batch_state["done"] = int(self._batch_state.get("done", 0)) + 1
                self._accumulate_usage(draft.get("usage") or {})
                self.clear_failure(comic_id)
                self._mark_batch_item(comic_id, "ready", "")
            except Exception as exc:
                error_logger.warning(f"批量识图补全失败: {comic_id} {exc}")
                self._batch_state["failed"] = int(self._batch_state.get("failed", 0)) + 1
                self.record_failure(comic_id, str(exc))
                self._mark_batch_item(comic_id, "failed", str(exc))
            time.sleep(BATCH_DELAY_SECONDS)

        self._batch_state["running"] = False
        self._batch_state["current"] = ""
        self._batch_state["finished_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        app_logger.info(
            f"批量识图补全结束: 成功 {self._batch_state.get('done', 0)} / "
            f"失败 {self._batch_state.get('failed', 0)} / 共 {self._batch_state.get('total', 0)}"
        )

    def _accumulate_usage(self, usage: Dict[str, Any]) -> None:
        bucket = self._batch_state.setdefault(
            "usage", {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
        )
        for key in ("prompt_tokens", "completion_tokens", "cached_tokens"):
            try:
                bucket[key] = int(bucket.get(key, 0)) + int(usage.get(key) or 0)
            except (TypeError, ValueError):
                continue

    def _mark_batch_item(self, comic_id: str, status: str, error: str) -> None:
        for item in self._batch_state.get("items", []):
            if item["comic_id"] == comic_id:
                item["status"] = status
                item["error"] = error
                break

    def _build_draft(self, comic_id: str, config: VisionConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        from utils.file_parser import file_parser  # 避免循环依赖，放到函数内

        comic = self._comic_repo.get_by_id(comic_id)
        if comic is None:
            raise ValueError("漫画不存在")

        image_paths = file_parser.parse_comic_images(comic_id) or []
        if not image_paths:
            raise ValueError("没有找到可读取的图片页")
        indexes = sample_page_indexes(
            len(image_paths),
            max_gap=config.max_gap,
            max_images=config.max_images,
        )
        selected = [image_paths[index] for index in indexes if 0 <= index < len(image_paths)]
        state["pages"] = [index + 1 for index in indexes]

        prompt = f"{config.prompt.strip() or DEFAULT_PROMPT}"
        context = self.load_context_text(config)
        response = call_vision_model_ex(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            prompt=prompt,
            system_prompt=context.get("text", ""),
            image_paths=selected,
            timeout_seconds=config.timeout_seconds,
        )
        text = response.get("text", "")
        usage = response.get("usage") or {}
        parsed = parse_draft_text(text)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return {
            "comic_id": comic_id,
            "title": parsed.get("title") or comic.title,
            "current_title": comic.title,
            "status": "ready",
            "draft": {
                "vibe": parsed.get("vibe", ""),
                "catalog": parsed.get("catalog", ""),
                "tags": parsed.get("tags", []),
            },
            "model": config.model,
            "usage": usage,
            "context": {
                "used": bool(context.get("text")),
                "path": context.get("path", ""),
                "chars": context.get("chars", 0),
            },
            "total_pages": len(image_paths),
            "sampled_pages": [index + 1 for index in indexes],
            "sampled_count": len(selected),
            "created_at": now,
        }

    # ---------- 应用草稿 ----------
    def apply_draft(self, comic_id: str, accept: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        comic_id = str(comic_id or "").strip()
        draft = self.get_draft(comic_id)
        if draft is None:
            raise ValueError("没有待确认的草稿")

        source = draft.get("draft") or {}
        accept = accept or {}
        updates: Dict[str, Any] = {}
        if accept.get("vibe", True):
            updates["vibe"] = str(accept.get("vibe_text") or source.get("vibe") or "")
        if accept.get("catalog", True):
            updates["catalog"] = str(accept.get("catalog_text") or source.get("catalog") or "")

        tag_payloads = accept.get("tags")
        if tag_payloads is None:
            tag_payloads = source.get("tags") or []

        comic = self._comic_repo.get_by_id(comic_id)
        if comic is None:
            raise ValueError("漫画不存在")

        comic.update_meta(updates)
        tag_ids = self._resolve_tag_ids(tag_payloads)
        if tag_ids:
            comic.add_tags(tag_ids)
        if not self._comic_repo.save(comic):
            raise ValueError("保存漫画失败")

        self.delete_draft(comic_id)
        app_logger.info(
            f"识图补全已写回: {comic_id}（梗概 {'有' if updates.get('vibe') else '无'} / "
            f"速览 {'有' if updates.get('catalog') else '无'} / 新增标签 {len(tag_ids)}）"
        )
        return {
            "comic_id": comic_id,
            "vibe": updates.get("vibe", ""),
            "catalog": updates.get("catalog", ""),
            "tag_ids": tag_ids,
            "applied_tags": len(tag_ids),
        }

    def _resolve_tag_ids(self, payloads: Sequence[Any]) -> List[str]:
        existing = {tag.name.strip().lower(): tag for tag in self._tag_repo.get_all(ContentType.COMIC) or []}
        resolved: List[str] = []
        for item in payloads or []:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                kind = str(item.get("kind") or "题材").strip() or "题材"
            else:
                name, kind = str(item or "").strip(), "题材"
            if not name:
                continue
            tag = existing.get(name.lower())
            if tag is None:
                tag = self._tag_repo.create(name, ContentType.COMIC)
                if tag is None:
                    continue
                if kind and getattr(tag, "kind", "") != kind:
                    try:
                        tag.kind = kind
                        self._tag_repo.save(tag)
                    except Exception:
                        pass
                existing[name.lower()] = tag
            if tag.id and tag.id not in resolved:
                resolved.append(tag.id)
        return resolved


_vision_metadata_service: Optional[VisionMetadataService] = None


def get_vision_metadata_service() -> VisionMetadataService:
    global _vision_metadata_service
    if _vision_metadata_service is None:
        _vision_metadata_service = VisionMetadataService()
    return _vision_metadata_service

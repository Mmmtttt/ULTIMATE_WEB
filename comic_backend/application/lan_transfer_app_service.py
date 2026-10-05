from __future__ import annotations

import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from core.constants import CACHE_ROOT_DIR, LAN_TRANSFER_JSON_FILE
from core.utils import generate_uuid, get_current_time
from infrastructure.common.result import ServiceResult
from infrastructure.logger import error_logger
from infrastructure.persistence.json_storage import JsonStorage


class LanTransferAppService:
    """Lightweight LAN text/file handoff independent from data sync."""

    UPLOAD_DIR_NAME = "lan_transfer/uploads"
    MAX_ITEMS = 80

    def __init__(self, storage: Optional[JsonStorage] = None):
        self._storage = storage or JsonStorage(LAN_TRANSFER_JSON_FILE)

    def list_items(self) -> ServiceResult:
        try:
            data = self._normalize_data(self._storage.read())
            return ServiceResult.ok({"items": [self._public_item(item) for item in data["items"]]})
        except Exception as exc:
            error_logger.error(f"读取局域网传输列表失败: {exc}")
            return ServiceResult.error("读取局域网传输列表失败")

    def publish_text(self, text: str, name: str = "") -> ServiceResult:
        content = str(text or "")
        if not content.strip():
            return ServiceResult.error("文字内容不能为空")

        item = {
            "id": generate_uuid(),
            "kind": "text",
            "name": self._normalize_download_name(name, "shared-text.txt"),
            "text": content,
            "size": len(content.encode("utf-8")),
            "mime_type": "text/plain; charset=utf-8",
            "created_at": get_current_time(),
        }
        if not self._insert_item(item):
            return ServiceResult.error("发布文字失败")
        return ServiceResult.ok(self._public_item(item))

    def register_server_file(self, file_path: str, name: str = "") -> ServiceResult:
        path = Path(str(file_path or "").strip()).expanduser()
        if not path:
            return ServiceResult.error("服务器文件路径不能为空")
        try:
            resolved_path = path.resolve()
        except Exception:
            return ServiceResult.error("服务器文件路径无效")
        if not resolved_path.is_file():
            return ServiceResult.error("服务器文件不存在")

        stat = resolved_path.stat()
        item = {
            "id": generate_uuid(),
            "kind": "server_file",
            "name": self._normalize_download_name(name, resolved_path.name),
            "server_path": str(resolved_path),
            "size": int(stat.st_size),
            "mime_type": mimetypes.guess_type(str(resolved_path))[0] or "application/octet-stream",
            "created_at": get_current_time(),
        }
        if not self._insert_item(item):
            return ServiceResult.error("登记服务器文件失败")
        return ServiceResult.ok(self._public_item(item))

    def save_upload(self, file_storage: Any) -> ServiceResult:
        if file_storage is None or not str(getattr(file_storage, "filename", "") or "").strip():
            return ServiceResult.error("请选择要上传的文件")

        original_name = os.path.basename(str(file_storage.filename or "").strip()) or "uploaded-file"
        item_id = generate_uuid()
        upload_dir = self._upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(original_name).suffix
        stored_path = upload_dir / f"{item_id}{suffix}"
        file_storage.save(str(stored_path))

        item = {
            "id": item_id,
            "kind": "upload",
            "name": original_name,
            "stored_path": str(stored_path),
            "size": int(stored_path.stat().st_size) if stored_path.exists() else 0,
            "mime_type": getattr(file_storage, "mimetype", None)
            or mimetypes.guess_type(original_name)[0]
            or "application/octet-stream",
            "created_at": get_current_time(),
        }
        if not self._insert_item(item):
            try:
                stored_path.unlink(missing_ok=True)
            except Exception:
                pass
            return ServiceResult.error("上传文件保存失败")
        return ServiceResult.ok(self._public_item(item))

    def delete_item(self, item_id: str) -> ServiceResult:
        normalized_id = str(item_id or "").strip()
        if not normalized_id:
            return ServiceResult.error("缺少传输项 ID")

        removed_item: Optional[Dict[str, Any]] = None

        def update_data(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            nonlocal removed_item
            normalized = self._normalize_data(data)
            next_items = []
            for item in normalized["items"]:
                if str(item.get("id") or "") == normalized_id:
                    removed_item = item
                    continue
                next_items.append(item)
            if removed_item is None:
                return None
            normalized["items"] = next_items
            normalized["last_updated"] = get_current_time()
            return normalized

        if not self._storage.atomic_update(update_data):
            return ServiceResult.error("传输项不存在")

        if removed_item and removed_item.get("kind") == "upload":
            self._remove_uploaded_file(str(removed_item.get("stored_path") or ""))
        return ServiceResult.ok({"id": normalized_id, "deleted": True})

    def resolve_download(self, item_id: str) -> ServiceResult:
        item = self._find_item(item_id)
        if not item:
            return ServiceResult.error("传输项不存在")
        kind = str(item.get("kind") or "")
        if kind == "text":
            return ServiceResult.ok(
                {
                    "kind": "text",
                    "content": str(item.get("text") or ""),
                    "name": item.get("name") or "shared-text.txt",
                    "mime_type": item.get("mime_type") or "text/plain; charset=utf-8",
                }
            )
        if kind == "upload":
            path = Path(str(item.get("stored_path") or ""))
        elif kind == "server_file":
            path = Path(str(item.get("server_path") or ""))
        else:
            return ServiceResult.error("传输项类型无效")

        if not path.is_file():
            return ServiceResult.error("文件不存在或已被移动")
        return ServiceResult.ok(
            {
                "kind": kind,
                "path": str(path),
                "name": item.get("name") or path.name,
                "mime_type": item.get("mime_type") or mimetypes.guess_type(str(path))[0] or "application/octet-stream",
            }
        )

    def _insert_item(self, item: Dict[str, Any]) -> bool:
        def update_data(data: Dict[str, Any]) -> Dict[str, Any]:
            normalized = self._normalize_data(data)
            normalized["items"] = [item] + normalized["items"][: self.MAX_ITEMS - 1]
            normalized["last_updated"] = item.get("created_at") or get_current_time()
            return normalized

        return self._storage.atomic_update(update_data)

    def _find_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        normalized_id = str(item_id or "").strip()
        if not normalized_id:
            return None
        data = self._normalize_data(self._storage.read())
        return next((item for item in data["items"] if str(item.get("id") or "") == normalized_id), None)

    def _normalize_data(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = dict(data or {})
        items = normalized.get("items")
        normalized["items"] = list(items) if isinstance(items, list) else []
        return normalized

    def _public_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        public = {
            "id": item.get("id") or "",
            "kind": item.get("kind") or "",
            "name": item.get("name") or "",
            "size": int(item.get("size") or 0),
            "mime_type": item.get("mime_type") or "",
            "created_at": item.get("created_at") or "",
            "server_path": item.get("server_path") if item.get("kind") == "server_file" else "",
        }
        if item.get("kind") == "text":
            public["text"] = str(item.get("text") or "")
        return public

    def _upload_dir(self) -> Path:
        return Path(str(CACHE_ROOT_DIR)) / self.UPLOAD_DIR_NAME

    def _remove_uploaded_file(self, stored_path: str) -> None:
        if not stored_path:
            return
        try:
            target = Path(stored_path).resolve()
            upload_root = self._upload_dir().resolve()
            if upload_root in target.parents and target.is_file():
                target.unlink()
        except Exception as exc:
            error_logger.warning(f"删除局域网上传文件失败: {stored_path}, {exc}")

    def _normalize_download_name(self, name: str, fallback: str) -> str:
        value = os.path.basename(str(name or "").strip())
        fallback_value = os.path.basename(str(fallback or "").strip()) or "download"
        return value or fallback_value

    def clear_uploads_for_tests(self) -> None:
        shutil.rmtree(self._upload_dir(), ignore_errors=True)

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.constants import CACHE_ROOT_DIR, LOCAL_PICTURES_DIR, SUPPORTED_FORMATS, TAGS_JSON_FILE
from infrastructure.archive import ensure_rar_backend_configured
from infrastructure.logger import app_logger
from infrastructure.persistence.json_storage import JsonStorage
from utils.file_parser import file_parser
from utils.image_handler import image_handler

try:
    import py7zr  # type: ignore
except Exception:  # pragma: no cover
    py7zr = None

try:
    import rarfile  # type: ignore
except Exception:  # pragma: no cover
    rarfile = None


ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
IMAGE_EXTENSIONS = {str(ext).lower() for ext in SUPPORTED_FORMATS}
MAX_NESTED_DEPTH = 30
SOFTREF_PASSWORDS_FILE = Path(CACHE_ROOT_DIR) / "comic_softref_passwords.json"
LOCAL_IMPORT_TAG_NAME = "本地"
IMPORT_MODE_COPY_SAFE = "copy_safe"
IMPORT_MODE_MOVE_HUGE = "move_huge"
IMPORT_MODE_HARDLINK_MOVE = "hardlink_move"
IMPORT_MODE_SOFTLINK_REF = "softlink_ref"
SESSION_PHASE_PREPARING = "preparing"
SESSION_PHASE_READY = "ready_for_mark"
SESSION_PHASE_COMMITTING = "committing"
SESSION_PHASE_COMPLETED = "completed"
SESSION_PHASE_FAILED = "failed"

LOCAL_IMPORT_WORKSPACE_DIR = Path(CACHE_ROOT_DIR) / "comic_local_import_workspace"
LOCAL_IMPORT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
ensure_rar_backend_configured(logger=app_logger)


class LocalComicImportService:
    def __init__(self):
        self._db_storage = JsonStorage()
        self._tag_storage = JsonStorage(TAGS_JSON_FILE)

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    def _session_dir(self, session_id: str) -> Path:
        return LOCAL_IMPORT_WORKSPACE_DIR / session_id

    def _tree_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "tree.json"

    def _meta_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "meta.json"

    def _result_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "result.json"

    def _state_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "import_state.json"

    def _prepare_state_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "prepare_state.json"

    def _ensure_session_dir(self, session_id: str) -> Path:
        path = self._session_dir(session_id)
        if not path.exists():
            raise ValueError("会话不存在或已失效")
        return path

    @staticmethod
    def _normalize_import_mode(raw_mode: Optional[str]) -> str:
        mode = str(raw_mode or "").strip().lower()
        if mode in {IMPORT_MODE_MOVE_HUGE, IMPORT_MODE_HARDLINK_MOVE}:
            return IMPORT_MODE_MOVE_HUGE
        if mode == IMPORT_MODE_SOFTLINK_REF:
            return IMPORT_MODE_SOFTLINK_REF
        return IMPORT_MODE_COPY_SAFE

    @staticmethod
    def _normalize_source_path_input(source_path: str) -> Path:
        raw = str(source_path or "").strip()
        if not raw:
            raise ValueError("缺少 source_path")

        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1].strip()

        normalized_raw = raw.replace("\\", "/").lower()
        if "/fakepath/" in normalized_raw:
            raise ValueError("检测到浏览器虚拟路径（fakepath）。请手动粘贴服务端本机可访问的真实绝对路径。")

        source = Path(os.path.expandvars(raw)).expanduser()
        try:
            source = source.resolve()
        except Exception:
            source = Path(os.path.abspath(os.path.expandvars(os.path.expanduser(raw))))
        return source

    @staticmethod
    def _is_same_filesystem(src_dir: Path, dst_dir: Path) -> bool:
        try:
            src_abs = src_dir.resolve()
            dst_abs = dst_dir.resolve()
        except Exception:
            src_abs = Path(os.path.abspath(str(src_dir)))
            dst_abs = Path(os.path.abspath(str(dst_dir)))

        if os.name == "nt":
            src_drive = os.path.splitdrive(str(src_abs))[0].lower()
            dst_drive = os.path.splitdrive(str(dst_abs))[0].lower()
            return bool(src_drive) and src_drive == dst_drive

        try:
            return os.stat(src_abs).st_dev == os.stat(dst_abs).st_dev
        except Exception:
            return False

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_meta(self, session_id: str) -> Dict[str, Any]:
        meta = self._read_json(self._meta_path(session_id), default={}) or {}
        if not isinstance(meta, dict):
            return {}
        return meta

    def _update_meta(self, session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        meta = self._load_meta(session_id)
        meta.update(updates or {})
        meta["updated_at"] = self._timestamp()
        self._write_json(self._meta_path(session_id), meta)
        return meta

    @staticmethod
    def _is_image(path: Path) -> bool:
        return path.suffix.lower() in IMAGE_EXTENSIONS

    @staticmethod
    def _is_archive(path: Path) -> bool:
        return path.suffix.lower() in ARCHIVE_EXTENSIONS

    @staticmethod
    def _looks_like_image_name(filename: str) -> bool:
        return Path(str(filename or "")).suffix.lower() in IMAGE_EXTENSIONS

    @staticmethod
    def _looks_like_archive_name(filename: str) -> bool:
        return Path(str(filename or "")).suffix.lower() in ARCHIVE_EXTENSIONS

    @staticmethod
    def _is_softref_locator(raw_path: str) -> bool:
        return str(raw_path or "").startswith("softref://")

    @staticmethod
    def _encode_softref_locator(payload: Dict[str, Any]) -> str:
        raw = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
        encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
        return f"softref://{encoded}"

    @staticmethod
    def _decode_softref_locator(locator: str) -> Dict[str, Any]:
        raw = str(locator or "").strip()
        if not raw.startswith("softref://"):
            return {}
        encoded = raw[len("softref://") :]
        if not encoded:
            return {}
        padding = "=" * ((4 - len(encoded) % 4) % 4)
        decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _softref_archive_fingerprint(top_archive_path: str, archive_chain: List[str]) -> str:
        top = os.path.normcase(os.path.abspath(str(top_archive_path or "")))
        chain = "|".join(str(item or "") for item in (archive_chain or []))
        raw = f"{top}::{chain}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _load_softref_password_store(self) -> Dict[str, Any]:
        if not SOFTREF_PASSWORDS_FILE.exists():
            return {"archives": {}}
        try:
            payload = json.loads(SOFTREF_PASSWORDS_FILE.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {"archives": {}}
            archives = payload.get("archives")
            if not isinstance(archives, dict):
                payload["archives"] = {}
            return payload
        except Exception:
            return {"archives": {}}

    def _save_softref_password_store(self, payload: Dict[str, Any]) -> None:
        normalized = payload if isinstance(payload, dict) else {"archives": {}}
        normalized.setdefault("archives", {})
        SOFTREF_PASSWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SOFTREF_PASSWORDS_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def _remember_softref_archive_password(self, locator: str, archive_password: Optional[str]) -> bool:
        password = str(archive_password or "").strip()
        if not password:
            return False
        try:
            payload = self._decode_softref_locator(locator)
        except Exception:
            return False
        if str(payload.get("kind", "")).strip().lower() != "archive_dir":
            return False
        top_archive_path = str(payload.get("top_archive_path", "")).strip()
        archive_chain = [str(item or "") for item in (payload.get("archive_chain") or [])]
        if not top_archive_path:
            return False

        fingerprint = self._softref_archive_fingerprint(top_archive_path, archive_chain)
        store = self._load_softref_password_store()
        archives = store.setdefault("archives", {})
        archives[fingerprint] = {
            "password": password,
            "updated_at": self._timestamp(),
        }
        self._save_softref_password_store(store)
        return True

    @staticmethod
    def _normalize_name(name: str) -> str:
        return "".join(ch.lower() for ch in str(name or "") if ch not in {" ", "_", "-", "."})

    @staticmethod
    def _strip_archive_suffix(filename: str) -> str:
        path = Path(filename)
        return path.stem if path.suffix else filename

    @staticmethod
    def _make_unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for index in range(2, 10_000):
            candidate = path.with_name(f"{stem}__{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"无法为路径生成可用名称: {path}")

    @staticmethod
    def _sorted_entries(entries: List[Path]) -> List[Path]:
        return sorted(entries, key=lambda item: (not item.is_dir(), LocalComicImportService._natural_sort_key(item.name)))

    @staticmethod
    def _natural_sort_key(text: str) -> List[Tuple[int, Any]]:
        parts: List[Tuple[int, Any]] = []
        chunk = ""
        for ch in str(text or ""):
            if ch.isdigit():
                if chunk and not chunk[-1].isdigit():
                    parts.append((1, chunk.lower()))
                    chunk = ""
                chunk += ch
            else:
                if chunk and chunk[-1].isdigit():
                    parts.append((0, int(chunk)))
                    chunk = ""
                chunk += ch
        if chunk:
            if chunk.isdigit():
                parts.append((0, int(chunk)))
            else:
                parts.append((1, chunk.lower()))
        return parts

    @staticmethod
    def _is_safe_member_name(member_name: str) -> bool:
        normalized = str(member_name or "").replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute():
            return False
        for part in pure.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                return False
            if len(part) >= 2 and part[1] == ":":
                return False
        return True

    def _safe_target_from_member(self, dest_dir: Path, member_name: str) -> Optional[Path]:
        if not self._is_safe_member_name(member_name):
            raise ValueError(f"压缩包内包含非法路径: {member_name}")
        pure = PurePosixPath(str(member_name).replace("\\", "/"))
        parts = [part for part in pure.parts if part not in {"", "."}]
        if not parts:
            return None
        return dest_dir.joinpath(*parts)

    def _new_virtual_node(
        self,
        node_id: str,
        display_name: str,
        real_name: str,
        abs_path: str,
        parent_id: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "id": node_id,
            "name": "根目录" if node_id == "." else display_name,
            "real_name": real_name if node_id != "." else display_name,
            "abs_path": abs_path,
            "rel_path": "." if node_id == "." else node_id,
            "direct_images": 0,
            "total_images": 0,
            "children": [],
            "_child_index": {},
            "_parent_id": parent_id,
        }

    def _ensure_virtual_dir_child(
        self,
        parent: Dict[str, Any],
        segment: str,
        abs_path: str,
        *,
        allow_reuse: bool = True,
    ) -> Dict[str, Any]:
        raw_segment = str(segment or "").strip() or "未命名目录"
        child_index = parent.setdefault("_child_index", {})

        if allow_reuse and raw_segment in child_index:
            child = child_index[raw_segment]
            if abs_path:
                child["abs_path"] = abs_path
            return child

        final_segment = raw_segment
        if final_segment in child_index:
            suffix = 2
            while f"{raw_segment}__{suffix}" in child_index:
                suffix += 1
            final_segment = f"{raw_segment}__{suffix}"

        parent_id = str(parent.get("id") or ".")
        node_id = final_segment if parent_id == "." else f"{parent_id}/{final_segment}"
        child = self._new_virtual_node(
            node_id=node_id,
            display_name=final_segment,
            real_name=final_segment,
            abs_path=abs_path,
            parent_id=parent_id,
        )
        child_index[final_segment] = child
        parent.setdefault("children", []).append(child)
        return child

    def _finalize_virtual_tree(self, root: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        node_map: Dict[str, Dict[str, Any]] = {}

        def walk(node: Dict[str, Any]) -> Dict[str, Any]:
            raw_children = list(node.get("children", []) or [])
            children = sorted(
                raw_children,
                key=lambda item: (
                    str(item.get("real_name", "")).lower(),
                    str(item.get("real_name", "")),
                ),
            )

            child_ids: List[str] = []
            total_images = int(node.get("direct_images", 0) or 0)
            finalized_children: List[Dict[str, Any]] = []
            for child in children:
                finalized = walk(child)
                finalized_children.append(finalized)
                child_ids.append(str(finalized.get("id") or ""))
                total_images += int(finalized.get("total_images", 0) or 0)

            node["children"] = finalized_children
            node["total_images"] = total_images
            node.pop("_child_index", None)
            parent_id = node.pop("_parent_id", None)

            node_id = str(node.get("id") or "")
            node_map[node_id] = {
                "id": node_id,
                "name": str(node.get("name") or ""),
                "real_name": str(node.get("real_name") or ""),
                "abs_path": str(node.get("abs_path") or ""),
                "rel_path": str(node.get("rel_path") or "."),
                "direct_images": int(node.get("direct_images", 0) or 0),
                "total_images": int(node.get("total_images", 0) or 0),
                "parent_id": parent_id,
                "child_ids": child_ids,
            }
            return node

        tree = walk(root)
        return tree, node_map

    def _make_archive_softref_locator(
        self,
        source_path: str,
        top_archive_path: str,
        archive_chain: List[str],
        inner_path: str,
    ) -> str:
        return self._encode_softref_locator(
            {
                "kind": "archive_dir",
                "source_path": str(source_path or ""),
                "top_archive_path": str(top_archive_path or ""),
                "archive_chain": list(archive_chain or []),
                "inner_path": str(inner_path or "."),
            }
        )

    def _populate_virtual_archive_node(
        self,
        archive_node: Dict[str, Any],
        members: List[Dict[str, Any]],
        *,
        source_path: str,
        top_archive_path: str,
        archive_chain: List[str],
        depth: int,
        archive_password: Optional[str],
        warnings: List[str],
        read_member_bytes: Optional[Callable[[str], bytes]] = None,
    ) -> None:
        def ensure_inner_dir(path_parts: List[str]) -> Dict[str, Any]:
            current = archive_node
            current_parts: List[str] = []
            for part in path_parts:
                current_parts.append(part)
                locator = self._make_archive_softref_locator(
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    inner_path="/".join(current_parts) or ".",
                )
                current = self._ensure_virtual_dir_child(current, part, locator, allow_reuse=True)
            return current

        sorted_members = sorted(
            list(members or []),
            key=lambda item: (str(item.get("name", "")).replace("\\", "/").lower(), str(item.get("name", ""))),
        )

        for member in sorted_members:
            member_name = str(member.get("name") or "").replace("\\", "/")
            if not member_name:
                continue
            if not self._is_safe_member_name(member_name):
                warnings.append(f"压缩包内包含非法路径，已跳过: {member_name}")
                continue

            pure = PurePosixPath(member_name)
            parts = [part for part in pure.parts if part not in {"", "."}]
            if not parts:
                continue

            is_dir = bool(member.get("is_dir", False))
            if is_dir:
                ensure_inner_dir(parts)
                continue

            parent_parts = parts[:-1]
            leaf_name = parts[-1]
            leaf_parent = ensure_inner_dir(parent_parts) if parent_parts else archive_node

            if self._looks_like_image_name(leaf_name):
                leaf_parent["direct_images"] = int(leaf_parent.get("direct_images", 0) or 0) + 1
                continue

            if not self._looks_like_archive_name(leaf_name):
                continue

            warnings.append(f"检测到内层压缩包，按导入规则已跳过: {member_name}")
            continue

    def _scan_archive_path_into_virtual_node(
        self,
        archive_node: Dict[str, Any],
        archive_path: Path,
        *,
        source_path: str,
        top_archive_path: str,
        archive_chain: List[str],
        depth: int,
        archive_password: Optional[str],
        warnings: List[str],
    ) -> None:
        suffix = archive_path.suffix.lower()
        if suffix == ".zip":
            pwd_bytes = archive_password.encode("utf-8") if archive_password else None
            with zipfile.ZipFile(archive_path, "r") as zf:
                if pwd_bytes:
                    zf.setpassword(pwd_bytes)
                infos = [info for info in zf.infolist() if not stat.S_ISLNK(info.external_attr >> 16)]
                members = [{"name": str(info.filename or ""), "is_dir": bool(info.is_dir())} for info in infos]
                info_map = {str(info.filename or ""): info for info in infos}

                def read_member_bytes(name: str) -> bytes:
                    info = info_map[name]
                    if pwd_bytes:
                        with zf.open(info, "r", pwd=pwd_bytes) as src:
                            return src.read()
                    with zf.open(info, "r") as src:
                        return src.read()

                self._populate_virtual_archive_node(
                    archive_node=archive_node,
                    members=members,
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                    read_member_bytes=read_member_bytes,
                )
            return

        if suffix == ".rar":
            if rarfile is None:
                warnings.append(f"缺少 rarfile 依赖，无法解析: {archive_path.name}")
                return
            with rarfile.RarFile(archive_path) as rf:  # type: ignore[arg-type]
                if archive_password and hasattr(rf, "setpassword"):
                    rf.setpassword(archive_password)
                infos = list(rf.infolist())
                if not infos and archive_password:
                    warnings.append(
                        f"未能读取加密 RAR 目录结构，已跳过: {archive_path.name}。"
                        "可能是当前系统解包后端不支持密码读取。"
                    )
                    return
                members: List[Dict[str, Any]] = []
                info_map: Dict[str, Any] = {}
                for info in infos:
                    member_name = str(getattr(info, "filename", "") or "")
                    if not member_name:
                        continue
                    is_dir = False
                    if hasattr(info, "is_dir"):
                        is_dir = bool(info.is_dir())
                    elif hasattr(info, "isdir"):
                        is_dir = bool(info.isdir())
                    if hasattr(info, "is_symlink") and info.is_symlink():
                        continue
                    members.append({"name": member_name, "is_dir": is_dir})
                    info_map[member_name] = info

                before_children = len(list(archive_node.get("children") or []))
                before_direct_images = int(archive_node.get("direct_images", 0) or 0)

                def read_member_bytes(name: str) -> bytes:
                    info = info_map[name]
                    kwargs: Dict[str, Any] = {}
                    if archive_password:
                        kwargs["pwd"] = archive_password
                    with rf.open(info, "r", **kwargs) as src:
                        return src.read()

                self._populate_virtual_archive_node(
                    archive_node=archive_node,
                    members=members,
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                    read_member_bytes=read_member_bytes,
                )
                after_children = len(list(archive_node.get("children") or []))
                after_direct_images = int(archive_node.get("direct_images", 0) or 0)
                if (
                    after_children <= before_children
                    and after_direct_images <= before_direct_images
                    and len(members) > 0
                ):
                    warnings.append(
                        f"RAR 内文件未识别到可导入图片/压缩包: {archive_path.name}。"
                        "若为加密头或特殊封装，请安装支持密码读取的 unrar/7z 后重试。"
                    )
            return

        if suffix == ".7z":
            if py7zr is None:
                warnings.append(f"缺少 py7zr 依赖，无法解析: {archive_path.name}")
                return
            with py7zr.SevenZipFile(archive_path, "r", password=(archive_password or None)) as archive:
                members = [{"name": str(name or ""), "is_dir": str(name or "").endswith("/")} for name in archive.getnames()]
                self._populate_virtual_archive_node(
                    archive_node=archive_node,
                    members=members,
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                    read_member_bytes=None,
                )
            return

        warnings.append(f"不支持的压缩格式，已跳过: {archive_path.name}")

    def _scan_archive_bytes_into_virtual_node(
        self,
        archive_node: Dict[str, Any],
        archive_name: str,
        archive_bytes: bytes,
        *,
        source_path: str,
        top_archive_path: str,
        archive_chain: List[str],
        depth: int,
        archive_password: Optional[str],
        warnings: List[str],
    ) -> None:
        suffix = Path(str(archive_name or "")).suffix.lower()
        if suffix == ".zip":
            pwd_bytes = archive_password.encode("utf-8") if archive_password else None
            with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as zf:
                if pwd_bytes:
                    zf.setpassword(pwd_bytes)
                infos = [info for info in zf.infolist() if not stat.S_ISLNK(info.external_attr >> 16)]
                members = [{"name": str(info.filename or ""), "is_dir": bool(info.is_dir())} for info in infos]
                info_map = {str(info.filename or ""): info for info in infos}

                def read_member_bytes(name: str) -> bytes:
                    info = info_map[name]
                    if pwd_bytes:
                        with zf.open(info, "r", pwd=pwd_bytes) as src:
                            return src.read()
                    with zf.open(info, "r") as src:
                        return src.read()

                self._populate_virtual_archive_node(
                    archive_node=archive_node,
                    members=members,
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                    read_member_bytes=read_member_bytes,
                )
            return

        if suffix == ".rar":
            if rarfile is None:
                warnings.append(f"缺少 rarfile 依赖，无法解析: {archive_name}")
                return
            temp_path: Optional[str] = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".rar") as temp_file:
                    temp_file.write(archive_bytes)
                    temp_path = temp_file.name
                with rarfile.RarFile(temp_path) as rf:  # type: ignore[arg-type]
                    if archive_password and hasattr(rf, "setpassword"):
                        rf.setpassword(archive_password)
                    infos = list(rf.infolist())
                    if not infos and archive_password:
                        warnings.append(f"未能读取嵌套加密 RAR 目录结构，已跳过: {archive_name}")
                        return
                    members: List[Dict[str, Any]] = []
                    info_map: Dict[str, Any] = {}
                    for info in infos:
                        member_name = str(getattr(info, "filename", "") or "")
                        if not member_name:
                            continue
                        is_dir = False
                        if hasattr(info, "is_dir"):
                            is_dir = bool(info.is_dir())
                        elif hasattr(info, "isdir"):
                            is_dir = bool(info.isdir())
                        if hasattr(info, "is_symlink") and info.is_symlink():
                            continue
                        members.append({"name": member_name, "is_dir": is_dir})
                        info_map[member_name] = info

                    def read_member_bytes(name: str) -> bytes:
                        info = info_map[name]
                        kwargs: Dict[str, Any] = {}
                        if archive_password:
                            kwargs["pwd"] = archive_password
                        with rf.open(info, "r", **kwargs) as src:
                            return src.read()

                    self._populate_virtual_archive_node(
                        archive_node=archive_node,
                        members=members,
                        source_path=source_path,
                        top_archive_path=top_archive_path,
                        archive_chain=archive_chain,
                        depth=depth,
                        archive_password=archive_password,
                        warnings=warnings,
                        read_member_bytes=read_member_bytes,
                    )
            except Exception as exc:
                warnings.append(f"解析嵌套 RAR 失败，已跳过 {archive_name}: {exc}")
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
            return

        if suffix == ".7z":
            if py7zr is None:
                warnings.append(f"缺少 py7zr 依赖，无法解析: {archive_name}")
                return
            with py7zr.SevenZipFile(io.BytesIO(archive_bytes), "r", password=(archive_password or None)) as archive:
                members = [{"name": str(name or ""), "is_dir": str(name or "").endswith("/")} for name in archive.getnames()]
                self._populate_virtual_archive_node(
                    archive_node=archive_node,
                    members=members,
                    source_path=source_path,
                    top_archive_path=top_archive_path,
                    archive_chain=archive_chain,
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                    read_member_bytes=None,
                )
            return

        warnings.append(f"不支持的嵌套压缩格式，已跳过: {archive_name}")

    def _build_softref_tree(
        self,
        source: Path,
        archive_password: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], List[str]]:
        warnings: List[str] = []
        source_abs = str(source.resolve())
        root = self._new_virtual_node(
            node_id=".",
            display_name="根目录",
            real_name=str(source.name or "根目录"),
            abs_path=source_abs,
            parent_id=None,
        )

        def add_archive_from_path(parent: Dict[str, Any], archive_path: Path, *, depth: int) -> None:
            archive_name = archive_path.name
            display_name = self._strip_archive_suffix(archive_name) or archive_name
            archive_locator = self._make_archive_softref_locator(
                source_path=source_abs,
                top_archive_path=str(archive_path.resolve()),
                archive_chain=[],
                inner_path=".",
            )
            archive_node = self._ensure_virtual_dir_child(
                parent,
                display_name,
                archive_locator,
                allow_reuse=False,
            )
            try:
                self._scan_archive_path_into_virtual_node(
                    archive_node=archive_node,
                    archive_path=archive_path,
                    source_path=source_abs,
                    top_archive_path=str(archive_path.resolve()),
                    archive_chain=[],
                    depth=depth,
                    archive_password=archive_password,
                    warnings=warnings,
                )
            except Exception as exc:
                warnings.append(f"解析压缩包失败，已跳过 {archive_name}: {exc}")

        def walk_fs_dir(parent: Dict[str, Any], folder: Path, *, depth: int) -> None:
            if depth > MAX_NESTED_DEPTH:
                warnings.append(f"目录层级过深，已跳过: {folder}")
                return
            for entry in self._sorted_entries(list(folder.iterdir())):
                if entry.is_dir():
                    child = self._ensure_virtual_dir_child(parent, entry.name, str(entry.resolve()), allow_reuse=True)
                    walk_fs_dir(child, entry, depth=depth + 1)
                    continue
                if self._is_image(entry):
                    parent["direct_images"] = int(parent.get("direct_images", 0) or 0) + 1
                    continue
                if self._is_archive(entry):
                    add_archive_from_path(parent, entry, depth=depth + 1)
                    continue

        if source.is_dir():
            walk_fs_dir(root, source, depth=0)
        elif source.is_file():
            if self._is_image(source):
                root["direct_images"] = int(root.get("direct_images", 0) or 0) + 1
            elif self._is_archive(source):
                add_archive_from_path(root, source, depth=0)
            else:
                raise ValueError("给定路径不是可导入的图片/压缩包/文件夹")
        else:
            raise ValueError("给定路径不可读取")

        tree, node_map = self._finalize_virtual_tree(root)
        total_images = int(tree.get("total_images", 0) or 0)
        if total_images <= 0:
            if source.is_file() and source.suffix.lower() == ".rar":
                warnings.append(
                    "未在当前 RAR 中识别到可导入图片。"
                    "请确认压缩包内容和密码是否正确，或安装支持加密 RAR 的解包后端（unrar/7z）。"
                )
            else:
                warnings.append("未在给定路径中识别到可导入图片。")
        return tree, node_map, warnings

    def _extract_zip(self, archive_path: Path, dest_dir: Path, archive_password: Optional[str] = None) -> None:
        pwd_bytes = archive_password.encode("utf-8") if archive_password else None
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                target = self._safe_target_from_member(dest_dir, info.filename)
                if target is None:
                    continue
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                open_kwargs: Dict[str, Any] = {}
                if pwd_bytes:
                    open_kwargs["pwd"] = pwd_bytes
                with zf.open(info, "r", **open_kwargs) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    def _extract_rar(self, archive_path: Path, dest_dir: Path, archive_password: Optional[str] = None) -> None:
        if rarfile is None:
            raise RuntimeError("rarfile 未安装，无法处理 .rar")
        with rarfile.RarFile(archive_path) as rf:
            if archive_password and hasattr(rf, "setpassword"):
                rf.setpassword(archive_password)
            for info in rf.infolist():
                target = self._safe_target_from_member(dest_dir, info.filename)
                if target is None:
                    continue
                is_dir = False
                if hasattr(info, "is_dir"):
                    is_dir = bool(info.is_dir())
                elif hasattr(info, "isdir"):
                    is_dir = bool(info.isdir())
                if hasattr(info, "is_symlink") and info.is_symlink():
                    continue
                if is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                kwargs: Dict[str, Any] = {}
                if archive_password:
                    kwargs["pwd"] = archive_password
                with rf.open(info, "r", **kwargs) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    def _extract_7z(self, archive_path: Path, dest_dir: Path, archive_password: Optional[str] = None) -> None:
        if py7zr is None:
            raise RuntimeError("py7zr 未安装，无法处理 .7z")
        with py7zr.SevenZipFile(archive_path, "r", password=(archive_password or None)) as archive:
            for name in archive.getnames():
                if not self._is_safe_member_name(name):
                    raise ValueError(f"7z 包内包含非法路径: {name}")
            archive.extractall(path=dest_dir)

    def _extract_archive(self, archive_path: Path, dest_dir: Path, archive_password: Optional[str] = None) -> None:
        suffix = archive_path.suffix.lower()
        if suffix == ".zip":
            self._extract_zip(archive_path, dest_dir, archive_password=archive_password)
            return
        if suffix == ".rar":
            self._extract_rar(archive_path, dest_dir, archive_password=archive_password)
            return
        if suffix == ".7z":
            self._extract_7z(archive_path, dest_dir, archive_password=archive_password)
            return
        raise RuntimeError(f"不支持的压缩格式: {archive_path.suffix}")

    def _flatten_archive_directory(self, target_dir: Path) -> None:
        children = [child for child in target_dir.iterdir()]
        dirs = [child for child in children if child.is_dir()]
        files = [child for child in children if child.is_file()]
        if len(dirs) != 1 or files:
            return
        only_child = dirs[0]
        if self._normalize_name(only_child.name) != self._normalize_name(target_dir.name):
            return
        for item in self._sorted_entries(list(only_child.iterdir())):
            destination = self._make_unique_path(target_dir / item.name)
            shutil.move(str(item), str(destination))
        only_child.rmdir()

    def _prune_empty_directories(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        for child in list(path.iterdir()):
            if child.is_dir():
                self._prune_empty_directories(child)
        if any(path.iterdir()):
            return False
        path.rmdir()
        return True

    @staticmethod
    def _copy_upload_file(upload_file, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        upload_file.stream.seek(0)
        with open(target_path, "wb") as dst:
            shutil.copyfileobj(upload_file.stream, dst)

    def _normalize_to_clean_tree(
        self,
        input_root: Path,
        clean_root: Path,
        archive_password: Optional[str] = None,
    ) -> List[str]:
        warnings: List[str] = []
        scratch_root = input_root.parent / "scratch"
        scratch_root.mkdir(parents=True, exist_ok=True)

        def expand_entry(entry: Path, dst_parent: Path, depth: int, allow_archive_expand: bool = True) -> None:
            if depth > MAX_NESTED_DEPTH:
                warnings.append(f"嵌套层级过深，已跳过: {entry}")
                return

            if entry.is_dir():
                target_dir = self._make_unique_path(dst_parent / entry.name)
                target_dir.mkdir(parents=True, exist_ok=True)
                for child in self._sorted_entries(list(entry.iterdir())):
                    expand_entry(child, target_dir, depth + 1, allow_archive_expand=allow_archive_expand)
                self._prune_empty_directories(target_dir)
                return

            if self._is_image(entry):
                target_file = self._make_unique_path(dst_parent / entry.name)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, target_file)
                return

            if self._is_archive(entry):
                if not allow_archive_expand:
                    warnings.append(f"检测到内层压缩包，按导入规则已跳过: {entry.name}")
                    return
                target_dir = self._make_unique_path(dst_parent / self._strip_archive_suffix(entry.name))
                target_dir.mkdir(parents=True, exist_ok=True)
                temp_dir = scratch_root / f"extract_{uuid.uuid4().hex}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    self._extract_archive(entry, temp_dir, archive_password=archive_password)
                    for child in self._sorted_entries(list(temp_dir.iterdir())):
                        expand_entry(child, target_dir, depth + 1, allow_archive_expand=False)
                    self._flatten_archive_directory(target_dir)
                    self._prune_empty_directories(target_dir)
                except Exception as exc:
                    shutil.rmtree(target_dir, ignore_errors=True)
                    warnings.append(f"解压失败，已跳过 {entry.name}: {exc}")
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return

            warnings.append(f"跳过非图片/非压缩包文件: {entry.name}")

        clean_root.mkdir(parents=True, exist_ok=True)
        for child in self._sorted_entries(list(input_root.iterdir())):
            expand_entry(child, clean_root, 0, allow_archive_expand=True)

        for child in list(clean_root.iterdir()):
            if child.is_dir():
                self._prune_empty_directories(child)
        return warnings

    @staticmethod
    def _build_prepare_record_key(archive_path: Path) -> str:
        return os.path.normcase(os.path.abspath(str(archive_path)))

    def _scan_archives(self, root: Path) -> List[Path]:
        archives: List[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if self._is_archive(path):
                archives.append(path)
        return sorted(archives, key=lambda p: str(p).replace("\\", "/").lower())

    def _load_or_create_prepare_state(self, session_id: str) -> Dict[str, Any]:
        path = self._prepare_state_path(session_id)
        state = self._read_json(path, default=None)
        if not isinstance(state, dict):
            state = {
                "session_id": session_id,
                "status": "pending",
                "records": {},
                "created_at": self._timestamp(),
                "updated_at": self._timestamp(),
            }
            self._write_json(path, state)
        return state

    def _save_prepare_state(self, session_id: str, state: Dict[str, Any]) -> None:
        state["updated_at"] = self._timestamp()
        self._write_json(self._prepare_state_path(session_id), state)

    def _prepare_source_inplace(
        self,
        session_id: str,
        source_root: Path,
        archive_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not source_root.exists() or not source_root.is_dir():
            raise ValueError("仅支持文件夹启用超大文件移动导入")

        state = self._load_or_create_prepare_state(session_id)
        records = state.setdefault("records", {})
        state["status"] = "running"
        self._save_prepare_state(session_id, state)

        session_base = self._ensure_session_dir(session_id)
        scratch_root = session_base / "prepare_scratch"
        scratch_root.mkdir(parents=True, exist_ok=True)

        warning_set: set[str] = set()
        total_processed = 0

        completed_extract_roots: List[Path] = []
        for item in records.values():
            if str((item or {}).get("status", "")).lower() != "completed":
                continue
            extracted_dir_raw = str((item or {}).get("extracted_dir", "")).strip()
            if not extracted_dir_raw:
                continue
            extracted_dir = Path(extracted_dir_raw)
            if extracted_dir.exists() and extracted_dir.is_dir():
                completed_extract_roots.append(extracted_dir.resolve())

        archives = self._scan_archives(source_root)
        pending: List[Tuple[str, Path]] = []
        for archive_path in archives:
            abs_archive = archive_path.resolve()
            if any(abs_archive.is_relative_to(root) for root in completed_extract_roots):
                warning_set.add(f"检测到内层压缩包，按导入规则已跳过: {archive_path.name}")
                continue

            key = self._build_prepare_record_key(archive_path)
            record = records.get(key, {})
            if str(record.get("status", "")).lower() == "running":
                record["status"] = "pending"
            records[key] = record
            if str(record.get("status", "")).lower() != "completed":
                pending.append((key, archive_path))

        for key, archive_path in pending:
            if not archive_path.exists():
                continue
            total_processed += 1
            record = records.setdefault(key, {})
            record.update(
                {
                    "archive_path": str(archive_path),
                    "status": "running",
                    "updated_at": self._timestamp(),
                    "error": "",
                }
            )
            self._save_prepare_state(session_id, state)

            target_dir = self._make_unique_path(archive_path.parent / self._strip_archive_suffix(archive_path.name))
            temp_dir = scratch_root / f"extract_{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                self._extract_archive(archive_path, temp_dir, archive_password=archive_password)
                target_dir.mkdir(parents=True, exist_ok=True)
                for child in self._sorted_entries(list(temp_dir.iterdir())):
                    destination = self._make_unique_path(target_dir / child.name)
                    shutil.move(str(child), str(destination))
                self._flatten_archive_directory(target_dir)
                self._prune_empty_directories(target_dir)

                archive_path.unlink(missing_ok=True)
                record["status"] = "completed"
                record["error"] = ""
                record["extracted_dir"] = str(target_dir.resolve())
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                warning_set.add(f"解压失败，已跳过 {archive_path.name}: {exc}")
            finally:
                record["updated_at"] = self._timestamp()
                self._save_prepare_state(session_id, state)
                shutil.rmtree(temp_dir, ignore_errors=True)

        failed_count = 0
        for record in records.values():
            if str((record or {}).get("status", "")).lower() == "failed":
                failed_count += 1
                err = str((record or {}).get("error", "")).strip()
                archive_name = Path(str((record or {}).get("archive_path", "")).strip()).name
                if err and archive_name:
                    warning_set.add(f"解压失败，已跳过 {archive_name}: {err}")

        state["status"] = "failed" if failed_count > 0 else "completed"
        self._save_prepare_state(session_id, state)
        return {
            "status": state["status"],
            "processed_count": total_processed,
            "failed_count": failed_count,
            "warnings": sorted(warning_set),
        }

    def _count_direct_images(self, path: Path) -> int:
        total = 0
        for child in path.iterdir():
            if child.is_file() and self._is_image(child):
                total += 1
        return total

    def _build_tree(self, clean_root: Path) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        node_map: Dict[str, Dict[str, Any]] = {}

        def walk(path: Path, rel_id: str, parent_id: Optional[str]) -> Dict[str, Any]:
            children_nodes: List[Dict[str, Any]] = []
            child_ids: List[str] = []
            for child_dir in self._sorted_entries([child for child in path.iterdir() if child.is_dir()]):
                child_rel = child_dir.name if rel_id == "." else f"{rel_id}/{child_dir.name}"
                child_node = walk(child_dir, child_rel, rel_id)
                children_nodes.append(child_node)
                child_ids.append(child_rel)

            direct_images = self._count_direct_images(path)
            total_images = direct_images + sum(child["total_images"] for child in children_nodes)
            node = {
                "id": rel_id,
                "name": "根目录" if rel_id == "." else path.name,
                "real_name": path.name,
                "abs_path": str(path.resolve()),
                "rel_path": "." if rel_id == "." else rel_id,
                "direct_images": direct_images,
                "total_images": total_images,
                "children": children_nodes,
            }
            node_map[rel_id] = {
                "id": rel_id,
                "name": path.name if rel_id != "." else "根目录",
                "real_name": path.name,
                "abs_path": str(path.resolve()),
                "rel_path": "." if rel_id == "." else rel_id,
                "direct_images": direct_images,
                "total_images": total_images,
                "parent_id": parent_id,
                "child_ids": child_ids,
            }
            return node

        tree = walk(clean_root, ".", None)
        return tree, node_map

    def _build_node_map_from_tree(self, tree: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        if not isinstance(tree, dict):
            raise ValueError("会话目录树格式错误")

        node_map: Dict[str, Dict[str, Any]] = {}

        def walk(node: Dict[str, Any], parent_id: Optional[str]) -> None:
            node_id = str(node.get("id") or "")
            if not node_id:
                return
            children = list(node.get("children") or [])
            child_ids: List[str] = [str(child.get("id") or "") for child in children if str(child.get("id") or "")]
            node_map[node_id] = {
                "id": node_id,
                "name": str(node.get("name") or ""),
                "real_name": str(node.get("real_name") or node.get("name") or ""),
                "abs_path": str(node.get("abs_path") or ""),
                "rel_path": str(node.get("rel_path") or "."),
                "direct_images": int(node.get("direct_images", 0) or 0),
                "total_images": int(node.get("total_images", 0) or 0),
                "parent_id": parent_id,
                "child_ids": child_ids,
            }
            for child in children:
                walk(child, node_id)

        walk(tree, None)
        return node_map

    def _nearest_author_name(self, node_id: str, node_map: Dict[str, Dict[str, Any]], assignments: Dict[str, str]) -> str:
        current_id = node_map[node_id]["parent_id"]
        while current_id is not None:
            current_node = node_map[current_id]
            parent_id = current_node["parent_id"]
            if parent_id is not None and assignments.get(parent_id) == "author":
                return current_node["real_name"]
            current_id = parent_id
        return ""

    @staticmethod
    def _normalize_assignments(raw_assignments: Optional[Dict[str, str]]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in (raw_assignments or {}).items():
            role = str(value or "").strip().lower()
            if role not in {"author", "work"}:
                continue
            normalized[str(key)] = role
        return normalized

    @staticmethod
    def _normalize_tag_assignments(raw_tag_assignments: Optional[Any]) -> Dict[str, bool]:
        normalized: Dict[str, bool] = {}
        if isinstance(raw_tag_assignments, dict):
            for key, value in raw_tag_assignments.items():
                node_id = str(key or "").strip()
                if not node_id:
                    continue
                if value is None:
                    continue
                if isinstance(value, bool) and not value:
                    continue
                if isinstance(value, (int, float)) and value == 0:
                    continue
                if isinstance(value, str) and value.strip().lower() in {"", "0", "false", "none", "null"}:
                    continue
                normalized[node_id] = True
            return normalized

        if isinstance(raw_tag_assignments, (list, tuple, set)):
            for value in raw_tag_assignments:
                node_id = str(value or "").strip()
                if not node_id:
                    continue
                normalized[node_id] = True
        return normalized

    def _collect_parent_tag_names(
        self,
        node_id: str,
        node_map: Dict[str, Dict[str, Any]],
        tag_assignments: Dict[str, bool],
    ) -> List[str]:
        names: List[str] = []
        current_id: Optional[str] = node_id
        while current_id is not None and current_id in node_map:
            current_node = node_map[current_id]
            parent_id = current_node["parent_id"]
            if parent_id is not None and parent_id in tag_assignments:
                tag_name = str(current_node.get("real_name", "")).strip()
                if tag_name:
                    names.append(tag_name)
            current_id = parent_id

        names.reverse()
        result: List[str] = []
        seen: set[str] = set()
        for item in names:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def _build_export_payload_from_tree(
        self,
        tree: Dict[str, Any],
        node_map: Dict[str, Dict[str, Any]],
        assignments: Dict[str, str],
        tag_assignments: Optional[Dict[str, bool]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_tag_assignments = self._normalize_tag_assignments(tag_assignments)

        work_nodes: set[str] = set()
        for parent_id, role in assignments.items():
            if role != "work":
                continue
            parent_node = node_map.get(parent_id)
            if not parent_node:
                continue
            # 允许“目录自身即作品”（例如根目录下直接是图片，或该目录无子目录但有直图）
            if int(parent_node.get("direct_images", 0) or 0) > 0:
                work_nodes.add(parent_id)
            for child_id in parent_node["child_ids"]:
                work_nodes.add(child_id)

        ancestor_selected: set[str] = set()
        for node_id in work_nodes:
            parent_id = node_map[node_id]["parent_id"]
            while parent_id is not None:
                if parent_id in work_nodes:
                    ancestor_selected.add(parent_id)
                parent_id = node_map[parent_id]["parent_id"] if parent_id in node_map else None

        deepest_work_nodes = sorted(
            [node_id for node_id in work_nodes if node_id not in ancestor_selected],
            key=lambda node_id: str(node_map[node_id].get("abs_path", "")),
        )

        payload: List[Dict[str, Any]] = []
        for node_id in deepest_work_nodes:
            node = node_map[node_id]
            payload.append(
                {
                    "作者名称": self._nearest_author_name(node_id, node_map, assignments),
                    "作品名称": node["real_name"],
                    "作品文件地址": node["abs_path"],
                    "图片数量": int(node.get("total_images", 0) or 0),
                    "标签名称列表": self._collect_parent_tag_names(node_id, node_map, normalized_tag_assignments),
                }
            )
        return payload

    def _build_export_payload(
        self,
        clean_root: Path,
        assignments: Dict[str, str],
        tag_assignments: Optional[Dict[str, bool]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        tree, node_map = self._build_tree(clean_root)
        payload = self._build_export_payload_from_tree(tree, node_map, assignments, tag_assignments)
        return payload, tree, node_map

    def _create_empty_session(self) -> Tuple[str, Path, Path, Path]:
        session_id = uuid.uuid4().hex
        base = self._session_dir(session_id)
        input_root = base / "input"
        clean_root = base / "clean"
        input_root.mkdir(parents=True, exist_ok=True)
        clean_root.mkdir(parents=True, exist_ok=True)
        return session_id, base, input_root, clean_root

    def _finalize_session(
        self,
        session_id: str,
        clean_root: Path,
        warnings: List[str],
        meta_updates: Optional[Dict[str, Any]] = None,
        tree_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if tree_override is None:
            tree, _ = self._build_tree(clean_root)
        else:
            tree = tree_override
        payload = {
            "session_id": session_id,
            "tree": tree,
            "warnings": warnings,
            "clean_root": str(clean_root.resolve()),
        }
        self._write_json(self._tree_path(session_id), payload)
        existing_meta = self._load_meta(session_id)
        next_meta = {
            "session_id": session_id,
            "clean_root": str(clean_root.resolve()),
            "warnings": warnings,
            "saved_assignments": existing_meta.get("saved_assignments", {}) or {},
            "saved_tag_assignments": existing_meta.get("saved_tag_assignments", {}) or {},
            "phase": SESSION_PHASE_READY,
            "created_at": existing_meta.get("created_at", self._timestamp()),
        }
        if meta_updates:
            next_meta.update(meta_updates)
        next_meta["updated_at"] = self._timestamp()
        self._write_json(self._meta_path(session_id), next_meta)
        return self._attach_meta_to_tree_payload(session_id, payload)

    def _save_assignments_to_meta(
        self,
        session_id: str,
        assignments: Dict[str, str],
        tag_assignments: Optional[Dict[str, bool]] = None,
    ) -> None:
        meta_file = self._meta_path(session_id)
        meta = self._read_json(meta_file, default={}) or {}
        meta["saved_assignments"] = dict(assignments or {})
        if tag_assignments is None:
            meta["saved_tag_assignments"] = self._normalize_tag_assignments(meta.get("saved_tag_assignments", {}))
        else:
            meta["saved_tag_assignments"] = dict(self._normalize_tag_assignments(tag_assignments))
        meta["updated_at"] = self._timestamp()
        self._write_json(meta_file, meta)

    def _load_clean_root(self, session_id: str) -> Path:
        self._ensure_session_dir(session_id)
        meta = self._read_json(self._meta_path(session_id), default={}) or {}
        clean_root = Path(str(meta.get("clean_root", "")).strip())
        if not clean_root.exists():
            raise ValueError("清洗后的目录不存在")
        return clean_root

    def _load_session_tree_and_node_map(self, session_id: str) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
        self._ensure_session_dir(session_id)
        payload = self._read_json(self._tree_path(session_id), default=None)
        if not isinstance(payload, dict):
            raise ValueError("会话目录树不存在")
        tree = payload.get("tree")
        if not isinstance(tree, dict):
            raise ValueError("会话目录树格式错误")
        node_map = self._build_node_map_from_tree(tree)
        return tree, node_map

    def _build_session_export_payload(
        self,
        session_id: str,
        assignments: Dict[str, str],
        tag_assignments: Optional[Dict[str, bool]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        meta = self._load_meta(session_id)
        effective_mode = self._normalize_import_mode(meta.get("effective_mode", IMPORT_MODE_COPY_SAFE))
        if effective_mode == IMPORT_MODE_SOFTLINK_REF:
            tree, node_map = self._load_session_tree_and_node_map(session_id)
            items = self._build_export_payload_from_tree(tree, node_map, assignments, tag_assignments)
            return items, tree, node_map

        clean_root = self._load_clean_root(session_id)
        return self._build_export_payload(clean_root, assignments, tag_assignments)

    def _attach_meta_to_tree_payload(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        meta = self._load_meta(session_id)
        data = dict(payload or {})
        data["saved_assignments"] = self._normalize_assignments(meta.get("saved_assignments", {}))
        data["saved_tag_assignments"] = self._normalize_tag_assignments(meta.get("saved_tag_assignments", {}))
        data["import_mode"] = str(meta.get("import_mode", IMPORT_MODE_COPY_SAFE))
        data["effective_mode"] = str(meta.get("effective_mode", IMPORT_MODE_COPY_SAFE))
        data["phase"] = str(meta.get("phase", ""))
        return data

    def create_session_from_path(
        self,
        source_path: str,
        import_mode: str = IMPORT_MODE_COPY_SAFE,
        archive_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        source = self._normalize_source_path_input(source_path)
        raw_mode = str(import_mode or "").strip().lower()
        mode = self._normalize_import_mode(raw_mode)
        display_mode = IMPORT_MODE_HARDLINK_MOVE if raw_mode == IMPORT_MODE_HARDLINK_MOVE else mode
        archive_password = str(archive_password or "").strip() or None
        if not source.exists():
            raise ValueError(
                "给定路径不存在。请注意：路径必须是服务器所在设备可访问的本机路径；"
                "若你在局域网其他设备访问本服务，不能直接使用你那台设备的本地路径。"
            )

        session_id, _base, input_root, clean_root = self._create_empty_session()
        session_meta = {
            "session_id": session_id,
            "source_path": str(source),
            "import_mode": display_mode,
            "effective_mode": mode,
            "archive_password": archive_password or "",
            "phase": SESSION_PHASE_PREPARING,
            "created_at": self._timestamp(),
            "saved_assignments": {},
            "saved_tag_assignments": {},
            "warnings": [],
        }
        self._write_json(self._meta_path(session_id), session_meta)

        target = input_root / source.name
        warnings: List[str] = []
        try:
            if mode == IMPORT_MODE_SOFTLINK_REF:
                tree, _node_map, soft_warnings = self._build_softref_tree(source, archive_password=archive_password)
                warnings.extend(soft_warnings)
                response = self._finalize_session(
                    session_id,
                    source,
                    warnings,
                    meta_updates={
                        "import_mode": display_mode,
                        "effective_mode": mode,
                        "source_path": str(source),
                        "archive_password": archive_password or "",
                    },
                    tree_override=tree,
                )
                app_logger.info(f"本地导入解析会话创建成功(path-softref): {session_id}")
                return response

            effective_mode = mode
            if mode == IMPORT_MODE_MOVE_HUGE:
                if not source.is_dir():
                    raise ValueError("超大文件移动导入仅支持文件夹路径")

                local_root = Path(LOCAL_PICTURES_DIR)
                if not self._is_same_filesystem(source, local_root):
                    effective_mode = IMPORT_MODE_COPY_SAFE
                    warnings.append(
                        "检测到源目录与本地图库目录不在同一磁盘，无法原地移动导入；已自动降级为复制导入。"
                    )

            self._update_meta(
                session_id,
                {
                    "effective_mode": effective_mode,
                    "phase": SESSION_PHASE_PREPARING,
                },
            )

            if effective_mode == IMPORT_MODE_MOVE_HUGE:
                prepare_result = self._prepare_source_inplace(
                    session_id,
                    source,
                    archive_password=archive_password,
                )
                warnings.extend(prepare_result.get("warnings", []))
                response = self._finalize_session(
                    session_id,
                    source,
                    warnings,
                    meta_updates={
                        "import_mode": display_mode,
                        "effective_mode": effective_mode,
                        "source_path": str(source),
                        "prepare_status": prepare_result.get("status", "completed"),
                        "archive_password": archive_password or "",
                    },
                )
                app_logger.info(f"本地导入解析会话创建成功(path-move): {session_id}")
                return response

            if source.is_dir():
                shutil.copytree(source, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            warnings.extend(
                self._normalize_to_clean_tree(
                    input_root,
                    clean_root,
                    archive_password=archive_password,
                )
            )
            response = self._finalize_session(
                session_id,
                clean_root,
                warnings,
                meta_updates={
                    "import_mode": display_mode,
                    "effective_mode": effective_mode,
                    "source_path": str(source),
                    "archive_password": archive_password or "",
                },
            )
            app_logger.info(f"本地导入解析会话创建成功(path): {session_id}")
            return response
        except Exception:
            # 保留 move_huge 会话用于恢复；copy 模式沿用原行为清理脏会话。
            try:
                meta = self._load_meta(session_id)
                keep_session = str(meta.get("effective_mode", "")) == IMPORT_MODE_MOVE_HUGE
            except Exception:
                keep_session = False

            if keep_session:
                self._update_meta(
                    session_id,
                    {
                        "phase": SESSION_PHASE_FAILED,
                        "error": "会话准备阶段中断，可继续恢复",
                        "warnings": warnings,
                    },
                )
            else:
                shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
            raise

    def create_session_from_upload(self, files: List[Any], relative_paths: List[str]) -> Dict[str, Any]:
        if not files:
            raise ValueError("没有上传文件")
        if len(files) != len(relative_paths):
            raise ValueError("上传文件与相对路径数量不一致")

        session_id, _base, input_root, clean_root = self._create_empty_session()
        self._write_json(
            self._meta_path(session_id),
            {
                "session_id": session_id,
                "import_mode": IMPORT_MODE_COPY_SAFE,
                "effective_mode": IMPORT_MODE_COPY_SAFE,
                "phase": SESSION_PHASE_PREPARING,
                "created_at": self._timestamp(),
                "saved_assignments": {},
                "saved_tag_assignments": {},
                "warnings": [],
            },
        )

        try:
            for upload_file, rel_path in zip(files, relative_paths):
                normalized = str(rel_path or "").replace("\\", "/")
                target = self._safe_target_from_member(input_root, normalized)
                if target is None:
                    continue
                self._copy_upload_file(upload_file, target)

            warnings = self._normalize_to_clean_tree(input_root, clean_root)
            response = self._finalize_session(
                session_id,
                clean_root,
                warnings,
                meta_updates={
                    "import_mode": IMPORT_MODE_COPY_SAFE,
                    "effective_mode": IMPORT_MODE_COPY_SAFE,
                },
            )
            app_logger.info(f"本地导入解析会话创建成功(upload): {session_id}")
            return response
        except Exception:
            shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
            raise

    def get_session_tree(self, session_id: str) -> Dict[str, Any]:
        self._ensure_session_dir(session_id)
        data = self._read_json(self._tree_path(session_id), default=None)
        if not data:
            raise ValueError("目录树不存在")
        return self._attach_meta_to_tree_payload(session_id, data)

    def export_session_items(
        self,
        session_id: str,
        raw_assignments: Dict[str, str],
        raw_tag_assignments: Optional[Any] = None,
    ) -> Dict[str, Any]:
        meta = self._load_meta(session_id)
        assignments = self._normalize_assignments(raw_assignments)
        if raw_tag_assignments is None:
            tag_assignments = self._normalize_tag_assignments(meta.get("saved_tag_assignments", {}))
            self._save_assignments_to_meta(session_id, assignments, None)
        else:
            tag_assignments = self._normalize_tag_assignments(raw_tag_assignments)
            self._save_assignments_to_meta(session_id, assignments, tag_assignments)

        items, tree, _node_map = self._build_session_export_payload(session_id, assignments, tag_assignments)
        self._write_json(self._result_path(session_id), items)
        return {
            "session_id": session_id,
            "items": items,
            "count": len(items),
            "download_url": f"/api/v1/comic/batch-upload/session/{session_id}/result.json",
            "tree": tree,
        }

    @staticmethod
    def _normalize_existing_source(raw_source: str) -> str:
        normalized = str(raw_source or "").strip()
        if normalized.startswith("softref://"):
            return normalized
        return os.path.normcase(os.path.abspath(normalized))

    def _build_local_comic_id(self, work_path: str, existing_ids: set[str]) -> str:
        normalized = self._normalize_existing_source(work_path)
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12].upper()
        base_id = f"LOCAL{digest}"
        if base_id not in existing_ids:
            return base_id
        suffix = 2
        while f"{base_id}_{suffix}" in existing_ids:
            suffix += 1
        return f"{base_id}_{suffix}"

    @staticmethod
    def _next_tag_id_from_items(tags: List[Dict[str, Any]]) -> str:
        max_tag_num = 0
        for tag in tags:
            tag_id = str((tag or {}).get("id", ""))
            if not tag_id.startswith("tag_"):
                continue
            try:
                max_tag_num = max(max_tag_num, int(tag_id[4:]))
            except Exception:
                continue
        return f"tag_{max_tag_num + 1:03d}"

    def _ensure_local_tag_id(self) -> str:
        result = {"tag_id": ""}

        def updater(data: Dict[str, Any]) -> Dict[str, Any]:
            tags = data.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            for item in tags:
                if not isinstance(item, dict):
                    continue
                content_type = str(item.get("content_type", "comic")).strip().lower() or "comic"
                if content_type != "comic":
                    continue
                if str(item.get("name", "")).strip() != LOCAL_IMPORT_TAG_NAME:
                    continue
                tag_id = str(item.get("id", "")).strip()
                if tag_id:
                    result["tag_id"] = tag_id
                    data["tags"] = tags
                    return data

            new_tag_id = self._next_tag_id_from_items(tags)
            tags.append(
                {
                    "id": new_tag_id,
                    "name": LOCAL_IMPORT_TAG_NAME,
                    "content_type": "comic",
                    "create_time": self._timestamp(),
                }
            )
            data["tags"] = tags
            data["last_updated"] = time.strftime("%Y-%m-%d")
            result["tag_id"] = new_tag_id
            return data

        ok = self._tag_storage.atomic_update(updater)
        if not ok or not result["tag_id"]:
            raise RuntimeError("创建/查询本地标签失败")
        return result["tag_id"]

    def _ensure_comic_tag_ids(self, raw_tag_names: List[str]) -> Dict[str, str]:
        tag_names: List[str] = []
        seen: set[str] = set()
        for raw_name in raw_tag_names:
            name = str(raw_name or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            tag_names.append(name)
        if not tag_names:
            return {}

        result: Dict[str, str] = {}

        def updater(data: Dict[str, Any]) -> Dict[str, Any]:
            tags = data.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            existing_map: Dict[str, str] = {}
            for item in tags:
                if not isinstance(item, dict):
                    continue
                content_type = str(item.get("content_type", "comic")).strip().lower() or "comic"
                if content_type != "comic":
                    continue
                name = str(item.get("name", "")).strip()
                tag_id = str(item.get("id", "")).strip()
                if not name or not tag_id:
                    continue
                if name not in existing_map:
                    existing_map[name] = tag_id

            changed = False
            for name in tag_names:
                if name in existing_map:
                    result[name] = existing_map[name]
                    continue

                tag_id = self._next_tag_id_from_items(tags)
                tags.append(
                    {
                        "id": tag_id,
                        "name": name,
                        "content_type": "comic",
                        "create_time": self._timestamp(),
                    }
                )
                existing_map[name] = tag_id
                result[name] = tag_id
                changed = True

            data["tags"] = tags
            if changed:
                data["last_updated"] = time.strftime("%Y-%m-%d")
            return data

        ok = self._tag_storage.atomic_update(updater)
        if not ok:
            raise RuntimeError("创建/查询漫画标签失败")
        for name in tag_names:
            if name not in result:
                raise RuntimeError(f"创建/查询漫画标签失败: {name}")
        return result

    def _ensure_comic_has_tags(self, comic_id: str, raw_tag_ids: List[str]) -> bool:
        normalized_tag_ids: List[str] = []
        seen: set[str] = set()
        for raw_tag_id in raw_tag_ids:
            tag_id = str(raw_tag_id or "").strip()
            if not tag_id or tag_id in seen:
                continue
            seen.add(tag_id)
            normalized_tag_ids.append(tag_id)

        if not normalized_tag_ids:
            return False

        status = {"updated": False}

        def updater(data: Dict[str, Any]) -> Dict[str, Any]:
            comics = data.get("comics", [])
            if not isinstance(comics, list):
                comics = []
            for comic in comics:
                if not isinstance(comic, dict):
                    continue
                if str(comic.get("id", "")) != comic_id:
                    continue
                tag_ids = comic.get("tag_ids", [])
                if not isinstance(tag_ids, list):
                    tag_ids = []
                changed = False
                for tag_id in normalized_tag_ids:
                    if tag_id in tag_ids:
                        continue
                    tag_ids.append(tag_id)
                    changed = True
                if changed:
                    comic["tag_ids"] = tag_ids
                    status["updated"] = True
                    data["last_updated"] = time.strftime("%Y-%m-%d")
                break
            data["comics"] = comics
            return data

        ok = self._db_storage.atomic_update(updater)
        return bool(ok and status["updated"])

    def _ensure_comic_has_tag(self, comic_id: str, tag_id: str) -> bool:
        return self._ensure_comic_has_tags(comic_id, [tag_id])

    @staticmethod
    def _normalize_entry_tag_names(raw_names: Any) -> List[str]:
        values: List[str] = []
        if isinstance(raw_names, str):
            values = [raw_names]
        elif isinstance(raw_names, (list, tuple, set)):
            values = [str(item) for item in raw_names]
        else:
            return []

        normalized: List[str] = []
        seen: set[str] = set()
        for item in values:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            normalized.append(name)
        return normalized

    @staticmethod
    def _iter_image_files(root: Path) -> List[Path]:
        files: List[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(path)
        return sorted(
            files,
            key=lambda p: LocalComicImportService._natural_sort_key(str(p).replace("\\", "/")),
        )

    def _copy_work_to_staging(self, work_dir: Path, staging_dir: Path) -> int:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        images = self._iter_image_files(work_dir)
        for source in images:
            relative = source.relative_to(work_dir)
            target = staging_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return len(images)

    def _move_work_to_target(self, work_dir: Path, target_dir: Path) -> None:
        if not work_dir.exists() or not work_dir.is_dir():
            raise RuntimeError("作品目录不存在，可能已被删除")
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work_dir), str(target_dir))

    def _append_comic_record(self, comic_record: Dict[str, Any]) -> Tuple[bool, bool]:
        status = {"inserted": False, "exists": False}

        def updater(data: Dict[str, Any]) -> Dict[str, Any]:
            comics = data.setdefault("comics", [])
            for item in comics:
                if str(item.get("id", "")) == comic_record["id"]:
                    status["exists"] = True
                    return data
            comics.append(comic_record)
            data["total_comics"] = len(comics)
            data["last_updated"] = time.strftime("%Y-%m-%d")
            status["inserted"] = True
            return data

        ok = self._db_storage.atomic_update(updater)
        return ok, bool(status["inserted"])

    def _load_or_create_state(self, session_id: str, total_items: int) -> Dict[str, Any]:
        state_path = self._state_path(session_id)
        state = self._read_json(state_path, default=None)
        if not isinstance(state, dict):
            state = {
                "session_id": session_id,
                "status": "pending",
                "total_items": total_items,
                "records": {},
                "created_at": self._timestamp(),
                "updated_at": self._timestamp(),
            }
            self._write_json(state_path, state)
        return state

    def _save_state(self, session_id: str, state: Dict[str, Any]) -> None:
        state["updated_at"] = self._timestamp()
        self._write_json(self._state_path(session_id), state)

    def _summarize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        records = state.get("records", {}) or {}
        imported_count = 0
        skipped_count = 0
        failed_count = 0
        failed_items: List[Dict[str, str]] = []
        for item in records.values():
            item_status = str((item or {}).get("status", "")).strip().lower()
            if item_status == "completed":
                imported_count += 1
            elif item_status == "skipped":
                skipped_count += 1
            elif item_status == "failed":
                failed_count += 1
                failed_items.append(
                    {
                        "作品名称": str(item.get("title") or ""),
                        "作品文件地址": str(item.get("work_path") or ""),
                        "error": str(item.get("error") or "导入失败"),
                    }
                )
        return {
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "failed_items": failed_items,
        }

    def commit_session_import(
        self,
        session_id: str,
        raw_assignments: Optional[Dict[str, str]] = None,
        raw_tag_assignments: Optional[Any] = None,
    ) -> Dict[str, Any]:
        meta = self._load_meta(session_id)
        effective_mode = self._normalize_import_mode(meta.get("effective_mode", IMPORT_MODE_COPY_SAFE))
        archive_password = str(meta.get("archive_password", "") or "").strip() or None

        assignments = self._normalize_assignments(raw_assignments)
        if not assignments:
            assignments = self._normalize_assignments(meta.get("saved_assignments", {}))
        if not assignments:
            raise ValueError("请先完成层级标记")

        tag_assignments = self._normalize_tag_assignments(raw_tag_assignments)
        if raw_tag_assignments is None:
            tag_assignments = self._normalize_tag_assignments(meta.get("saved_tag_assignments", {}))

        self._save_assignments_to_meta(session_id, assignments, tag_assignments)

        existing_result_items = self._read_json(self._result_path(session_id), default=None)
        computed_items, _tree, _node_map = self._build_session_export_payload(session_id, assignments, tag_assignments)
        items = computed_items
        if (
            effective_mode == IMPORT_MODE_MOVE_HUGE
            and isinstance(existing_result_items, list)
            and len(existing_result_items) > 0
            and len(computed_items) < len(existing_result_items)
        ):
            # move 模式会改变源目录结构，恢复时优先沿用首轮解析结果继续补偿导入。
            items = existing_result_items

        self._write_json(self._result_path(session_id), items)

        state = self._load_or_create_state(session_id, total_items=len(items))
        state["status"] = "running"
        self._save_state(session_id, state)
        self._update_meta(
            session_id,
            {
                "phase": SESSION_PHASE_COMMITTING,
                "effective_mode": effective_mode,
            },
        )

        local_tag_id = self._ensure_local_tag_id() if items else ""
        all_tag_names: List[str] = []
        for entry in items:
            all_tag_names.extend(self._normalize_entry_tag_names(entry.get("标签名称列表")))
        tag_id_map = self._ensure_comic_tag_ids(all_tag_names) if all_tag_names else {}

        db_data = self._db_storage.read()
        comics = db_data.get("comics", [])
        existing_ids = {str(item.get("id", "")) for item in comics if str(item.get("id", "")).strip()}
        existing_source_map = {
            self._normalize_existing_source(str(item.get("import_source", ""))): str(item.get("id", ""))
            for item in comics
            if str(item.get("import_source", "")).strip()
        }

        session_base = self._ensure_session_dir(session_id)
        staging_root = session_base / "commit_staging"
        staging_root.mkdir(parents=True, exist_ok=True)

        records = state.setdefault("records", {})

        for entry in items:
            work_path = str(entry.get("作品文件地址") or "").strip()
            key = self._normalize_existing_source(work_path)
            if not key:
                continue

            record = records.get(key, {})
            if str(record.get("status", "")).lower() in {"completed", "skipped"}:
                continue

            title = str(entry.get("作品名称") or "").strip() or Path(work_path).name
            author = str(entry.get("作者名称") or "").strip()
            tag_names = self._normalize_entry_tag_names(entry.get("标签名称列表"))
            selected_tag_ids = [tag_id_map[name] for name in tag_names if name in tag_id_map]
            target_tag_ids: List[str] = []
            if local_tag_id:
                target_tag_ids.append(local_tag_id)
            for tag_id in selected_tag_ids:
                if tag_id not in target_tag_ids:
                    target_tag_ids.append(tag_id)
            record.update(
                {
                    "status": "running",
                    "title": title,
                    "author": author,
                    "work_path": work_path,
                    "tag_names": tag_names,
                    "tag_ids": target_tag_ids,
                    "updated_at": self._timestamp(),
                }
            )
            records[key] = record
            self._save_state(session_id, state)

            try:
                if key in existing_source_map:
                    if effective_mode == IMPORT_MODE_SOFTLINK_REF and archive_password and self._is_softref_locator(work_path):
                        self._remember_softref_archive_password(work_path, archive_password)
                    record["status"] = "skipped"
                    record["comic_id"] = existing_source_map[key]
                    if target_tag_ids:
                        self._ensure_comic_has_tags(record["comic_id"], target_tag_ids)
                    record["error"] = ""
                    record["updated_at"] = self._timestamp()
                    self._save_state(session_id, state)
                    continue

                comic_id = str(record.get("comic_id", "")).strip()
                if not comic_id:
                    comic_id = self._build_local_comic_id(work_path, existing_ids)
                    record["comic_id"] = comic_id

                original_id = comic_id[len("JM"):] if comic_id.startswith("JM") else comic_id
                page_count = int(entry.get("图片数量", 0) or 0)
                cover_path = "/static/default/default_cover.jpg"

                if effective_mode == IMPORT_MODE_SOFTLINK_REF:
                    if page_count <= 0:
                        raise RuntimeError("作品中没有可导入图片")
                    # 软连接模式不拷贝数据，封面使用首图接口兜底，避免依赖缺失的默认封面文件。
                    cover_path = f"/api/v1/comic/image?comic_id={comic_id}&page_num=1"
                    record["data_moved"] = False
                    self._save_state(session_id, state)
                else:
                    target_dir = Path(LOCAL_PICTURES_DIR) / original_id
                    moved_flag = bool(record.get("data_moved", False))
                    work_dir = Path(work_path)
                    if effective_mode == IMPORT_MODE_MOVE_HUGE:
                        if not moved_flag:
                            if not work_dir.exists() or not work_dir.is_dir():
                                raise RuntimeError("作品目录不存在，可能已被删除")
                            self._move_work_to_target(work_dir, target_dir)
                            record["data_moved"] = True
                            moved_flag = True
                            self._save_state(session_id, state)
                    else:
                        if not work_dir.exists() or not work_dir.is_dir():
                            raise RuntimeError("作品目录不存在，可能已被删除")
                        staging_dir = staging_root / original_id
                        copied_count = self._copy_work_to_staging(work_dir, staging_dir)
                        if copied_count <= 0:
                            raise RuntimeError("作品目录中没有可导入图片")
                        if target_dir.exists():
                            shutil.rmtree(target_dir, ignore_errors=True)
                        target_dir.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(staging_dir), str(target_dir))
                        moved_flag = True
                        record["data_moved"] = True
                        self._save_state(session_id, state)

                    if not target_dir.exists() or not target_dir.is_dir():
                        raise RuntimeError("目标作品目录不存在，导入过程可能被中断")

                    image_paths = file_parser.parse_comic_images(comic_id)
                    if not image_paths:
                        raise RuntimeError("导入后未检测到可读图片")
                    page_count = len(image_paths)
                    cover_path = image_handler.generate_cover(comic_id, image_paths[0])
                    if not cover_path or cover_path == "/static/default/default_cover.jpg":
                        cover_path = f"/api/v1/comic/image?comic_id={comic_id}&page_num=1"

                now = self._timestamp()
                comic_record = {
                    "id": comic_id,
                    "title": title,
                    "title_jp": "",
                    "author": author,
                    "desc": "",
                    "cover_path": cover_path,
                    "total_page": page_count,
                    "current_page": 1,
                    "score": 8.0,
                    "tag_ids": target_tag_ids,
                    "list_ids": [],
                    "create_time": now,
                    "last_read_time": now,
                    "is_deleted": False,
                    "import_source": work_path,
                }
                if effective_mode == IMPORT_MODE_SOFTLINK_REF:
                    comic_record["storage_mode"] = "soft_ref"
                    comic_record["soft_ref_locator"] = work_path

                ok, inserted = self._append_comic_record(comic_record)
                if not ok:
                    raise RuntimeError("写入漫画数据库失败")
                if effective_mode == IMPORT_MODE_SOFTLINK_REF and archive_password and self._is_softref_locator(work_path):
                    self._remember_softref_archive_password(work_path, archive_password)
                if not inserted and target_tag_ids:
                    self._ensure_comic_has_tags(comic_id, target_tag_ids)

                existing_ids.add(comic_id)
                existing_source_map[key] = comic_id
                record["status"] = "completed" if inserted else "skipped"
                record["error"] = ""
                record["effective_mode"] = effective_mode
                record["updated_at"] = self._timestamp()
                self._save_state(session_id, state)
            except Exception as exc:
                record["status"] = "failed"
                record["error"] = str(exc)
                record["updated_at"] = self._timestamp()
                self._save_state(session_id, state)

        summary = self._summarize_state(state)
        has_failed = summary["failed_count"] > 0
        state["status"] = "failed" if has_failed else "completed"
        self._save_state(session_id, state)
        self._update_meta(
            session_id,
            {
                "phase": SESSION_PHASE_FAILED if has_failed else SESSION_PHASE_COMPLETED,
            },
        )

        session_removed = False
        if not has_failed:
            try:
                shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
                session_removed = True
            except Exception:
                session_removed = False

        return {
            "session_id": session_id,
            "status": state["status"],
            "total_count": len(items),
            "session_removed": session_removed,
            **summary,
        }

    def list_recoverable_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []
        if not LOCAL_IMPORT_WORKSPACE_DIR.exists():
            return sessions

        for session_dir in LOCAL_IMPORT_WORKSPACE_DIR.iterdir():
            if not session_dir.is_dir():
                continue
            session_id = session_dir.name
            meta = self._load_meta(session_id)
            if not meta:
                continue
            phase = str(meta.get("phase", "")).strip().lower()
            if phase not in {
                SESSION_PHASE_PREPARING,
                SESSION_PHASE_READY,
                SESSION_PHASE_COMMITTING,
                SESSION_PHASE_FAILED,
            }:
                continue
            sessions.append(
                {
                    "session_id": session_id,
                    "phase": phase,
                    "import_mode": str(meta.get("import_mode", IMPORT_MODE_COPY_SAFE)),
                    "effective_mode": str(meta.get("effective_mode", IMPORT_MODE_COPY_SAFE)),
                    "source_path": str(meta.get("source_path", "")),
                    "updated_at": str(meta.get("updated_at", meta.get("created_at", ""))),
                    "warnings": list(meta.get("warnings", []) or []),
                }
            )

        sessions.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return sessions[: max(1, int(limit or 20))]

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        self._ensure_session_dir(session_id)
        meta = self._load_meta(session_id)
        if not meta:
            raise ValueError("会话元数据不存在")

        phase = str(meta.get("phase", "")).strip().lower()
        clean_root_raw = str(meta.get("clean_root", "")).strip()
        warnings = list(meta.get("warnings", []) or [])

        if phase == SESSION_PHASE_PREPARING and str(meta.get("effective_mode", "")) == IMPORT_MODE_MOVE_HUGE:
            source_path = str(meta.get("source_path", "")).strip()
            if not source_path:
                raise ValueError("缺少源路径，无法恢复会话")
            source_root = Path(source_path)
            if not source_root.exists() or not source_root.is_dir():
                raise ValueError("源目录不存在，无法恢复会话")
            prepare_result = self._prepare_source_inplace(
                session_id,
                source_root,
                archive_password=str(meta.get("archive_password", "") or "").strip() or None,
            )
            warnings.extend(prepare_result.get("warnings", []))
            payload = self._finalize_session(
                session_id,
                source_root,
                warnings,
                meta_updates={
                    "source_path": source_path,
                    "import_mode": str(meta.get("import_mode", IMPORT_MODE_COPY_SAFE)),
                    "effective_mode": str(meta.get("effective_mode", IMPORT_MODE_MOVE_HUGE)),
                    "prepare_status": prepare_result.get("status", "completed"),
                },
            )
            return payload

        tree = self._read_json(self._tree_path(session_id), default=None)
        if tree:
            return self.get_session_tree(session_id)

        if clean_root_raw:
            clean_root = Path(clean_root_raw)
            if clean_root.exists():
                return self._finalize_session(
                    session_id,
                    clean_root,
                    warnings,
                    meta_updates={
                        "import_mode": str(meta.get("import_mode", IMPORT_MODE_COPY_SAFE)),
                        "effective_mode": str(meta.get("effective_mode", IMPORT_MODE_COPY_SAFE)),
                    },
                )

        raise ValueError("当前会话不可恢复")

    def get_result_file_path(self, session_id: str) -> Path:
        self._ensure_session_dir(session_id)
        path = self._result_path(session_id)
        if not path.exists():
            raise ValueError("请先生成 JSON")
        return path

    def clear_session(self, session_id: str) -> None:
        path = self._ensure_session_dir(session_id)
        shutil.rmtree(path, ignore_errors=True)


local_comic_import_service = LocalComicImportService()

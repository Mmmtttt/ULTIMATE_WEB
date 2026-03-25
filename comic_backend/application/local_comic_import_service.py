from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from core.constants import CACHE_ROOT_DIR, LOCAL_PICTURES_DIR, SUPPORTED_FORMATS, TAGS_JSON_FILE
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
LOCAL_IMPORT_TAG_NAME = "本地"

LOCAL_IMPORT_WORKSPACE_DIR = Path(CACHE_ROOT_DIR) / "comic_local_import_workspace"
LOCAL_IMPORT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


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

    def _ensure_session_dir(self, session_id: str) -> Path:
        path = self._session_dir(session_id)
        if not path.exists():
            raise ValueError("会话不存在或已失效")
        return path

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _is_image(path: Path) -> bool:
        return path.suffix.lower() in IMAGE_EXTENSIONS

    @staticmethod
    def _is_archive(path: Path) -> bool:
        return path.suffix.lower() in ARCHIVE_EXTENSIONS

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
        return sorted(entries, key=lambda item: (not item.is_dir(), item.name.lower(), item.name))

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

    def _extract_zip(self, archive_path: Path, dest_dir: Path) -> None:
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
                with zf.open(info, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    def _extract_rar(self, archive_path: Path, dest_dir: Path) -> None:
        if rarfile is None:
            raise RuntimeError("rarfile 未安装，无法处理 .rar")
        with rarfile.RarFile(archive_path) as rf:
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
                with rf.open(info, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    def _extract_7z(self, archive_path: Path, dest_dir: Path) -> None:
        if py7zr is None:
            raise RuntimeError("py7zr 未安装，无法处理 .7z")
        with py7zr.SevenZipFile(archive_path, "r") as archive:
            for name in archive.getnames():
                if not self._is_safe_member_name(name):
                    raise ValueError(f"7z 包内包含非法路径: {name}")
            archive.extractall(path=dest_dir)

    def _extract_archive(self, archive_path: Path, dest_dir: Path) -> None:
        suffix = archive_path.suffix.lower()
        if suffix == ".zip":
            self._extract_zip(archive_path, dest_dir)
            return
        if suffix == ".rar":
            self._extract_rar(archive_path, dest_dir)
            return
        if suffix == ".7z":
            self._extract_7z(archive_path, dest_dir)
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

    def _normalize_to_clean_tree(self, input_root: Path, clean_root: Path) -> List[str]:
        warnings: List[str] = []
        scratch_root = input_root.parent / "scratch"
        scratch_root.mkdir(parents=True, exist_ok=True)

        def expand_entry(entry: Path, dst_parent: Path, depth: int) -> None:
            if depth > MAX_NESTED_DEPTH:
                warnings.append(f"嵌套层级过深，已跳过: {entry}")
                return

            if entry.is_dir():
                target_dir = self._make_unique_path(dst_parent / entry.name)
                target_dir.mkdir(parents=True, exist_ok=True)
                for child in self._sorted_entries(list(entry.iterdir())):
                    expand_entry(child, target_dir, depth + 1)
                self._prune_empty_directories(target_dir)
                return

            if self._is_image(entry):
                target_file = self._make_unique_path(dst_parent / entry.name)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, target_file)
                return

            if self._is_archive(entry):
                target_dir = self._make_unique_path(dst_parent / self._strip_archive_suffix(entry.name))
                target_dir.mkdir(parents=True, exist_ok=True)
                temp_dir = scratch_root / f"extract_{uuid.uuid4().hex}"
                temp_dir.mkdir(parents=True, exist_ok=True)
                try:
                    self._extract_archive(entry, temp_dir)
                    for child in self._sorted_entries(list(temp_dir.iterdir())):
                        expand_entry(child, target_dir, depth + 1)
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
            expand_entry(child, clean_root, 0)

        for child in list(clean_root.iterdir()):
            if child.is_dir():
                self._prune_empty_directories(child)
        return warnings

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

    def _build_export_payload(
        self,
        clean_root: Path,
        assignments: Dict[str, str],
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
        tree, node_map = self._build_tree(clean_root)

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
            key=lambda node_id: node_map[node_id]["abs_path"],
        )

        payload: List[Dict[str, str]] = []
        for node_id in deepest_work_nodes:
            node = node_map[node_id]
            payload.append(
                {
                    "作者名称": self._nearest_author_name(node_id, node_map, assignments),
                    "作品名称": node["real_name"],
                    "作品文件地址": node["abs_path"],
                }
            )
        return payload, tree, node_map

    def _create_empty_session(self) -> Tuple[str, Path, Path, Path]:
        session_id = uuid.uuid4().hex
        base = self._session_dir(session_id)
        input_root = base / "input"
        clean_root = base / "clean"
        input_root.mkdir(parents=True, exist_ok=True)
        clean_root.mkdir(parents=True, exist_ok=True)
        return session_id, base, input_root, clean_root

    def _finalize_session(self, session_id: str, clean_root: Path, warnings: List[str]) -> Dict[str, Any]:
        tree, _ = self._build_tree(clean_root)
        payload = {
            "session_id": session_id,
            "tree": tree,
            "warnings": warnings,
            "clean_root": str(clean_root.resolve()),
        }
        self._write_json(self._tree_path(session_id), payload)
        self._write_json(
            self._meta_path(session_id),
            {
                "session_id": session_id,
                "clean_root": str(clean_root.resolve()),
                "warnings": warnings,
                "created_at": self._timestamp(),
                "saved_assignments": {},
            },
        )
        return payload

    def _save_assignments_to_meta(self, session_id: str, assignments: Dict[str, str]) -> None:
        meta_file = self._meta_path(session_id)
        meta = self._read_json(meta_file, default={}) or {}
        meta["saved_assignments"] = dict(assignments)
        meta["updated_at"] = self._timestamp()
        self._write_json(meta_file, meta)

    def _load_clean_root(self, session_id: str) -> Path:
        self._ensure_session_dir(session_id)
        meta = self._read_json(self._meta_path(session_id), default={}) or {}
        clean_root = Path(str(meta.get("clean_root", "")).strip())
        if not clean_root.exists():
            raise ValueError("清洗后的目录不存在")
        return clean_root

    def create_session_from_path(self, source_path: str) -> Dict[str, Any]:
        raw = str(source_path or "").strip()
        if not raw:
            raise ValueError("缺少 source_path")

        source = Path(raw).expanduser()
        try:
            source = source.resolve()
        except Exception:
            source = Path(os.path.abspath(os.path.expanduser(raw)))

        if not source.exists():
            raise ValueError(
                "给定路径不存在。请注意：路径必须是服务器所在设备可访问的本机路径；"
                "若你在局域网其他设备访问本服务，不能直接使用你那台设备的本地路径。"
            )

        session_id, _base, input_root, clean_root = self._create_empty_session()
        target = input_root / source.name
        try:
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            warnings = self._normalize_to_clean_tree(input_root, clean_root)
            response = self._finalize_session(session_id, clean_root, warnings)
            app_logger.info(f"本地导入解析会话创建成功(path): {session_id}")
            return response
        except Exception:
            shutil.rmtree(self._session_dir(session_id), ignore_errors=True)
            raise

    def create_session_from_upload(self, files: List[Any], relative_paths: List[str]) -> Dict[str, Any]:
        if not files:
            raise ValueError("没有上传文件")
        if len(files) != len(relative_paths):
            raise ValueError("上传文件与相对路径数量不一致")

        session_id, _base, input_root, clean_root = self._create_empty_session()

        try:
            for upload_file, rel_path in zip(files, relative_paths):
                normalized = str(rel_path or "").replace("\\", "/")
                target = self._safe_target_from_member(input_root, normalized)
                if target is None:
                    continue
                self._copy_upload_file(upload_file, target)

            warnings = self._normalize_to_clean_tree(input_root, clean_root)
            response = self._finalize_session(session_id, clean_root, warnings)
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
        return data

    def export_session_items(self, session_id: str, raw_assignments: Dict[str, str]) -> Dict[str, Any]:
        clean_root = self._load_clean_root(session_id)
        assignments = self._normalize_assignments(raw_assignments)
        self._save_assignments_to_meta(session_id, assignments)

        items, tree, _node_map = self._build_export_payload(clean_root, assignments)
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
        return os.path.normcase(os.path.abspath(str(raw_source or "").strip()))

    def _build_local_comic_id(self, work_path: str, existing_ids: set[str]) -> str:
        normalized = self._normalize_existing_source(work_path)
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12].upper()
        base_id = f"JMLOCAL{digest}"
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

    def _ensure_comic_has_tag(self, comic_id: str, tag_id: str) -> bool:
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
                if tag_id not in tag_ids:
                    tag_ids.append(tag_id)
                    comic["tag_ids"] = tag_ids
                    status["updated"] = True
                    data["last_updated"] = time.strftime("%Y-%m-%d")
                break
            data["comics"] = comics
            return data

        ok = self._db_storage.atomic_update(updater)
        return bool(ok and status["updated"])

    @staticmethod
    def _iter_image_files(root: Path) -> List[Path]:
        files: List[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(path)

        def alphanum_key(text: str) -> List[Any]:
            parts: List[Any] = []
            chunk = ""
            for ch in text:
                if ch.isdigit():
                    if chunk and not chunk[-1].isdigit():
                        parts.append(chunk.lower())
                        chunk = ""
                    chunk += ch
                else:
                    if chunk and chunk[-1].isdigit():
                        parts.append(int(chunk))
                        chunk = ""
                    chunk += ch
            if chunk:
                if chunk.isdigit():
                    parts.append(int(chunk))
                else:
                    parts.append(chunk.lower())
            return parts

        return sorted(files, key=lambda p: alphanum_key(str(p).replace("\\", "/")))

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
    ) -> Dict[str, Any]:
        clean_root = self._load_clean_root(session_id)

        assignments = self._normalize_assignments(raw_assignments)
        if not assignments:
            meta = self._read_json(self._meta_path(session_id), default={}) or {}
            assignments = self._normalize_assignments(meta.get("saved_assignments", {}))
        if not assignments:
            raise ValueError("请先完成层级标记")

        self._save_assignments_to_meta(session_id, assignments)

        items, _tree, _node_map = self._build_export_payload(clean_root, assignments)
        self._write_json(self._result_path(session_id), items)

        state = self._load_or_create_state(session_id, total_items=len(items))
        state["status"] = "running"
        self._save_state(session_id, state)

        local_tag_id = self._ensure_local_tag_id() if items else ""

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
            record.update(
                {
                    "status": "running",
                    "title": title,
                    "author": author,
                    "work_path": work_path,
                    "updated_at": self._timestamp(),
                }
            )
            records[key] = record
            self._save_state(session_id, state)

            try:
                if key in existing_source_map:
                    record["status"] = "skipped"
                    record["comic_id"] = existing_source_map[key]
                    if local_tag_id:
                        self._ensure_comic_has_tag(record["comic_id"], local_tag_id)
                    record["error"] = ""
                    record["updated_at"] = self._timestamp()
                    self._save_state(session_id, state)
                    continue

                work_dir = Path(work_path)
                if not work_dir.exists() or not work_dir.is_dir():
                    raise RuntimeError("作品目录不存在，可能已被删除")

                comic_id = str(record.get("comic_id", "")).strip()
                if not comic_id:
                    comic_id = self._build_local_comic_id(work_path, existing_ids)
                    record["comic_id"] = comic_id

                original_id = comic_id[len("JM"):] if comic_id.startswith("JM") else comic_id
                staging_dir = staging_root / original_id
                copied_count = self._copy_work_to_staging(work_dir, staging_dir)
                if copied_count <= 0:
                    raise RuntimeError("作品目录中没有可导入图片")

                target_dir = Path(LOCAL_PICTURES_DIR) / original_id
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staging_dir), str(target_dir))

                image_paths = file_parser.parse_comic_images(comic_id)
                if not image_paths:
                    raise RuntimeError("导入后未检测到可读图片")

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
                    "total_page": len(image_paths),
                    "current_page": 1,
                    "score": 8.0,
                    "tag_ids": [local_tag_id] if local_tag_id else [],
                    "list_ids": [],
                    "create_time": now,
                    "last_read_time": now,
                    "is_deleted": False,
                    "import_source": work_path,
                }

                ok, inserted = self._append_comic_record(comic_record)
                if not ok:
                    raise RuntimeError("写入漫画数据库失败")

                existing_ids.add(comic_id)
                existing_source_map[key] = comic_id
                record["status"] = "completed" if inserted else "skipped"
                record["error"] = ""
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

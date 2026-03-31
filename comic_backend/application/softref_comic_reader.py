from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import stat
import tempfile
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from core.constants import CACHE_ROOT_DIR, JSON_FILE, SUPPORTED_FORMATS
from infrastructure.archive import ensure_rar_backend_configured
from infrastructure.persistence.json_storage import JsonStorage

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
SOFTREF_NESTED_ARCHIVE_CACHE_MAX_BYTES = 256 * 1024 * 1024
SOFTREF_NESTED_ARCHIVE_CACHE_SINGLE_MAX_BYTES = 64 * 1024 * 1024


class SoftRefError(Exception):
    pass


class SoftRefSourceMissingError(SoftRefError):
    pass


class SoftRefPasswordRequiredError(SoftRefError):
    def __init__(self, archive_fingerprint: str, archive_label: str, message: str = "压缩包需要密码"):
        super().__init__(message)
        self.archive_fingerprint = archive_fingerprint
        self.archive_label = archive_label


@dataclass
class _SoftRefContext:
    comic_id: str
    locator: str
    source_path: str


class SoftRefComicReader:
    def __init__(self):
        ensure_rar_backend_configured()
        self._db_storage = JsonStorage(JSON_FILE)
        self._index_cache: Dict[str, Dict[str, Any]] = {}
        self._nested_archive_cache: "OrderedDict[str, bytes]" = OrderedDict()
        self._nested_archive_cache_total_bytes = 0
        self._nested_archive_cache_max_bytes = self._resolve_positive_int_env(
            "SOFTREF_NESTED_ARCHIVE_CACHE_MAX_BYTES",
            SOFTREF_NESTED_ARCHIVE_CACHE_MAX_BYTES,
        )
        self._nested_archive_cache_single_max_bytes = self._resolve_positive_int_env(
            "SOFTREF_NESTED_ARCHIVE_CACHE_SINGLE_MAX_BYTES",
            SOFTREF_NESTED_ARCHIVE_CACHE_SINGLE_MAX_BYTES,
        )

    @staticmethod
    def _resolve_positive_int_env(name: str, default_value: int) -> int:
        try:
            value = int(str(os.environ.get(name, "")).strip())
            if value > 0:
                return value
        except Exception:
            pass
        return int(default_value)

    @staticmethod
    def _is_softref_locator(raw_path: str) -> bool:
        return str(raw_path or "").startswith("softref://")

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

    @staticmethod
    def _looks_like_image_name(filename: str) -> bool:
        return Path(str(filename or "")).suffix.lower() in IMAGE_EXTENSIONS

    @staticmethod
    def _looks_like_archive_name(filename: str) -> bool:
        return Path(str(filename or "")).suffix.lower() in ARCHIVE_EXTENSIONS

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
    def _guess_mimetype_from_name(name: str) -> str:
        ext = Path(str(name or "")).suffix.lower().lstrip(".")
        if ext in {"jpg", "jpeg"}:
            return "image/jpeg"
        if ext == "png":
            return "image/png"
        if ext == "webp":
            return "image/webp"
        if ext == "gif":
            return "image/gif"
        if ext == "bmp":
            return "image/bmp"
        return "application/octet-stream"

    @staticmethod
    def _member_relative_to_base(member_name: str, base_inner_path: str) -> Optional[str]:
        normalized = str(member_name or "").replace("\\", "/")
        pure_member = PurePosixPath(normalized)
        member_parts = [part for part in pure_member.parts if part not in {"", "."}]
        if not member_parts:
            return None

        base = str(base_inner_path or ".").replace("\\", "/")
        if base in {"", "."}:
            return "/".join(member_parts)

        base_parts = [part for part in PurePosixPath(base).parts if part not in {"", "."}]
        if len(member_parts) < len(base_parts):
            return None
        if [part.lower() for part in member_parts[: len(base_parts)]] != [part.lower() for part in base_parts]:
            return None
        rel_parts = member_parts[len(base_parts) :]
        return "/".join(rel_parts) if rel_parts else "."

    @staticmethod
    def _normalize_locator_signature(locator: str, payload: Dict[str, Any]) -> str:
        if not locator:
            return ""
        if not locator.startswith("softref://"):
            source = Path(locator)
            if not source.exists():
                return "missing"
            stat_info = source.stat()
            source_type = "dir" if source.is_dir() else "file"
            return f"{source_type}:{os.path.normcase(str(source.resolve()))}:{stat_info.st_mtime_ns}:{stat_info.st_size}"

        top_archive = Path(str(payload.get("top_archive_path", "")).strip())
        if not top_archive.exists():
            return "missing"
        stat_info = top_archive.stat()
        chain = payload.get("archive_chain") or []
        chain_sig = "|".join(str(item) for item in chain)
        inner_path = str(payload.get("inner_path", "."))
        return (
            f"archive:{os.path.normcase(str(top_archive.resolve()))}:"
            f"{stat_info.st_mtime_ns}:{stat_info.st_size}:{chain_sig}:{inner_path}"
        )

    @staticmethod
    def _is_password_error(exc: Exception) -> bool:
        message = str(exc or "").lower()
        return any(
            keyword in message
            for keyword in [
                "password",
                "encrypted",
                "bad passphrase",
                "wrong pass",
                "wrong password",
                "need password",
            ]
        )

    @staticmethod
    def _is_rar_password_tool_missing(exc: Exception) -> bool:
        message = str(exc or "").lower()
        return "does not support passwords" in message

    @staticmethod
    def _archive_fingerprint(top_archive_path: str, archive_prefix_chain: List[str]) -> str:
        top = os.path.normcase(os.path.abspath(str(top_archive_path or "")))
        chain = "|".join(str(item or "") for item in (archive_prefix_chain or []))
        raw = f"{top}::{chain}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _archive_label(top_archive_path: str, archive_prefix_chain: List[str]) -> str:
        base = Path(str(top_archive_path or "")).name or str(top_archive_path or "")
        if not archive_prefix_chain:
            return base
        return f"{base} :: {' / '.join(archive_prefix_chain)}"

    @staticmethod
    def _nested_archive_cache_key(top_archive_path: str, archive_chain: List[str]) -> str:
        normalized_top = os.path.normcase(os.path.abspath(str(top_archive_path or "")))
        chain = "|".join(str(item or "") for item in (archive_chain or []))
        return f"{normalized_top}::{chain}"

    def _get_nested_archive_cache(self, key: str) -> Optional[bytes]:
        entry = self._nested_archive_cache.pop(key, None)
        if entry is None:
            return None
        self._nested_archive_cache[key] = entry
        return entry

    def _put_nested_archive_cache(self, key: str, payload: bytes) -> None:
        if not isinstance(payload, (bytes, bytearray)):
            return
        data = bytes(payload)
        payload_size = len(data)
        if payload_size <= 0:
            return
        if payload_size > self._nested_archive_cache_single_max_bytes:
            return
        if self._nested_archive_cache_max_bytes <= 0:
            return

        old = self._nested_archive_cache.pop(key, None)
        if old is not None:
            self._nested_archive_cache_total_bytes -= len(old)

        self._nested_archive_cache[key] = data
        self._nested_archive_cache_total_bytes += payload_size

        while self._nested_archive_cache and self._nested_archive_cache_total_bytes > self._nested_archive_cache_max_bytes:
            _, removed_payload = self._nested_archive_cache.popitem(last=False)
            self._nested_archive_cache_total_bytes -= len(removed_payload)

    @staticmethod
    def _password_required_error(top_archive_path: str, archive_prefix_chain: List[str]) -> SoftRefPasswordRequiredError:
        return SoftRefPasswordRequiredError(
            archive_fingerprint=SoftRefComicReader._archive_fingerprint(top_archive_path, archive_prefix_chain),
            archive_label=SoftRefComicReader._archive_label(top_archive_path, archive_prefix_chain),
        )

    @staticmethod
    def _timestamp() -> str:
        import time

        return time.strftime("%Y-%m-%dT%H:%M:%S")

    def _load_password_store(self) -> Dict[str, Any]:
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

    def _save_password_store(self, payload: Dict[str, Any]) -> None:
        payload = payload if isinstance(payload, dict) else {"archives": {}}
        payload.setdefault("archives", {})
        SOFTREF_PASSWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SOFTREF_PASSWORDS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_password_for_archive(self, top_archive_path: str, archive_prefix_chain: List[str]) -> Optional[str]:
        store = self._load_password_store()
        archives = store.get("archives", {}) if isinstance(store, dict) else {}
        fingerprint = self._archive_fingerprint(top_archive_path, archive_prefix_chain)
        item = archives.get(fingerprint) if isinstance(archives, dict) else None
        password = str((item or {}).get("password", "")).strip()
        return password or None

    def _get_raw_comic_record(self, comic_id: str) -> Optional[Dict[str, Any]]:
        data = self._db_storage.read()
        comics = data.get("comics", []) if isinstance(data, dict) else []
        for item in comics:
            if str((item or {}).get("id", "")) == str(comic_id):
                return item if isinstance(item, dict) else None
        return None

    def is_soft_ref_comic(self, comic_id: str) -> bool:
        item = self._get_raw_comic_record(comic_id)
        if not item:
            return False
        return str(item.get("storage_mode", "")).strip().lower() == "soft_ref"

    def set_archive_password(self, comic_id: str, archive_fingerprint: str, password: str) -> Dict[str, Any]:
        comic_record = self._get_raw_comic_record(comic_id)
        if not comic_record:
            raise ValueError("漫画不存在")
        if str(comic_record.get("storage_mode", "")).strip().lower() != "soft_ref":
            raise ValueError("该漫画不是软连接导入")

        fp = str(archive_fingerprint or "").strip().lower()
        if not fp:
            raise ValueError("缺少 archive_fingerprint")
        pwd = str(password or "")
        if not pwd:
            raise ValueError("密码不能为空")

        store = self._load_password_store()
        archives = store.setdefault("archives", {})
        archives[fp] = {
            "password": pwd,
            "updated_at": self._timestamp(),
        }
        self._save_password_store(store)
        self._index_cache.pop(comic_id, None)
        return {"archive_fingerprint": fp, "saved": True}

    def _resolve_context(self, comic_id: str) -> _SoftRefContext:
        item = self._get_raw_comic_record(comic_id)
        if not item:
            raise ValueError("漫画不存在")
        if str(item.get("storage_mode", "")).strip().lower() != "soft_ref":
            raise ValueError("该漫画不是软连接导入")

        locator = str(item.get("soft_ref_locator", "") or item.get("import_source", "")).strip()
        if not locator:
            raise SoftRefSourceMissingError("软连接定位信息缺失")
        source_path = str(item.get("import_source", "")).strip()
        return _SoftRefContext(comic_id=comic_id, locator=locator, source_path=source_path)

    def _get_or_build_page_index(self, context: _SoftRefContext) -> List[Dict[str, Any]]:
        locator_payload = self._decode_softref_locator(context.locator) if self._is_softref_locator(context.locator) else {}
        signature = self._normalize_locator_signature(context.locator, locator_payload)
        if signature == "missing":
            raise SoftRefSourceMissingError("源文件不存在或不可访问")

        cached = self._index_cache.get(context.comic_id)
        if (
            cached
            and str(cached.get("locator", "")) == context.locator
            and str(cached.get("signature", "")) == signature
            and isinstance(cached.get("entries"), list)
        ):
            return cached["entries"]

        entries = self._build_page_entries(context, locator_payload)
        self._index_cache[context.comic_id] = {
            "locator": context.locator,
            "signature": signature,
            "entries": entries,
            "updated_at": self._timestamp(),
        }
        return entries

    def get_page_count(self, comic_id: str) -> int:
        context = self._resolve_context(comic_id)
        entries = self._get_or_build_page_index(context)
        return len(entries)

    def get_password_required_payload(self, comic_id: str, exc: SoftRefPasswordRequiredError) -> Dict[str, Any]:
        return {
            "type": "softref_password_required",
            "comic_id": comic_id,
            "archive_fingerprint": exc.archive_fingerprint,
            "archive_label": exc.archive_label,
            "message": str(exc),
        }

    def get_image_stream(self, comic_id: str, page_num: int) -> Tuple[io.BytesIO, str]:
        context = self._resolve_context(comic_id)
        entries = self._get_or_build_page_index(context)
        if page_num < 1 or page_num > len(entries):
            raise ValueError("页码超出范围")

        entry = entries[page_num - 1]
        kind = str(entry.get("kind", ""))
        if kind == "file":
            path = Path(str(entry.get("path", "")).strip())
            if not path.exists() or not path.is_file():
                raise SoftRefSourceMissingError("源图片文件不存在")
            data = path.read_bytes()
            return io.BytesIO(data), self._guess_mimetype_from_name(path.name)

        if kind == "archive_member":
            top_archive_path = str(entry.get("top_archive_path", "")).strip()
            chain = list(entry.get("archive_chain") or [])
            member_name = str(entry.get("member_name", "")).replace("\\", "/")
            if not top_archive_path or not member_name:
                raise SoftRefSourceMissingError("压缩包定位信息损坏")
            data = self._read_archive_member_bytes_by_chain(top_archive_path, chain, member_name)
            return io.BytesIO(data), self._guess_mimetype_from_name(member_name)

        raise SoftRefSourceMissingError("不支持的软连接页面类型")

    def _build_page_entries(self, context: _SoftRefContext, locator_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._is_softref_locator(context.locator):
            source = Path(context.locator)
            if not source.exists():
                raise SoftRefSourceMissingError("源文件不存在或不可访问")
            if source.is_dir():
                entries: List[Dict[str, Any]] = []
                for path in source.rglob("*"):
                    if not path.is_file():
                        continue
                    if path.suffix.lower() not in IMAGE_EXTENSIONS:
                        continue
                    entries.append(
                        {
                            "kind": "file",
                            "path": str(path.resolve()),
                            "sort_path": str(path.relative_to(source)).replace("\\", "/"),
                        }
                    )
                entries.sort(key=lambda item: self._natural_sort_key(str(item.get("sort_path", ""))))
                return entries
            if source.is_file() and source.suffix.lower() in IMAGE_EXTENSIONS:
                return [{"kind": "file", "path": str(source.resolve()), "sort_path": source.name}]
            raise SoftRefSourceMissingError("软连接源不是可读目录或图片文件")

        kind = str(locator_payload.get("kind", "")).strip().lower()
        if kind != "archive_dir":
            raise SoftRefSourceMissingError("不支持的软连接定位类型")

        source_path = str(locator_payload.get("source_path", "")).strip()
        top_archive_path = str(locator_payload.get("top_archive_path", "")).strip()
        archive_chain = [str(item or "").replace("\\", "/") for item in (locator_payload.get("archive_chain") or [])]
        inner_path = str(locator_payload.get("inner_path", ".") or ".").replace("\\", "/")
        if not top_archive_path:
            raise SoftRefSourceMissingError("压缩包路径缺失")
        top_archive = Path(top_archive_path)
        if not top_archive.exists() or not top_archive.is_file():
            raise SoftRefSourceMissingError("源压缩包不存在")

        entries: List[Dict[str, Any]] = []
        self._collect_archive_images_recursive(
            archive_source_kind="path",
            archive_source=top_archive_path,
            archive_suffix=top_archive.suffix.lower(),
            top_archive_path=top_archive_path,
            archive_prefix_chain=[],
            base_inner_path=".",
            depth=0,
            output_entries=entries,
            selected_chain=archive_chain,
            selected_inner_path=inner_path,
            source_path=source_path,
        )
        entries.sort(key=lambda item: self._natural_sort_key(str(item.get("sort_path", ""))))
        return entries

    def _collect_archive_images_recursive(
        self,
        *,
        archive_source_kind: str,
        archive_source: Any,
        archive_suffix: str,
        top_archive_path: str,
        archive_prefix_chain: List[str],
        base_inner_path: str,
        depth: int,
        output_entries: List[Dict[str, Any]],
        selected_chain: List[str],
        selected_inner_path: str,
        source_path: str,
    ) -> None:
        if depth > MAX_NESTED_DEPTH:
            return

        members = self._list_archive_members(
            archive_source_kind=archive_source_kind,
            archive_source=archive_source,
            archive_suffix=archive_suffix,
            top_archive_path=top_archive_path,
            archive_prefix_chain=archive_prefix_chain,
        )

        for member in members:
            member_name = str(member.get("name", "")).replace("\\", "/")
            if not member_name or not self._is_safe_member_name(member_name):
                continue
            rel_to_base = self._member_relative_to_base(member_name, base_inner_path)
            if rel_to_base is None or rel_to_base == ".":
                continue
            is_dir = bool(member.get("is_dir", False))
            if is_dir:
                continue

            current_chain = list(archive_prefix_chain)

            if self._looks_like_image_name(member_name):
                if current_chain != selected_chain:
                    continue
                rel_to_selected = self._member_relative_to_base(member_name, selected_inner_path)
                if rel_to_selected is None or rel_to_selected == ".":
                    continue
                output_entries.append(
                    {
                        "kind": "archive_member",
                        "top_archive_path": top_archive_path,
                        "archive_chain": list(current_chain),
                        "member_name": member_name,
                        "source_path": source_path,
                        "sort_path": rel_to_selected,
                    }
                )
                continue

            if not self._looks_like_archive_name(member_name):
                continue

            nested_chain = list(current_chain) + [member_name]
            should_descend = False
            nested_base_inner = "."
            if selected_chain[: len(nested_chain)] == nested_chain:
                should_descend = True
                if len(selected_chain) == len(nested_chain):
                    nested_base_inner = selected_inner_path
            elif selected_chain == current_chain:
                rel_to_selected = self._member_relative_to_base(member_name, selected_inner_path)
                if rel_to_selected is not None and rel_to_selected != ".":
                    should_descend = True
                    nested_base_inner = "."

            if not should_descend:
                continue

            nested_bytes = self._read_archive_member_bytes(
                archive_source_kind=archive_source_kind,
                archive_source=archive_source,
                archive_suffix=archive_suffix,
                top_archive_path=top_archive_path,
                archive_prefix_chain=current_chain,
                member_name=member_name,
            )
            self._collect_archive_images_recursive(
                archive_source_kind="bytes",
                archive_source=nested_bytes,
                archive_suffix=Path(member_name).suffix.lower(),
                top_archive_path=top_archive_path,
                archive_prefix_chain=nested_chain,
                base_inner_path=nested_base_inner,
                depth=depth + 1,
                output_entries=output_entries,
                selected_chain=selected_chain,
                selected_inner_path=selected_inner_path,
                source_path=source_path,
            )

    def _read_archive_member_bytes_by_chain(
        self,
        top_archive_path: str,
        archive_chain: List[str],
        member_name: str,
    ) -> bytes:
        source_kind = "path"
        source: Any = top_archive_path
        suffix = Path(top_archive_path).suffix.lower()
        current_chain: List[str] = []

        for nested_archive_name in archive_chain:
            next_chain = list(current_chain) + [nested_archive_name]
            cache_key = self._nested_archive_cache_key(top_archive_path, next_chain)
            cached_nested = self._get_nested_archive_cache(cache_key)
            if cached_nested is not None:
                source_kind = "bytes"
                source = cached_nested
                suffix = Path(nested_archive_name).suffix.lower()
                current_chain = next_chain
                continue

            nested_bytes = self._read_archive_member_bytes(
                archive_source_kind=source_kind,
                archive_source=source,
                archive_suffix=suffix,
                top_archive_path=top_archive_path,
                archive_prefix_chain=current_chain,
                member_name=nested_archive_name,
            )
            self._put_nested_archive_cache(cache_key, nested_bytes)
            source_kind = "bytes"
            source = nested_bytes
            suffix = Path(nested_archive_name).suffix.lower()
            current_chain = next_chain

        return self._read_archive_member_bytes(
            archive_source_kind=source_kind,
            archive_source=source,
            archive_suffix=suffix,
            top_archive_path=top_archive_path,
            archive_prefix_chain=current_chain,
            member_name=member_name,
        )

    def _list_archive_members(
        self,
        *,
        archive_source_kind: str,
        archive_source: Any,
        archive_suffix: str,
        top_archive_path: str,
        archive_prefix_chain: List[str],
    ) -> List[Dict[str, Any]]:
        suffix = str(archive_suffix or "").lower()
        password = self._get_password_for_archive(top_archive_path, archive_prefix_chain)

        if suffix == ".zip":
            zip_obj = (
                zipfile.ZipFile(str(archive_source), "r")
                if archive_source_kind == "path"
                else zipfile.ZipFile(io.BytesIO(archive_source), "r")
            )
            with zip_obj as zf:
                infos = [info for info in zf.infolist() if self._is_safe_member_name(info.filename)]
                return [
                    {
                        "name": str(info.filename or ""),
                        "is_dir": bool(info.is_dir()),
                        "encrypted": bool(info.flag_bits & 0x1),
                    }
                    for info in infos
                    if not stat.S_ISLNK(info.external_attr >> 16)
                ]

        if suffix == ".rar":
            if rarfile is None:
                raise RuntimeError("缺少 rarfile 依赖，无法读取 RAR 软连接漫画")
            temp_path = None
            try:
                rar_path = str(archive_source)
                if archive_source_kind != "path":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".rar") as tmp:
                        tmp.write(archive_source)
                        temp_path = tmp.name
                    rar_path = temp_path
                with rarfile.RarFile(rar_path) as rf:  # type: ignore[arg-type]
                    if password and hasattr(rf, "setpassword"):
                        rf.setpassword(password)
                    infos = list(rf.infolist())
                    if not infos and not password:
                        raise self._password_required_error(top_archive_path, archive_prefix_chain)
                    result: List[Dict[str, Any]] = []
                    for info in infos:
                        member_name = str(getattr(info, "filename", "") or "")
                        if not member_name or not self._is_safe_member_name(member_name):
                            continue
                        is_dir = False
                        if hasattr(info, "is_dir"):
                            is_dir = bool(info.is_dir())
                        elif hasattr(info, "isdir"):
                            is_dir = bool(info.isdir())
                        if hasattr(info, "is_symlink") and info.is_symlink():
                            continue
                        result.append({"name": member_name, "is_dir": is_dir, "encrypted": False})
                    return result
            except SoftRefPasswordRequiredError:
                raise
            except Exception as exc:
                if self._is_rar_password_tool_missing(exc):
                    raise RuntimeError("当前 RAR 解包器不支持加密包读取，请安装支持密码的 unrar/7z 工具。")
                if self._is_password_error(exc):
                    raise self._password_required_error(top_archive_path, archive_prefix_chain)
                raise
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        if suffix == ".7z":
            if py7zr is None:
                raise RuntimeError("缺少 py7zr 依赖，无法读取 7z 软连接漫画")
            try:
                if archive_source_kind == "path":
                    with py7zr.SevenZipFile(str(archive_source), "r", password=(password or None)) as archive:
                        names = archive.getnames()
                else:
                    with py7zr.SevenZipFile(io.BytesIO(archive_source), "r", password=(password or None)) as archive:
                        names = archive.getnames()
                return [
                    {"name": str(name or ""), "is_dir": str(name or "").endswith("/"), "encrypted": False}
                    for name in names
                    if self._is_safe_member_name(str(name or ""))
                ]
            except Exception as exc:
                if self._is_password_error(exc):
                    raise self._password_required_error(top_archive_path, archive_prefix_chain)
                raise

        raise RuntimeError(f"不支持的压缩包格式: {archive_suffix}")

    def _read_archive_member_bytes(
        self,
        *,
        archive_source_kind: str,
        archive_source: Any,
        archive_suffix: str,
        top_archive_path: str,
        archive_prefix_chain: List[str],
        member_name: str,
    ) -> bytes:
        suffix = str(archive_suffix or "").lower()
        if not self._is_safe_member_name(member_name):
            raise RuntimeError(f"压缩包内路径不安全: {member_name}")

        password = self._get_password_for_archive(top_archive_path, archive_prefix_chain)
        password_bytes = password.encode("utf-8") if password else None

        if suffix == ".zip":
            zip_obj = (
                zipfile.ZipFile(str(archive_source), "r")
                if archive_source_kind == "path"
                else zipfile.ZipFile(io.BytesIO(archive_source), "r")
            )
            with zip_obj as zf:
                try:
                    info = zf.getinfo(member_name)
                except KeyError:
                    info = None
                if info is None or stat.S_ISLNK(info.external_attr >> 16):
                    raise RuntimeError(f"压缩包内文件不存在: {member_name}")
                try:
                    if password_bytes:
                        with zf.open(info, "r", pwd=password_bytes) as src:
                            return src.read()
                    with zf.open(info, "r") as src:
                        return src.read()
                except Exception as exc:
                    if self._is_password_error(exc):
                        raise self._password_required_error(top_archive_path, archive_prefix_chain)
                    raise

        if suffix == ".rar":
            if rarfile is None:
                raise RuntimeError("缺少 rarfile 依赖，无法读取 RAR 软连接漫画")
            temp_path = None
            try:
                rar_path = str(archive_source)
                if archive_source_kind != "path":
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".rar") as tmp:
                        tmp.write(archive_source)
                        temp_path = tmp.name
                    rar_path = temp_path
                with rarfile.RarFile(rar_path) as rf:  # type: ignore[arg-type]
                    if password and hasattr(rf, "setpassword"):
                        rf.setpassword(password)
                    try:
                        info = rf.getinfo(member_name)
                    except Exception:
                        info = None
                    if info is None:
                        raise RuntimeError(f"压缩包内文件不存在: {member_name}")
                    kwargs: Dict[str, Any] = {}
                    if password:
                        kwargs["pwd"] = password
                    with rf.open(info, "r", **kwargs) as src:
                        return src.read()
            except Exception as exc:
                if self._is_rar_password_tool_missing(exc):
                    raise RuntimeError("当前 RAR 解包器不支持加密包读取，请安装支持密码的 unrar/7z 工具。")
                if self._is_password_error(exc):
                    raise self._password_required_error(top_archive_path, archive_prefix_chain)
                raise
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        if suffix == ".7z":
            if py7zr is None:
                raise RuntimeError("缺少 py7zr 依赖，无法读取 7z 软连接漫画")
            try:
                with tempfile.TemporaryDirectory(prefix="softref_7z_") as temp_dir:
                    if archive_source_kind == "path":
                        with py7zr.SevenZipFile(str(archive_source), "r", password=(password or None)) as archive:
                            archive.extract(path=temp_dir, targets=[member_name])
                    else:
                        with py7zr.SevenZipFile(io.BytesIO(archive_source), "r", password=(password or None)) as archive:
                            archive.extract(path=temp_dir, targets=[member_name])
                    target = Path(temp_dir) / PurePosixPath(member_name)
                    if not target.exists() or not target.is_file():
                        raise RuntimeError(f"压缩包内文件不存在: {member_name}")
                    return target.read_bytes()
            except Exception as exc:
                if self._is_password_error(exc):
                    raise self._password_required_error(top_archive_path, archive_prefix_chain)
                raise

        raise RuntimeError(f"不支持的压缩包格式: {archive_suffix}")


softref_comic_reader = SoftRefComicReader()


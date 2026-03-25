from __future__ import annotations

import json
import shutil
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import py7zr  # type: ignore
except Exception:  # pragma: no cover
    py7zr = None

try:
    import rarfile  # type: ignore
except Exception:  # pragma: no cover
    rarfile = None


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
WORKSPACE_DIR = BASE_DIR / "workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".avif",
    ".jfif",
}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
MAX_NESTED_DEPTH = 30

app = FastAPI(title="本地漫画导入解析器")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class PathImportRequest(BaseModel):
    source_path: str


class ExportRequest(BaseModel):
    session_id: str
    assignments: Dict[str, str]


def session_dir(session_id: str) -> Path:
    return WORKSPACE_DIR / session_id


def meta_path(session_id: str) -> Path:
    return session_dir(session_id) / "meta.json"


def tree_path(session_id: str) -> Path:
    return session_dir(session_id) / "tree.json"


def result_path(session_id: str) -> Path:
    return session_dir(session_id) / "result.json"


def ensure_session(session_id: str) -> Path:
    path = session_dir(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    return path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_archive(path: Path) -> bool:
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def normalize_name(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch not in {" ", "_", "-", "."})


def strip_archive_suffix(filename: str) -> str:
    path = Path(filename)
    return path.stem if path.suffix else filename


def make_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10_000):
        candidate = path.with_name(f"{stem}__{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法为 {path} 找到可用的唯一名称")


def sorted_entries(entries: List[Path]) -> List[Path]:
    return sorted(entries, key=lambda item: (not item.is_dir(), item.name.lower(), item.name))


def is_safe_member_name(member_name: str) -> bool:
    normalized = member_name.replace("\\", "/")
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


def safe_target_from_member(dest_dir: Path, member_name: str) -> Optional[Path]:
    if not is_safe_member_name(member_name):
        raise ValueError(f"压缩包中存在非法路径: {member_name}")
    pure = PurePosixPath(member_name.replace("\\", "/"))
    parts = [part for part in pure.parts if part not in {"", "."}]
    if not parts:
        return None
    return dest_dir.joinpath(*parts)


def extract_zip(archive_path: Path, dest_dir: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as zf:
        for info in zf.infolist():
            target = safe_target_from_member(dest_dir, info.filename)
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


def extract_rar(archive_path: Path, dest_dir: Path) -> None:
    if rarfile is None:
        raise RuntimeError("未安装 rarfile，无法处理 .rar")
    with rarfile.RarFile(archive_path) as rf:
        for info in rf.infolist():
            target = safe_target_from_member(dest_dir, info.filename)
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


def extract_7z(archive_path: Path, dest_dir: Path) -> None:
    if py7zr is None:
        raise RuntimeError("未安装 py7zr，无法处理 .7z")
    with py7zr.SevenZipFile(archive_path, "r") as archive:
        for name in archive.getnames():
            if not is_safe_member_name(name):
                raise ValueError(f"7z 包中存在非法路径: {name}")
        archive.extractall(path=dest_dir)


def extract_archive(archive_path: Path, dest_dir: Path) -> None:
    suffix = archive_path.suffix.lower()
    if suffix == ".zip":
        extract_zip(archive_path, dest_dir)
        return
    if suffix == ".rar":
        extract_rar(archive_path, dest_dir)
        return
    if suffix == ".7z":
        extract_7z(archive_path, dest_dir)
        return
    raise RuntimeError(f"不支持的压缩格式: {archive_path.suffix}")


def flatten_archive_directory(target_dir: Path) -> None:
    children = [child for child in target_dir.iterdir()]
    dirs = [child for child in children if child.is_dir()]
    files = [child for child in children if child.is_file()]
    if len(dirs) != 1 or files:
        return
    only_child = dirs[0]
    if normalize_name(only_child.name) != normalize_name(target_dir.name):
        return
    for item in sorted_entries(list(only_child.iterdir())):
        destination = make_unique_path(target_dir / item.name)
        shutil.move(str(item), str(destination))
    only_child.rmdir()


def prune_empty_directories(path: Path) -> bool:
    if not path.is_dir():
        return False
    for child in list(path.iterdir()):
        if child.is_dir():
            prune_empty_directories(child)
    if any(path.iterdir()):
        return False
    path.rmdir()
    return True


def copy_upload_file(upload_file: UploadFile, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "wb") as dst:
        shutil.copyfileobj(upload_file.file, dst)


def normalize_to_clean_tree(input_root: Path, clean_root: Path) -> List[str]:
    warnings: List[str] = []
    scratch_root = input_root.parent / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)

    def expand_entry(entry: Path, dst_parent: Path, depth: int) -> None:
        if depth > MAX_NESTED_DEPTH:
            warnings.append(f"嵌套层级过深，已跳过: {entry}")
            return

        if entry.is_dir():
            target_dir = make_unique_path(dst_parent / entry.name)
            target_dir.mkdir(parents=True, exist_ok=True)
            for child in sorted_entries(list(entry.iterdir())):
                expand_entry(child, target_dir, depth + 1)
            prune_empty_directories(target_dir)
            return

        if is_image(entry):
            target_file = make_unique_path(dst_parent / entry.name)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target_file)
            return

        if is_archive(entry):
            target_dir = make_unique_path(dst_parent / strip_archive_suffix(entry.name))
            target_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = scratch_root / f"extract_{uuid.uuid4().hex}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            try:
                extract_archive(entry, temp_dir)
                for child in sorted_entries(list(temp_dir.iterdir())):
                    expand_entry(child, target_dir, depth + 1)
                flatten_archive_directory(target_dir)
                prune_empty_directories(target_dir)
            except Exception as exc:
                shutil.rmtree(target_dir, ignore_errors=True)
                warnings.append(f"解压失败，已跳过 {entry.name}: {exc}")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return

        warnings.append(f"跳过非图片/非压缩包文件: {entry.name}")

    clean_root.mkdir(parents=True, exist_ok=True)
    for child in sorted_entries(list(input_root.iterdir())):
        expand_entry(child, clean_root, 0)

    for child in list(clean_root.iterdir()):
        if child.is_dir():
            prune_empty_directories(child)
    return warnings


def count_direct_images(path: Path) -> int:
    total = 0
    for child in path.iterdir():
        if child.is_file() and is_image(child):
            total += 1
    return total


def build_tree(clean_root: Path) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    node_map: Dict[str, Dict[str, Any]] = {}

    def walk(path: Path, rel_id: str, parent_id: Optional[str]) -> Dict[str, Any]:
        children_nodes: List[Dict[str, Any]] = []
        child_ids: List[str] = []
        for child_dir in sorted_entries([child for child in path.iterdir() if child.is_dir()]):
            child_rel = child_dir.name if rel_id == "." else f"{rel_id}/{child_dir.name}"
            child_node = walk(child_dir, child_rel, rel_id)
            children_nodes.append(child_node)
            child_ids.append(child_rel)

        direct_images = count_direct_images(path)
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


def nearest_author_name(node_id: str, node_map: Dict[str, Dict[str, Any]], assignments: Dict[str, str]) -> str:
    current_id = node_map[node_id]["parent_id"]
    while current_id is not None:
        current_node = node_map[current_id]
        parent_id = current_node["parent_id"]
        if parent_id is not None and assignments.get(parent_id) == "author":
            return current_node["real_name"]
        current_id = parent_id
    return ""


def build_export_payload(
    clean_root: Path, assignments: Dict[str, str]
) -> Tuple[List[Dict[str, str]], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    tree, node_map = build_tree(clean_root)

    work_nodes: set[str] = set()
    for parent_id, role in assignments.items():
        if role != "work":
            continue
        parent_node = node_map.get(parent_id)
        if not parent_node:
            continue
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
                "作者名称": nearest_author_name(node_id, node_map, assignments),
                "作品名称": node["real_name"],
                "作品文件地址": node["abs_path"],
            }
        )
    return payload, tree, node_map


def create_empty_session() -> Tuple[str, Path, Path, Path]:
    session_id = uuid.uuid4().hex
    base = WORKSPACE_DIR / session_id
    input_root = base / "input"
    clean_root = base / "clean"
    input_root.mkdir(parents=True, exist_ok=True)
    clean_root.mkdir(parents=True, exist_ok=True)
    return session_id, base, input_root, clean_root


def finalize_session(session_id: str, clean_root: Path, warnings: List[str]) -> Dict[str, Any]:
    tree, _ = build_tree(clean_root)
    payload = {
        "session_id": session_id,
        "tree": tree,
        "warnings": warnings,
        "clean_root": str(clean_root.resolve()),
    }
    write_json(tree_path(session_id), payload)
    write_json(
        meta_path(session_id),
        {
            "session_id": session_id,
            "clean_root": str(clean_root.resolve()),
            "warnings": warnings,
        },
    )
    return payload


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/import/from-path")
def import_from_path(payload: PathImportRequest) -> JSONResponse:
    source = Path(payload.source_path).expanduser().resolve()
    if not source.exists():
        raise HTTPException(status_code=400, detail="给定路径不存在")

    session_id, _base, input_root, clean_root = create_empty_session()
    target = input_root / source.name
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    warnings = normalize_to_clean_tree(input_root, clean_root)
    response = finalize_session(session_id, clean_root, warnings)
    return JSONResponse(response)


@app.post("/api/import/upload")
def import_from_upload(
    files: List[UploadFile] = File(...),
    relative_paths: List[str] = Form(...),
) -> JSONResponse:
    if len(files) != len(relative_paths):
        raise HTTPException(status_code=400, detail="上传文件与相对路径数量不一致")

    session_id, _base, input_root, clean_root = create_empty_session()

    for upload_file, rel_path in zip(files, relative_paths):
        normalized = rel_path.replace("\\", "/")
        target = safe_target_from_member(input_root, normalized)
        if target is None:
            continue
        copy_upload_file(upload_file, target)

    warnings = normalize_to_clean_tree(input_root, clean_root)
    response = finalize_session(session_id, clean_root, warnings)
    return JSONResponse(response)


@app.get("/api/sessions/{session_id}/tree")
def get_tree(session_id: str) -> JSONResponse:
    ensure_session(session_id)
    if not tree_path(session_id).exists():
        raise HTTPException(status_code=404, detail="目录树不存在")
    return JSONResponse(read_json(tree_path(session_id)))


@app.post("/api/export-json")
def export_json(payload: ExportRequest) -> JSONResponse:
    ensure_session(payload.session_id)
    meta = read_json(meta_path(payload.session_id))
    clean_root = Path(meta["clean_root"])
    if not clean_root.exists():
        raise HTTPException(status_code=404, detail="清洗后的目录不存在")

    items, tree, _node_map = build_export_payload(clean_root, payload.assignments)
    write_json(result_path(payload.session_id), items)
    return JSONResponse(
        {
            "session_id": payload.session_id,
            "items": items,
            "count": len(items),
            "download_url": f"/api/sessions/{payload.session_id}/result.json",
            "tree": tree,
        }
    )


@app.get("/api/sessions/{session_id}/result.json")
def download_result(session_id: str) -> FileResponse:
    ensure_session(session_id)
    path = result_path(session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="请先生成 JSON")
    return FileResponse(path, media_type="application/json", filename="result.json")


@app.delete("/api/sessions/{session_id}")
def clear_session(session_id: str) -> JSONResponse:
    path = ensure_session(session_id)
    shutil.rmtree(path, ignore_errors=True)
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _runtime_profile() -> str:
    return str(os.environ.get("BACKEND_RUNTIME_PROFILE") or "").strip().lower()


def _install_root(create: bool = True) -> Path:
    raw = str(os.environ.get("ULTIMATE_USER_PLUGIN_ROOT") or "").strip()
    if not raw:
        roots = str(os.environ.get("ULTIMATE_PLUGIN_ROOTS") or os.environ.get("BACKEND_PLUGIN_ROOTS") or "").split(os.pathsep)
        raw = next((item for item in roots if str(item or "").strip()), "")
    if not raw:
        raw = os.path.abspath(os.path.join(os.getcwd(), "plugins"))
    root = Path(raw).expanduser().resolve()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _dependency_manifest_path() -> Path | None:
    raw = str(os.environ.get("ULTIMATE_PLUGIN_DEP_MANIFEST") or "").strip()
    if raw:
        path = Path(raw).expanduser()
        if path.is_file():
            return path
    return None


def _requirement_name(requirement: str) -> str:
    text = str(requirement or "").strip()
    if not text or text.startswith("-"):
        return ""
    return re.split(r"\s*(?:\[|==|>=|<=|~=|!=|>|<|=|;)\s*", text, maxsplit=1)[0].strip().lower().replace("_", "-")


def _manifest_requirements(payload: Dict[str, Any]) -> List[str]:
    packaging = dict(payload.get("packaging") or {})
    platform_key = "android" if _runtime_profile() == "android" else "external"
    section = dict(packaging.get(platform_key) or {})
    if section.get("pip_requirements"):
        return [str(item or "").strip() for item in section.get("pip_requirements") or [] if str(item or "").strip()]
    if platform_key == "external":
        pyinstaller = dict(packaging.get("pyinstaller") or {})
        return [str(item or "").strip() for item in pyinstaller.get("pip_requirements") or [] if str(item or "").strip()]
    return []


def _load_dependency_pool_names() -> set[str] | None:
    manifest_path = _dependency_manifest_path()
    if manifest_path is None:
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    names = payload.get("requirement_names")
    if isinstance(names, list):
        return {str(item or "").strip().lower().replace("_", "-") for item in names if str(item or "").strip()}
    return {_requirement_name(item) for item in payload.get("requirements") or [] if _requirement_name(item)}


def _validate_dependency_pool(payload: Dict[str, Any]) -> None:
    required = {_requirement_name(item) for item in _manifest_requirements(payload)}
    required = {item for item in required if item}
    if not required:
        return
    available = _load_dependency_pool_names()
    if available is None:
        raise ValueError("扩展依赖池清单不可用，请确认安装包为最新 external 构建并重启应用")
    missing = sorted(required - available)
    if missing:
        raise ValueError("扩展依赖未被当前安装包预置: " + ", ".join(missing))


def _validate_platform(payload: Dict[str, Any]) -> None:
    if _runtime_profile() != "android":
        return
    android_packaging = dict((dict(payload.get("packaging") or {})).get("android") or {})
    enabled = str(android_packaging.get("enabled") or "").strip().lower()
    if enabled not in {"1", "true", "yes", "on", "enabled"}:
        raise ValueError("该扩展未声明支持 Android")


def _safe_member_name(name: str) -> str:
    normalized = str(name or "").replace("\\", "/")
    if not normalized or normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"扩展包包含不安全路径: {name}")
    return normalized


def _safe_extract(zip_path: Path, target_dir: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            member_name = _safe_member_name(info.filename)
            if not member_name or member_name.endswith("/"):
                continue
            target_path = (target_dir / member_name).resolve()
            if target_dir.resolve() not in target_path.parents:
                raise ValueError(f"扩展包包含越界路径: {info.filename}")
        archive.extractall(target_dir)


def _parse_github_repo_url(url: str) -> Tuple[str, str, str]:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        raise ValueError("只支持 GitHub 仓库链接")
    parts = [urllib.parse.unquote(item) for item in parsed.path.strip("/").split("/") if item]
    if len(parts) < 2:
        raise ValueError("GitHub 链接缺少 owner/repo")
    owner = parts[0]
    repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
    ref = ""
    if len(parts) >= 4 and parts[2] == "tree":
        ref = "/".join(parts[3:])
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("GitHub 仓库名称不合法")
    return owner, repo, ref


def _download_url_to_file(url: str, target_path: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ULTIMATE_WEB-PluginInstaller/1.0",
            "Accept": "application/zip,application/octet-stream,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            target_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GitHub 下载失败: HTTP {exc.code}") from exc
    except Exception as exc:
        raise ValueError(f"GitHub 下载失败: {exc}") from exc


def _resolve_github_default_branch(owner: str, repo: str) -> str:
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    request = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "ULTIMATE_WEB-PluginInstaller/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        branch = str(payload.get("default_branch") or "").strip()
        return branch or "main"
    except Exception:
        return "main"


def _plugin_id(payload: Dict[str, Any]) -> str:
    return str((dict(payload.get("plugin") or {})).get("id") or "").strip()


def _safe_dir_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._-")
    return name or "plugin"


def _config_path() -> Path:
    from core.constants import THIRD_PARTY_CONFIG_PATH

    return Path(THIRD_PARTY_CONFIG_PATH).expanduser().resolve()


def _load_config_document() -> Dict[str, Any]:
    path = _config_path()
    if not path.is_file():
        return {"default_adapter": "", "adapters": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"default_adapter": "", "adapters": {}}
    except Exception:
        return {"default_adapter": "", "adapters": {}}


def _save_config_document(payload: Dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload or {}), ensure_ascii=False, indent=2), encoding="utf-8")


def _load_extension_sources() -> Dict[str, Dict[str, Any]]:
    sources = (_load_config_document().get("extension_sources") or {})
    if not isinstance(sources, dict):
        return {}
    return {
        str(plugin_id or "").strip(): dict(source or {})
        for plugin_id, source in sources.items()
        if str(plugin_id or "").strip() and isinstance(source, dict)
    }


def _save_extension_source(plugin_id: str, source: Dict[str, Any]) -> None:
    normalized_plugin_id = str(plugin_id or "").strip()
    if not normalized_plugin_id:
        return
    payload = _load_config_document()
    sources = payload.get("extension_sources")
    if not isinstance(sources, dict):
        sources = {}
        payload["extension_sources"] = sources
    sources[normalized_plugin_id] = dict(source or {})
    _save_config_document(payload)


def _package_roots(extract_dir: Path) -> List[Path]:
    children = [item for item in extract_dir.iterdir() if item.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        return [extract_dir, children[0]]
    return [extract_dir]


def _select_manifest(extract_dir: Path, manifests: List[Path]) -> Path:
    for root in _package_roots(extract_dir):
        manifest_path = root / "ultimate-plugin.json"
        if manifest_path in manifests:
            return manifest_path
    if len(manifests) == 1:
        return manifests[0]
    paths = ", ".join(str(path.relative_to(extract_dir)).replace("\\", "/") for path in manifests)
    raise ValueError("扩展包必须明确一个根 ultimate-plugin.json；发现多个: " + paths)


def _disable_nested_manifests(source_dir: Path, manifest_path: Path) -> List[str]:
    ignored: List[str] = []
    for nested_manifest in sorted(source_dir.rglob("ultimate-plugin.json")):
        if nested_manifest == manifest_path:
            continue
        ignored.append(str(nested_manifest.relative_to(source_dir)).replace("\\", "/"))
        nested_manifest.unlink()
    return ignored


def list_extensions() -> Dict[str, Any]:
    root = _install_root(create=False)
    installed: List[Dict[str, Any]] = []
    sources = _load_extension_sources()
    installed_ids = set()
    if not root.is_dir():
        return {
            "install_root": str(root),
            "installed": installed,
            "saved_sources": [
                {"plugin_id": plugin_id, **source, "installed": False}
                for plugin_id, source in sorted(sources.items())
            ],
            "requires_restart": True,
        }
    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        manifest_path = next(iter(sorted(child.rglob("ultimate-plugin.json"))), None)
        if manifest_path is None:
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        plugin = dict(payload.get("plugin") or {})
        plugin_id = str(plugin.get("id") or "").strip()
        if plugin_id:
            installed_ids.add(plugin_id)
        installed.append(
            {
                "plugin_id": plugin_id,
                "name": str(plugin.get("name") or plugin.get("id") or child.name).strip(),
                "version": str(plugin.get("version") or "").strip(),
                "directory": child.name,
                "source": sources.get(plugin_id) or {},
            }
        )
    return {
        "install_root": str(root),
        "installed": installed,
        "saved_sources": [
            {"plugin_id": plugin_id, **source, "installed": plugin_id in installed_ids}
            for plugin_id, source in sorted(sources.items())
        ],
        "requires_restart": True,
    }


def _install_extension_zip_path(zip_path: Path) -> Dict[str, Any]:
    root = _install_root(create=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".install-", dir=str(root))).resolve()
    try:
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        _safe_extract(zip_path, extract_dir)

        manifests = sorted(extract_dir.rglob("ultimate-plugin.json"))
        if not manifests:
            raise ValueError("扩展包缺少 ultimate-plugin.json")
        manifest_path = _select_manifest(extract_dir, manifests)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        plugin_id = _plugin_id(payload)
        if not plugin_id:
            raise ValueError("扩展 manifest 缺少 plugin.id")
        _validate_platform(payload)
        _validate_dependency_pool(payload)

        source_dir = manifest_path.parent.resolve()
        ignored_manifests = _disable_nested_manifests(source_dir, manifest_path)
        target_dir = (root / _safe_dir_name(plugin_id)).resolve()
        if root not in target_dir.parents:
            raise ValueError("扩展安装目录越界")
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(source_dir), str(target_dir))
        return {
            "plugin_id": plugin_id,
            "directory": target_dir.name,
            "ignored_manifests": ignored_manifests,
            "requires_restart": True,
            "message": "扩展安装成功，重启后生效",
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def install_extension_zip(file_storage) -> Dict[str, Any]:
    filename = str(getattr(file_storage, "filename", "") or "").strip()
    if not filename.lower().endswith(".zip"):
        raise ValueError("只支持安装 .zip 扩展包")

    root = _install_root(create=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".upload-", dir=str(root))).resolve()
    try:
        zip_path = temp_dir / "package.zip"
        file_storage.save(str(zip_path))
        return _install_extension_zip_path(zip_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def install_extension_from_github(url: str) -> Dict[str, Any]:
    owner, repo, ref = _parse_github_repo_url(url)
    resolved_ref = ref or _resolve_github_default_branch(owner, repo)
    archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/{urllib.parse.quote(resolved_ref, safe='/')}"
    root = _install_root(create=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".github-", dir=str(root))).resolve()
    try:
        zip_path = temp_dir / "repo.zip"
        _download_url_to_file(archive_url, zip_path)
        result = _install_extension_zip_path(zip_path)
        source = {
            "type": "github",
            "url": str(url or "").strip(),
            "owner": owner,
            "repo": repo,
            "ref": resolved_ref,
        }
        result["source"] = source
        _save_extension_source(str(result.get("plugin_id") or ""), source)
        return result
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def reinstall_saved_extension(plugin_id: str) -> Dict[str, Any]:
    normalized_plugin_id = str(plugin_id or "").strip()
    source = _load_extension_sources().get(normalized_plugin_id) or {}
    if str(source.get("type") or "").strip().lower() != "github" or not str(source.get("url") or "").strip():
        raise ValueError("该扩展没有已保存的 GitHub 安装链接")
    return install_extension_from_github(str(source.get("url") or "").strip())


def delete_extension(plugin_id: str) -> Dict[str, Any]:
    normalized_plugin_id = str(plugin_id or "").strip()
    if not normalized_plugin_id:
        raise ValueError("缺少扩展 plugin_id")
    root = _install_root(create=True)
    target_dir = (root / _safe_dir_name(normalized_plugin_id)).resolve()
    if root not in target_dir.parents:
        raise ValueError("扩展安装目录越界")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    return {
        "plugin_id": normalized_plugin_id,
        "deleted": True,
        "requires_restart": True,
        "message": "扩展代码已删除，配置已保留，重启后生效",
    }

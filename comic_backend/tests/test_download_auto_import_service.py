"""下载完成自动导入服务测试。

覆盖：
- 引擎启用了 auto_import_enabled 时，对 complete 任务以软链接模式导入
- 未启用自动导入的引擎被跳过
- 已处理任务（engine, gid）跨轮次去重
- 下载目录未就绪时跳过且不标记（可重试）
- 任务 dir 为空时回退到插件配置的 dir
- 导入模式归一化（soft -> softlink_ref）
- 状态持久化与重新加载
- 能力裁剪：引擎未声明 download.task.list 时整段跳过；未声明
  download.task.migrate 时只跳过迁移（文件本地移动不受影响）
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import application.download_auto_import_service as das
from protocol.download_features import resolve_download_features


class FakeConfigStore:
    def __init__(self, configs: dict):
        self.configs = configs

    def get_plugin_config(self, config_key: str) -> dict:
        return dict(self.configs.get(config_key, {}))


class FakeHost:
    def __init__(self, engines: list, plugin_configs: dict, completed_tasks: list,
                 per_engine_tasks: dict = None):
        self._engines = engines
        self._config_store = FakeConfigStore(plugin_configs)
        self._tasks = completed_tasks
        self._per_engine = per_engine_tasks or {}
        self.list_calls = 0
        self.migrate_calls = []

    def list_download_engines(self):
        self.list_calls += 1
        return list(self._engines)

    def execute_download_capability(self, engine_id, capability, params=None):
        params = params or {}
        if capability == "download.task.list":
            tasks = self._per_engine.get(engine_id, self._tasks)
            return engine_id, capability, {"tasks": list(tasks)}
        if capability == "download.task.migrate":
            gid = str(params.get("gid") or "")
            self.migrate_calls.append({
                "engine_id": engine_id,
                "gid": gid,
                "dir": str(params.get("dir") or ""),
            })
            self._drop_task(engine_id, gid)
            return engine_id, capability, {"gid": gid, "migrated": True, "dir": str(params.get("dir") or "")}
        raise AssertionError(f"不支持的 capability: {capability}")

    def _drop_task(self, engine_id, gid):
        """模拟 migrate 后原任务已删除，不再出现在任务列表中。"""
        pool = self._per_engine.get(engine_id)
        if pool is not None:
            self._per_engine[engine_id] = [
                t for t in pool if str(t.get("gid") or "") != str(gid or "")
            ]
        else:
            self._tasks = [
                t for t in self._tasks if str(t.get("gid") or "") != str(gid or "")
            ]


def _engine(plugin_id="download.qbittorrent", config_key="qbittorrent", name="qBittorrent"):
    return {"plugin_id": plugin_id, "config_key": config_key, "name": name}


def _task(gid="abc123", dir_path="", name="ABC-123"):
    return {"gid": gid, "dir": dir_path, "name": name}


def _service(host, state_path, poll_interval_seconds=3600):
    return das.DownloadAutoImportService(
        host=host,
        state_path=state_path,
        poll_interval_seconds=poll_interval_seconds,
        space_mode="normal",
    )


def test_imports_completed_task_with_softlink_mode(tmp_path, monkeypatch):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "softlink_ref"}},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append((source_path, import_mode))
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == [(str(download_dir), "softlink_ref")]
    # 状态已持久化
    assert "download.qbittorrent:abc123" in service._processed


def test_skips_engine_without_auto_import(tmp_path, monkeypatch):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": False}},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == []
    assert "download.qbittorrent:abc123" not in service._processed


def test_deduplicates_across_runs(tmp_path, monkeypatch):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": True}},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()
    service.run_once()

    assert calls == [str(download_dir)]


def test_skips_missing_directory_and_retries_later(tmp_path, monkeypatch):
    # 目录不存在：不导入、不标记，下一轮可重试
    missing_dir = tmp_path / "missing"
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": True}},
        completed_tasks=[_task(gid="abc123", dir_path=str(missing_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == []
    assert "download.qbittorrent:abc123" not in service._processed

    # 目录出现后，下一轮成功导入
    missing_dir.mkdir()
    service.run_once()
    assert calls == [str(missing_dir)]


def test_falls_back_to_plugin_config_dir(tmp_path, monkeypatch):
    config_dir = tmp_path / "config_dir"
    config_dir.mkdir()
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={
            "qbittorrent": {
                "auto_import_enabled": True,
                "dir": str(config_dir),
            }
        },
        completed_tasks=[_task(gid="abc123", dir_path="")],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == [str(config_dir)]


def test_import_mode_normalization(tmp_path, monkeypatch):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "soft"}},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(import_mode)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == ["softlink_ref"]


def test_state_loaded_from_disk(tmp_path, monkeypatch):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    state_path = tmp_path / "state.json"

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": {"auto_import_enabled": True}},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    # 第一次运行：处理并持久化
    first = _service(host, str(state_path))
    first.run_once()
    assert len(calls) == 1

    # 新实例（模拟重启）：从磁盘加载状态，不再重复导入
    second = _service(host, str(state_path))
    second.run_once()
    assert len(calls) == 1
    assert "download.qbittorrent:abc123" in second._processed


def test_multiple_engines_processed_independently(tmp_path, monkeypatch):
    qb_dir = tmp_path / "qb"
    qb_dir.mkdir()
    aria_dir = tmp_path / "aria"
    aria_dir.mkdir()
    host = FakeHost(
        engines=[_engine(), _engine(plugin_id="download.aria2", config_key="aria2", name="Aria2")],
        plugin_configs={
            "qbittorrent": {"auto_import_enabled": True},
            "aria2": {"auto_import_enabled": True},
        },
        completed_tasks=[],
        per_engine_tasks={
            "download.qbittorrent": [_task(gid="q1", dir_path=str(qb_dir))],
            "download.aria2": [_task(gid="a1", dir_path=str(aria_dir))],
        },
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert sorted(calls) == sorted([str(qb_dir), str(aria_dir)])
    assert "download.qbittorrent:q1" in service._processed
    assert "download.aria2:a1" in service._processed


# ---------- 自动归集（番号文件夹） ----------


def _organize_config(**overrides):
    config = {"auto_organize_enabled": True, "auto_import_enabled": False}
    config.update(overrides)
    return config


def test_organize_moves_into_existing_code_folder(tmp_path, monkeypatch):
    """下载目录已存在番号文件夹时，散文件直接移入"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    folder = download_dir / "ABC-123"
    folder.mkdir()
    loose = download_dir / "ABC-123 CD1.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )
    import_calls = []

    def fake_import(source_path, import_mode):
        import_calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    # 散文件已移入文件夹
    assert not loose.exists()
    assert list(folder.iterdir()) != []
    # 归集完成后标记 processed，无待确认
    assert "download.qbittorrent:abc123" in service._processed
    assert service.get_pending_organizations() == []
    assert import_calls == []


def test_organize_creates_pending_when_no_folder(tmp_path, monkeypatch):
    """下载目录无番号文件夹时，写入待确认且不导入、不标记"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "ABC-123.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )
    import_calls = []

    def fake_import(source_path, import_mode):
        import_calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    pending = service.get_pending_organizations()
    assert len(pending) == 1
    item = pending[0]
    assert item["id"] == "download.qbittorrent:abc123"
    assert item["code"] == "ABC-123"
    assert item["target_dir"] == str(download_dir / "ABC-123")
    # 不导入、不标记，等待用户决策
    assert import_calls == []
    assert "download.qbittorrent:abc123" not in service._processed
    assert loose.exists()


def test_confirm_organization_creates_folder_and_moves(tmp_path, monkeypatch):
    """确认后创建番号文件夹、移入散文件，并把下载任务迁移到新目录"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "ABC-123.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()
    org_id = service.get_pending_organizations()[0]["id"]

    ok, msg = service.confirm_organization(org_id)
    assert ok is True
    # 原任务通过 download.task.migrate 迁移到番号目录
    assert host.migrate_calls == [{
        "engine_id": "download.qbittorrent",
        "gid": "abc123",
        "dir": str(download_dir / "ABC-123"),
    }]
    assert "已重建 1 个下载任务" in msg
    folder = download_dir / "ABC-123"
    assert folder.is_dir()
    assert (folder / "ABC-123.mkv").exists()
    assert not loose.exists()
    assert service.get_pending_organizations() == []

    # 再次轮询：文件已在文件夹内，任务已迁移 → 直接处理完成
    service.run_once()
    assert "download.qbittorrent:abc123" in service._processed


def test_dismiss_organization_ignores_key(tmp_path, monkeypatch):
    """忽略后不再重复询问该任务"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "ABC-123.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()
    assert len(service.get_pending_organizations()) == 1

    ok, _msg = service.dismiss_organization("download.qbittorrent:abc123")
    assert ok is True
    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:abc123" in service._ignored

    # 再次轮询：不再生成 pending，也不处理
    service.run_once()
    assert service.get_pending_organizations() == []
    assert loose.exists()


def test_organize_skips_task_without_code(tmp_path, monkeypatch):
    """任务名无番号时跳过归集，正常处理（无 pending、无文件夹移动）"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "some random file.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="Some Movie")],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:abc123" in service._processed
    assert loose.exists()


def test_organize_skips_when_no_loose_file(tmp_path, monkeypatch):
    """下载目录中无匹配散文件时不生成 pending"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "XYZ-999.mkv").write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:abc123" in service._processed


# ---------- 按剧名分组归集（动漫剧集） ----------


def test_series_organize_creates_pending_when_no_folder(tmp_path, monkeypatch):
    """动漫剧集无番号时按剧名生成待确认"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip 1080p].mkv").write_bytes(b"a")
    (download_dir / "[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 02 [WebRip 1080p].mkv").write_bytes(b"b")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[
            _task(gid="s01", dir_path=str(download_dir), name="[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip 1080p HEVC-10bit AAC ASSx2]"),
        ],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    pending = service.get_pending_organizations()
    assert len(pending) == 1
    item = pending[0]
    assert item["code"] == "Katainaka no Ossan, Kensei ni Naru II"
    assert item["target_dir"] == str(download_dir / "Katainaka no Ossan, Kensei ni Naru II")
    # 两个同剧集散文件都应被收集
    assert len(item["files"]) == 2
    assert "download.qbittorrent:s01" not in service._processed


def test_series_organize_moves_into_existing_folder(tmp_path, monkeypatch):
    """下载目录已有剧名文件夹时，同剧集散文件移入"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    folder = download_dir / "Katainaka no Ossan, Kensei ni Naru II"
    folder.mkdir()
    loose = download_dir / "[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 02 [WebRip 1080p].mkv"
    loose.write_bytes(b"b")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[
            _task(gid="s02", dir_path=str(download_dir), name="[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 02 [WebRip 1080p HEVC-10bit AAC ASSx2]"),
        ],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert not loose.exists()
    assert any(folder.iterdir())
    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:s02" in service._processed


def test_series_organize_ignores_other_series(tmp_path, monkeypatch):
    """剧名归集不误伤其他剧集的文件"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip 1080p].mkv").write_bytes(b"a")
    (download_dir / "[SubGroup] Another Show - 01 [1080p].mkv").write_bytes(b"c")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[
            _task(gid="s03", dir_path=str(download_dir), name="[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip 1080p HEVC-10bit AAC ASSx2]"),
        ],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    pending = service.get_pending_organizations()
    assert len(pending) == 1
    assert len(pending[0]["files"]) == 1
    assert pending[0]["files"][0].startswith("[LoliHouse] Katainaka")
    # 另一剧集文件未被移动（仍存在）
    assert (download_dir / "[SubGroup] Another Show - 01 [1080p].mkv").exists()


def test_series_organize_skips_short_name(tmp_path, monkeypatch):
    """剧名过短（归一化 < 5 字符）时跳过归集"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "AB - 01.mkv").write_bytes(b"a")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[_task(gid="s04", dir_path=str(download_dir), name="AB - 01 [1080p]")],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:s04" in service._processed


def test_series_organize_skips_when_already_in_series_folder(tmp_path, monkeypatch):
    """任务已直接下载到剧名文件夹时跳过归集（创建任务时已指定子目录）"""
    series_dir = tmp_path / "downloads" / "Katainaka no Ossan, Kensei ni Naru II"
    series_dir.mkdir(parents=True)
    (series_dir / "01.mkv").write_bytes(b"a")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config()},
        completed_tasks=[
            _task(
                gid="s05",
                dir_path=str(series_dir),
                name="[LoliHouse] Katainaka no Ossan, Kensei ni Naru II - 01 [WebRip 1080p HEVC-10bit AAC ASSx2]",
            ),
        ],
    )

    def fake_import(source_path, import_mode):
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert service.get_pending_organizations() == []
    assert "download.qbittorrent:s05" in service._processed


# ---------- 归集决策后补自动导入（auto_organize + auto_import 同时开启） ----------


def test_dismiss_with_auto_import_imports_source_dir(tmp_path, monkeypatch):
    """忽略归集时若开启自动导入：文件保留原处，忽略后立即补导原目录。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "ABC-123.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config(auto_import_enabled=True)},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )
    import_calls = []

    def fake_import(source_path, import_mode):
        import_calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()
    assert len(service.get_pending_organizations()) == 1
    # 未决策前不导入
    assert import_calls == []

    ok, _msg = service.dismiss_organization("download.qbittorrent:abc123")
    assert ok is True
    # 忽略后仍补导原目录，任务进入 ignored 不再重复询问
    assert import_calls == [str(download_dir)]
    assert "download.qbittorrent:abc123" in service._ignored
    assert loose.exists()

    # 后续轮询不再重复导入或重复询问
    service.run_once()
    assert service.get_pending_organizations() == []
    assert import_calls == [str(download_dir)]


def test_confirm_with_auto_import_imports_target_folder(tmp_path, monkeypatch):
    """确认归集时若开启自动导入：文件移入新文件夹后立即导入该文件夹。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    loose = download_dir / "ABC-123.mkv"
    loose.write_bytes(b"data")

    host = FakeHost(
        engines=[_engine()],
        plugin_configs={"qbittorrent": _organize_config(auto_import_enabled=True)},
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir), name="ABC-123")],
    )
    import_calls = []

    def fake_import(source_path, import_mode):
        import_calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()
    org_id = service.get_pending_organizations()[0]["id"]

    ok, _msg = service.confirm_organization(org_id)
    assert ok is True
    folder = download_dir / "ABC-123"
    assert folder.is_dir()
    assert (folder / "ABC-123.mkv").exists()
    assert not loose.exists()
    # 确认后立即导入目标文件夹（而非依赖迁移任务再次下载完成才导入）
    assert import_calls == [str(folder)]
    assert "download.qbittorrent:abc123" in service._processed


# ---------- 能力裁剪（功能由引擎声明的能力决定） ----------

FULL_ENGINE_CAPABILITIES = [
    "download.magnet.add",
    "download.task.status",
    "download.task.list",
    "download.task.pause",
    "download.task.resume",
    "download.task.remove",
    "download.task.migrate",
    "health.query.status",
]
FULL_ENGINE_FIELDS = ["auto_import_enabled", "auto_organize_enabled"]


def _engine_with_feature_matrix(features, **overrides):
    engine = _engine(**overrides)
    engine["features"] = dict(features)
    engine["capabilities"] = []
    return engine


def _engine_with_capabilities(capabilities, fields=(), **overrides):
    """不带 features 的引擎：走 capabilities 兜底路径。"""
    engine = _engine(**overrides)
    engine["capabilities"] = list(capabilities)
    return engine


def test_engine_without_task_list_capability_is_skipped(tmp_path, monkeypatch):
    """只支持投递的引擎（如外部客户端桥接插件）不该被自动归集轮询触碰。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    features = resolve_download_features(["download.magnet.add"], [])
    host = FakeHost(
        engines=[_engine_with_feature_matrix(features)],
        plugin_configs={
            "qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "softlink_ref"}
        },
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == []
    assert not service._processed


def test_capabilities_fallback_also_gates_without_features_field(tmp_path, monkeypatch):
    """引擎字典只带 capabilities 时，兜底路径同样完成裁剪。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    host = FakeHost(
        engines=[_engine_with_capabilities(["download.magnet.add"])],
        plugin_configs={
            "qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "softlink_ref"}
        },
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == []


def test_auto_import_switch_ignored_when_engine_lacks_feature(tmp_path, monkeypatch):
    """用户打开了开关，但引擎未声明该功能 —— 不执行，也不报错。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    # 有 task.list，但没有 auto_import_enabled 字段 -> auto_import 功能不可用
    features = resolve_download_features(
        ["download.magnet.add", "download.task.list"], []
    )
    assert features["auto_import"] is False
    host = FakeHost(
        engines=[_engine_with_feature_matrix(features)],
        plugin_configs={
            "qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "softlink_ref"}
        },
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append(source_path)
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == []


def test_migrate_related_tasks_skips_engine_without_migrate_feature(tmp_path):
    """引擎未声明 download.task.migrate 时跳过迁移（文件本地移动已完成，不是故障）。"""
    features = resolve_download_features(
        ["download.magnet.add", "download.task.list"], []
    )
    assert features["migrate"] is False
    host = FakeHost(
        engines=[_engine_with_feature_matrix(features)],
        plugin_configs={},
        completed_tasks=[],
    )
    service = _service(host, str(tmp_path / "state.json"))
    target = str(tmp_path / "target")

    migrated = service._migrate_related_tasks(["download.qbittorrent:abc123"], target)

    assert migrated == 0
    assert host.migrate_calls == []


def test_migrate_related_tasks_proceeds_when_feature_unknown(tmp_path):
    """引擎信息未知（未带 features/capabilities）时保持原有行为，不静默丢功能。"""
    host = FakeHost(
        engines=[_engine()],
        plugin_configs={},
        completed_tasks=[],
    )
    service = _service(host, str(tmp_path / "state.json"))
    target = str(tmp_path / "target")

    migrated = service._migrate_related_tasks(["download.qbittorrent:abc123"], target)

    assert migrated == 1
    assert host.migrate_calls == [{
        "engine_id": "download.qbittorrent",
        "gid": "abc123",
        "dir": target,
    }]


def test_full_capability_engine_still_auto_imports(tmp_path, monkeypatch):
    """声明了全套能力的引擎行为不变（能力裁剪不误伤正常引擎）。"""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    features = resolve_download_features(FULL_ENGINE_CAPABILITIES, FULL_ENGINE_FIELDS)
    host = FakeHost(
        engines=[_engine_with_feature_matrix(features)],
        plugin_configs={
            "qbittorrent": {"auto_import_enabled": True, "auto_import_mode": "softlink_ref"}
        },
        completed_tasks=[_task(gid="abc123", dir_path=str(download_dir))],
    )
    calls = []

    def fake_import(source_path, import_mode):
        calls.append((source_path, import_mode))
        return SimpleNamespace(success=True, message="ok")

    monkeypatch.setattr(
        das.DownloadAutoImportService, "_import_video", staticmethod(fake_import)
    )

    service = _service(host, str(tmp_path / "state.json"))
    service.run_once()

    assert calls == [(str(download_dir), "softlink_ref")]

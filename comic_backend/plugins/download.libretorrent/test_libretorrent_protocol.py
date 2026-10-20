"""LibreTorrent 下载引擎插件的协议契约测试。

按 API_INTEGRATION_STANDARD.md 的约定，插件的契约测试随插件仓库维护。
在插件仓库内运行：

    python -m pytest tests -q

覆盖：
- manifest 合法性与「只声明一个能力」的边界；
- normalize_config 默认值；
- execute 的能力白名单、enabled 自检、非 Android 环境的可读失败；
- 磁力解析优先级（magnet > uris）与 dir/out 未生效时的如实回报；
- 宿主集成：本引擎被识别为「只支持投递」的下载引擎。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PLUGIN_DIR.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

MANIFEST_PATH = PLUGIN_DIR / "ultimate-plugin.json"
PLUGIN_ID = "download.libretorrent"
MAGNET = "magnet:?xt=urn:btih:abcdef0123456789"


def _load_provider_module():
    """按路径加载 provider，模块名唯一以免与其它插件的 ultimate_provider 撞名。"""
    module_name = "libretorrent_ultimate_provider_undertest"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_DIR / "ultimate_provider.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_runtime_module():
    """按路径加载 Android 适配层，模块名唯一避免与其它插件冲突。"""
    module_name = "libretorrent_android_runtime_undertest"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, PLUGIN_DIR / "libretorrent_android_runtime.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def provider():
    module = _load_provider_module()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return module.LibreTorrentProvider(manifest=manifest, manifest_path=str(MANIFEST_PATH))


class _FakeRuntime:
    """替身 Android 适配层：记录调用并返回固定结果。

    ``bridge=False`` 模拟桌面端（没有 Java 桥）；``error`` 模拟 Android 端上的
    运行时探测失败。两者语义不同，测试必须能区分——这正是状态逻辑的关键分支。
    """

    def __init__(self, error=None, bridge=True):
        self.calls = []
        self.error = error
        self.bridge = bridge

    def has_java_bridge(self):
        return self.bridge

    def android_context(self):
        return None if self.error else object()

    def unavailable_reason(self):
        return self.error or ""

    def is_package_installed(self, package_name):
        return True

    def start_download(self, uri, package_name):
        self.calls.append((uri, package_name))
        if self.error:
            raise RuntimeError(self.error)
        return {"added": True, "engine": package_name, "gid": None, "handoff": True}


# ---------- manifest ----------


def test_context_probe_reports_which_stage_failed():
    """非 Android 环境时，探测必须说清卡在哪一步，而不是一句含糊的「不可用」。

    真机上没有 adb 时，这条诊断会随投递失败的错误提示显示出来，直接指出是
    「没有 java 模块」「Python 未启动」还是「平台不是 AndroidPlatform」。
    """
    runtime = _load_runtime_module()
    context, detail = runtime.context_probe()
    assert context is None
    assert detail, "诊断信息不能为空"
    assert ("java" in detail) or ("Chaquopy" in detail)
    assert runtime.has_java_bridge() is False
    assert "Android" in runtime.unavailable_reason()


def test_manifest_declares_only_magnet_submission():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["plugin"]["id"] == PLUGIN_ID
    assert manifest["plugin"]["config_key"] == "libretorrent"
    assert manifest["plugin"]["entrypoint"] == "./ultimate_provider.py:LibreTorrentProvider"
    assert manifest["protocol_version"] == "1.0"

    # 这是本插件的核心边界：只有投递能力，因此宿主的界面裁剪会自动生效
    keys = [item["key"] for item in manifest["capabilities"]]
    assert keys == ["download.magnet.add"]
    assert not any(key.startswith("download.task.") for key in keys)

    # 必须声明 Android 支持，否则 supported 模式不会把它打进 APK
    android = manifest["packaging"]["android"]
    assert android["enabled"] is True


def test_manifest_declares_package_visibility_queries():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    queries = manifest["packaging"]["android"]["manifest_queries"]

    assert "org.proninyaroslav.libretorrent" in queries["packages"]
    actions = [item["action"] for item in queries["intents"]]
    assert "android.intent.action.VIEW" in actions


# ---------- 配置 ----------


def test_normalize_config_defaults(provider):
    config = provider.normalize_config({})
    assert config["enabled"] is True
    assert config["package_name"] == "org.proninyaroslav.libretorrent"


def test_normalize_config_respects_overrides(provider):
    config = provider.normalize_config({"enabled": "false", "package_name": "  com.example.bt  "})
    assert config["enabled"] is False
    assert config["package_name"] == "com.example.bt"


def test_serialize_public_config_has_no_secrets(provider):
    config = provider.serialize_public_config({"enabled": True})
    assert config["enabled"] is True
    assert "secret" not in json.dumps(config).lower()


# ---------- execute ----------


def test_execute_rejects_unsupported_capability(provider):
    with pytest.raises(ValueError, match="不支持能力"):
        provider.execute("download.task.list", {}, {}, {"enabled": True})


def test_execute_respects_own_enabled_flag(provider):
    with pytest.raises(RuntimeError, match="未启用"):
        provider.execute("download.magnet.add", {"magnet": MAGNET}, {}, {"enabled": False})


def test_execute_fails_readably_outside_android(provider, monkeypatch):
    module = _load_provider_module()
    monkeypatch.setattr(module, "load_android_runtime", lambda: _FakeRuntime(error="无 Java 桥"))

    with pytest.raises(RuntimeError, match="无 Java 桥"):
        provider.execute("download.magnet.add", {"magnet": MAGNET}, {}, {"enabled": True})


def test_execute_hands_off_magnet(provider, monkeypatch):
    module = _load_provider_module()
    runtime = _FakeRuntime()
    monkeypatch.setattr(module, "load_android_runtime", lambda: runtime)

    result = provider.execute(
        "download.magnet.add",
        {"magnet": MAGNET, "uris": ["http://example.com/other.torrent"]},
        {},
        {"enabled": True},
    )

    # 有 magnet 时优先用 magnet，不理会 uris
    assert runtime.calls == [(MAGNET, "org.proninyaroslav.libretorrent")]
    assert result["added"] is True
    assert result["handoff"] is True
    # 单向投递：LibreTorrent 自己管理任务，宿主拿不到 gid
    assert result["gid"] is None


def test_execute_falls_back_to_uris(provider, monkeypatch):
    module = _load_provider_module()
    runtime = _FakeRuntime()
    monkeypatch.setattr(module, "load_android_runtime", lambda: runtime)

    provider.execute(
        "download.magnet.add",
        {"uris": ["", "  http://example.com/a.torrent  "]},
        {},
        {"enabled": True},
    )
    assert runtime.calls == [("http://example.com/a.torrent", "org.proninyaroslav.libretorrent")]


def test_execute_requires_uri(provider, monkeypatch):
    module = _load_provider_module()
    monkeypatch.setattr(module, "load_android_runtime", lambda: _FakeRuntime())

    with pytest.raises(ValueError, match="缺少 magnet 或 uris"):
        provider.execute("download.magnet.add", {}, {}, {"enabled": True})


def test_execute_reports_ignored_dir_and_out(provider, monkeypatch):
    """宿主的投递接口带 dir/out，LibreTorrent 不接受——必须如实回报而非假装生效。"""
    module = _load_provider_module()
    monkeypatch.setattr(module, "load_android_runtime", lambda: _FakeRuntime())

    result = provider.execute(
        "download.magnet.add",
        {"magnet": MAGNET, "dir": "/downloads/ABC-123", "out": "ABC-123.mkv"},
        {},
        {"enabled": True},
    )
    assert result["ignored_params"] == {"dir": "/downloads/ABC-123", "out": "ABC-123.mkv"}
    assert "未生效" in result["warning"]


def test_execute_uses_custom_package_name(provider, monkeypatch):
    module = _load_provider_module()
    runtime = _FakeRuntime()
    monkeypatch.setattr(module, "load_android_runtime", lambda: runtime)

    provider.execute(
        "download.magnet.add", {"magnet": MAGNET}, {}, {"enabled": True, "package_name": "com.x.bt"}
    )
    assert runtime.calls == [(MAGNET, "com.x.bt")]


# ---------- status ----------


def test_query_status_reports_platform_limitation(provider, monkeypatch):
    """没有 Java 桥 = 明确不是 Android 端，才判为不可用。"""
    module = _load_provider_module()
    monkeypatch.setattr(
        module,
        "load_android_runtime",
        lambda: _FakeRuntime(error="只能在 Android 端使用", bridge=False),
    )
    status = provider.get_query_status({"enabled": True})
    assert status["configured"] is False
    assert "Android" in status["message"]


def test_query_status_keeps_engine_visible_when_context_probe_fails(provider, monkeypatch):
    """Android 端探测失败时**不能**报成未配置。

    宿主前端按 status.configured !== false 过滤可投递引擎，若把探测失败报成
    「未配置」，引擎会从界面上静默消失，用户看到的是「没有配置下载引擎」——
    而配置其实是好的。这里锁定修复后的语义：保持可见 + 用 message 说明。
    """
    module = _load_provider_module()
    monkeypatch.setattr(
        module, "load_android_runtime", lambda: _FakeRuntime(error="上下文探测失败")
    )
    status = provider.get_query_status({"enabled": True})
    assert status["configured"] is True
    assert "上下文" in status["message"]


def test_query_status_stays_configured_when_package_not_detected(provider, monkeypatch):
    """探测不到 LibreTorrent 时不能判为不可用：Android 11+ 可见性过滤会误报。"""
    module = _load_provider_module()

    class _Missing(_FakeRuntime):
        def is_package_installed(self, package_name):
            return False

    monkeypatch.setattr(module, "load_android_runtime", lambda: _Missing())
    status = provider.get_query_status({"enabled": True})
    assert status["configured"] is True
    assert "queries" in status["message"]


# ---------- 宿主集成 ----------


def test_host_sees_engine_as_submit_only(tmp_path):
    """关键断言：宿主把本引擎识别为「只支持投递」，其余功能全部为 False。

    这正是能力驱动裁剪要达成的效果——插件只声明真实能力，界面自动只剩投递入口。
    """
    from protocol.download_features import DOWNLOAD_FEATURE_ORDER
    from protocol.gateway import ProtocolGateway
    from protocol.host_service import ProtocolHostService
    from protocol.provider_manager import ProviderManager
    from protocol.registry import PluginRegistry
    from protocol.runtime_config import ProtocolConfigStore

    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps({"default_adapter": "", "adapters": {}}, ensure_ascii=False), encoding="utf-8"
    )
    store = ProtocolConfigStore(str(config_path))
    registry = PluginRegistry(search_root=str(PLUGIN_DIR.parent))
    manager = ProviderManager(registry=registry)
    manager._config_store = store
    host = ProtocolHostService(
        gateway=ProtocolGateway(registry=registry, provider_manager=manager),
        config_store=store,
    )

    engines = host.list_download_engines()
    engine = next((item for item in engines if item["plugin_id"] == PLUGIN_ID), None)
    assert engine is not None, "宿主未发现 LibreTorrent 引擎"

    features = engine["features"]
    assert set(features.keys()) == set(DOWNLOAD_FEATURE_ORDER)
    assert features["submit_magnet"] is True
    for name in DOWNLOAD_FEATURE_ORDER:
        if name == "submit_magnet":
            continue
        assert features[name] is False, name

    assert engine["capabilities"] == ["download.magnet.add"]
    assert engine["base_dir"] == ""

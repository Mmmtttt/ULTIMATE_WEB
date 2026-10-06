"""下载功能的「功能 ↔ 能力」裁剪测试。

覆盖两层：

1. 纯映射逻辑（download_features）：能力集合 + 配置字段 -> 功能矩阵。
2. 宿主集成（host_service）：引擎列表附 features、功能矩阵汇总形状。

关键契约：features 描述引擎「能做什么」（静态），与 status「现在能不能用」
（运行时）分离；缺失能力的功能一律为 False，界面据此裁剪按钮。
"""
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.download_features import (
    DOWNLOAD_FEATURE_ORDER,
    aggregate_download_features,
    is_download_engine,
    manifest_config_field_keys,
    resolve_download_features,
    unsupported_download_features,
)
from protocol.gateway import ProtocolGateway
from protocol.host_service import ProtocolHostService
from protocol.provider_manager import ProviderManager
from protocol.registry import PluginRegistry
from protocol.runtime_config import ProtocolConfigStore

THIRD_PARTY_ROOT = BACKEND_ROOT / "third_party"

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
FULL_ENGINE_FIELDS = [
    "enabled",
    "rpc_url",
    "dir",
    "auto_import_enabled",
    "auto_import_mode",
    "auto_organize_enabled",
]


def _make_host_service_for(search_root, tmp_path) -> ProtocolHostService:
    """构造 host service，插件配置指向临时文件（不依赖本机 third_party_config.json）。"""
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps({"default_adapter": "", "adapters": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    store = ProtocolConfigStore(str(config_path))
    registry = PluginRegistry(search_root=str(search_root))
    manager = ProviderManager(registry=registry)
    manager._config_store = store
    gateway = ProtocolGateway(registry=registry, provider_manager=manager)
    return ProtocolHostService(gateway=gateway, config_store=store)


def _make_host_service(tmp_path) -> ProtocolHostService:
    return _make_host_service_for(THIRD_PARTY_ROOT, tmp_path)


# ---------- 纯映射逻辑 ----------


def test_resolve_full_engine_supports_all_features():
    features = resolve_download_features(FULL_ENGINE_CAPABILITIES, FULL_ENGINE_FIELDS)
    assert all(features[feature] is True for feature in DOWNLOAD_FEATURE_ORDER)
    assert list(features.keys()) == list(DOWNLOAD_FEATURE_ORDER)


def test_resolve_magnet_only_engine_supports_submit_only():
    """只声明投递能力的引擎（如「链式启动外部客户端」的桥接插件）。"""
    features = resolve_download_features(["download.magnet.add"], [])
    assert features["submit_magnet"] is True
    for feature in DOWNLOAD_FEATURE_ORDER:
        if feature == "submit_magnet":
            continue
        assert features[feature] is False, feature


def test_auto_organize_requires_migrate_capability():
    """自动归集依赖 task.list + task.migrate，两者缺一不可。"""
    base = ["download.magnet.add", "download.task.list"]
    fields = ["auto_import_enabled", "auto_organize_enabled"]

    without_migrate = resolve_download_features(base, fields)
    assert without_migrate["auto_import"] is True
    assert without_migrate["auto_organize"] is False

    with_migrate = resolve_download_features(
        base + ["download.task.migrate"], fields
    )
    assert with_migrate["auto_organize"] is True


def test_auto_import_requires_declared_config_field():
    """引擎未声明开关字段时，用户无从开启，该功能不算可用。"""
    capabilities = ["download.magnet.add", "download.task.list"]
    assert resolve_download_features(capabilities, [])["auto_import"] is False
    assert (
        resolve_download_features(capabilities, ["auto_import_enabled"])["auto_import"]
        is True
    )


def test_capability_matching_ignores_case_and_whitespace():
    features = resolve_download_features(
        ["  Download.Magnet.Add  ", "DOWNLOAD.TASK.LIST", None, ""],
        ["  AUTO_IMPORT_ENABLED "],
    )
    assert features["submit_magnet"] is True
    assert features["task_list"] is True
    assert features["auto_import"] is True


def test_resolve_tolerates_none_inputs():
    features = resolve_download_features(None, None)
    assert all(value is False for value in features.values())


def test_aggregate_is_any_engine():
    magnet_only = resolve_download_features(["download.magnet.add"], [])
    full = resolve_download_features(FULL_ENGINE_CAPABILITIES, FULL_ENGINE_FIELDS)

    single = aggregate_download_features([magnet_only])
    assert single["submit_magnet"] is True
    assert single["pause"] is False

    combined = aggregate_download_features([magnet_only, full])
    assert all(combined[feature] is True for feature in DOWNLOAD_FEATURE_ORDER)


def test_aggregate_handles_empty_and_malformed():
    empty = aggregate_download_features([])
    assert all(value is False for value in empty.values())
    assert empty.keys() == set(DOWNLOAD_FEATURE_ORDER)

    mixed = aggregate_download_features([None, "not-a-mapping", {}, {"pause": True}])
    assert mixed["pause"] is True
    assert mixed["resume"] is False


def test_is_download_engine():
    assert is_download_engine(["download.magnet.add"]) is True
    assert is_download_engine(["Download.Magnet.Add"]) is True
    assert is_download_engine(["download.task.list"]) is False
    assert is_download_engine(None) is False


def test_unsupported_download_features_is_stable_and_ordered():
    features = resolve_download_features(["download.magnet.add"], [])
    unsupported = unsupported_download_features(features)
    assert "submit_magnet" not in unsupported
    assert unsupported == [
        feature for feature in DOWNLOAD_FEATURE_ORDER if feature != "submit_magnet"
    ]
    assert unsupported_download_features(None) == []


def test_manifest_config_field_keys_duck_typing():
    class _Manifest:
        def list_configuration_fields(self):
            return [{"key": "enabled"}, {"key": "  "}, {"no_key": 1}, None]

    assert manifest_config_field_keys(_Manifest()) == ["enabled"]

    class _Broken:
        def list_configuration_fields(self):
            raise RuntimeError("boom")

    assert manifest_config_field_keys(_Broken()) == []


# ---------- 宿主集成 ----------


def test_host_service_engines_expose_features(tmp_path):
    host = _make_host_service(tmp_path)
    engines = host.list_download_engines()
    ids = {engine["plugin_id"] for engine in engines}
    assert "download.aria2" in ids

    aria2 = next(engine for engine in engines if engine["plugin_id"] == "download.aria2")
    features = aria2["features"]
    # aria2 manifest 声明了全套 download.* 能力与自动归集配置字段
    assert features["submit_magnet"] is True
    assert features["task_list"] is True
    assert features["pause"] is True
    assert features["resume"] is True
    assert features["remove"] is True
    assert features["migrate"] is True
    assert features["auto_import"] is True
    assert features["auto_organize"] is True

    # features 与 status 是两件事：默认停用不影响「能做什么」的判定
    assert set(features.keys()) == set(DOWNLOAD_FEATURE_ORDER)


def test_host_service_feature_matrix_shape(tmp_path):
    host = _make_host_service(tmp_path)
    payload = host.list_download_features()

    assert set(payload.keys()) == {"features", "engines"}
    assert payload["features"]["submit_magnet"] is True
    assert payload["features"]["task_list"] is True

    assert payload["engines"], "至少应有一个下载引擎"
    for item in payload["engines"]:
        assert set(item.keys()) == {"plugin_id", "name", "features", "status"}
        assert set(item["features"].keys()) == set(DOWNLOAD_FEATURE_ORDER)


def test_feature_matrix_reflects_engine_capabilities(tmp_path):
    """汇总视图必须与逐引擎明细一致（任意引擎支持即可用）。"""
    host = _make_host_service(tmp_path)
    engines = host.list_download_engines()
    payload = host.list_download_features()

    expected = aggregate_download_features(
        engine.get("features") for engine in engines
    )
    assert payload["features"] == expected


# ---------- 新增引擎无需改宿主 ----------

MAGNET_ONLY_PROVIDER_SOURCE = '''
"""最小可用的「只支持投递」引擎：用于验证能力裁剪。"""


class MagnetOnlyProvider:
    def __init__(self, manifest=None, manifest_path=None):
        self.manifest = manifest or {}
        self.manifest_path = manifest_path

    def normalize_config(self, config):
        return dict(config or {})

    def serialize_public_config(self, config):
        return dict(config or {})

    def get_query_status(self, config):
        return {"configured": True, "message": "", "missing_fields": []}

    def execute(self, capability, params, context, config):
        return {"capability": capability, "added": True, "gid": "fake-gid"}
'''


def test_magnet_only_plugin_is_reported_as_submit_only(tmp_path):
    """只声明 download.magnet.add 的新引擎：能投递，但任务控制与自动归集全部为 False。

    这条用例是「新增引擎零宿主改动」的证明：插件只写 manifest + provider，
    宿主的 features 计算、接口、自动归集裁剪全部自动适配。
    """
    plugin_dir = tmp_path / "MagnetOnly"
    plugin_dir.mkdir()
    (plugin_dir / "ultimate-plugin.json").write_text(
        json.dumps(
            {
                "protocol_version": "1.0",
                "plugin": {
                    "id": "download.magnetonly",
                    "name": "MagnetOnly",
                    "version": "0.1.0",
                    "entrypoint": "./ultimate_provider.py:MagnetOnlyProvider",
                    "config_key": "magnetonly",
                },
                "media_types": ["video", "comic"],
                "capabilities": [{"key": "download.magnet.add"}],
                "configuration": {
                    "order": 80,
                    "label": "MagnetOnly",
                    "sections": [
                        {
                            "id": "basic",
                            "label": "基础配置",
                            "fields": [
                                {"key": "enabled", "label": "启用", "type": "boolean"},
                                {"key": "rpc_url", "label": "RPC 地址", "type": "text"},
                            ],
                        }
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "ultimate_provider.py").write_text(
        MAGNET_ONLY_PROVIDER_SOURCE, encoding="utf-8"
    )

    host = _make_host_service_for(tmp_path, tmp_path)
    engines = host.list_download_engines()

    assert [engine["plugin_id"] for engine in engines] == ["download.magnetonly"]
    features = engines[0]["features"]
    assert features["submit_magnet"] is True
    assert features["task_list"] is False
    assert features["task_status"] is False
    assert features["pause"] is False
    assert features["resume"] is False
    assert features["remove"] is False
    assert features["migrate"] is False
    assert features["auto_import"] is False
    assert features["auto_organize"] is False

    # 汇总视图同样反映该引擎的能力边界
    payload = host.list_download_features()
    assert payload["features"]["submit_magnet"] is True
    assert payload["features"]["pause"] is False
    assert unsupported_download_features(features) == [
        feature
        for feature in DOWNLOAD_FEATURE_ORDER
        if feature != "submit_magnet"
    ]

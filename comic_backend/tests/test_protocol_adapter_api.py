import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.adapter_api import ProtocolAdapterAPI


class _FakeConfigStore:
    def __init__(self, default_adapter="jmcomic", configs=None, legacy_keys=None):
        self._default_adapter = default_adapter
        self._configs = dict(configs or {})
        self._legacy_keys = list(legacy_keys or [])
        self.reset_calls = []

    def get_default_adapter(self):
        return self._default_adapter

    def set_default_adapter(self, adapter_name):
        self._default_adapter = adapter_name

    def get_adapter_config(self, adapter_name, reload=False):
        return dict(self._configs.get(adapter_name, {}) or {})

    def set_adapter_config(self, adapter_name, payload):
        self._configs[adapter_name] = dict(payload or {})

    def list_legacy_config_keys(self):
        return list(self._legacy_keys)

    def reset_runtime_caches(self, config_keys=None):
        self.reset_calls.append(list(config_keys or []))


class _FakeGateway:
    def __init__(self, manifests=None):
        self.executed = []
        self.legacy_clients = []
        self._manifests = list(manifests or [])

    def execute_plugin(self, plugin_id, capability, params=None, context=None):
        self.executed.append(
            {
                "plugin_id": plugin_id,
                "capability": capability,
                "params": dict(params or {}),
                "context": dict(context or {}),
            }
        )
        return {
            "plugin_id": plugin_id,
            "capability": capability,
            "params": dict(params or {}),
        }

    def get_legacy_client(self, plugin_id, *args, **kwargs):
        client = {
            "plugin_id": plugin_id,
            "args": args,
            "kwargs": kwargs,
        }
        self.legacy_clients.append(client)
        return client

    def list_manifests(self):
        return list(self._manifests)


def test_protocol_adapter_api_uses_default_adapter_for_search():
    gateway = _FakeGateway()
    config_store = _FakeConfigStore(default_adapter="jmcomic")
    api = ProtocolAdapterAPI(gateway=gateway, config_store=config_store)

    result = api.search_albums("keyword", page=2, max_pages=3, fast_mode=True)

    assert result["plugin_id"] == "comic.jmcomic"
    assert gateway.executed == [
        {
            "plugin_id": "comic.jmcomic",
            "capability": "catalog.search",
            "params": {
                "keyword": "keyword",
                "page": 2,
                "max_pages": 3,
                "fast_mode": True,
            },
            "context": {},
        }
    ]


def test_protocol_adapter_api_lists_manifest_and_legacy_keys_without_duplicates():
    gateway = _FakeGateway(
        manifests=[
            SimpleNamespace(config_key="jmcomic"),
            SimpleNamespace(config_key="picacomic"),
            SimpleNamespace(config_key="javdb"),
            SimpleNamespace(config_key=""),
        ]
    )
    config_store = _FakeConfigStore(legacy_keys=["jmcomic", "picacomic", "legacy_only"])
    api = ProtocolAdapterAPI(gateway=gateway, config_store=config_store)

    assert api.list_available_adapters() == ["javdb", "jmcomic", "legacy_only", "picacomic"]


def test_protocol_adapter_api_reset_adapter_refreshes_runtime_caches():
    gateway = _FakeGateway()
    config_store = _FakeConfigStore()
    api = ProtocolAdapterAPI(gateway=gateway, config_store=config_store)
    original_store = api.get_config_manager()

    api.reset_adapter("jmcomic")

    assert config_store.reset_calls == [["jmcomic"]]
    assert api.get_config_manager() is not original_store

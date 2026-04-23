import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.adapter_api import ProtocolAdapterAPI


class _FakeConfigStore:
    def __init__(self, default_adapter="jmcomic", configs=None, config_keys=None):
        self._default_adapter = default_adapter
        self._configs = dict(configs or {})
        self._config_keys = list(config_keys or [])
        self.reset_calls = []

    def get_default_adapter(self):
        return self._default_adapter

    def set_default_adapter(self, adapter_name):
        self._default_adapter = adapter_name

    def get_adapter_config(self, adapter_name, reload=False):
        return dict(self._configs.get(adapter_name, {}) or {})

    def set_adapter_config(self, adapter_name, payload):
        self._configs[adapter_name] = dict(payload or {})

    def list_config_keys(self):
        return list(self._config_keys)

    def reset_runtime_caches(self, config_keys=None):
        self.reset_calls.append(list(config_keys or []))


class _FakeGateway:
    def __init__(self, manifests=None):
        self.executed = []
        self.clients = []
        self._manifests = list(manifests or [])

    def _manifest_lookup_names(self, manifest):
        list_lookup_names = getattr(manifest, "list_lookup_names", None)
        if callable(list_lookup_names):
            return [str(item or "").strip().lower() for item in list_lookup_names() if str(item or "").strip()]
        return [str(getattr(manifest, "config_key", "") or "").strip().lower()]

    def get_manifest_by_config_key(self, config_key):
        lookup = str(config_key or "").strip().lower()
        for manifest in self._manifests:
            if str(getattr(manifest, "config_key", "") or "").strip().lower() == lookup:
                return manifest
        return None

    def get_manifest_by_lookup(self, lookup_name, media_type=None, capability=None):
        lookup = str(lookup_name or "").strip().lower()
        if not lookup:
            return None
        for manifest in self._manifests:
            if lookup in set(self._manifest_lookup_names(manifest)):
                return manifest
        return None

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

    def get_client(self, plugin_id, *args, **kwargs):
        client = {
            "plugin_id": plugin_id,
            "args": args,
            "kwargs": kwargs,
        }
        self.clients.append(client)
        return client

    def list_manifests(self):
        return list(self._manifests)


def _make_manifest(plugin_id, config_key, lookup_names):
    return SimpleNamespace(
        plugin_id=plugin_id,
        config_key=config_key,
        list_lookup_names=lambda: list(lookup_names),
    )


def test_protocol_adapter_api_uses_default_adapter_for_search():
    gateway = _FakeGateway(
        manifests=[
            _make_manifest("comic.jmcomic", "jmcomic", ["jmcomic", "JM"]),
        ]
    )
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


def test_protocol_adapter_api_lists_manifest_and_config_keys_without_duplicates():
    gateway = _FakeGateway(
        manifests=[
            _make_manifest("comic.jmcomic", "jmcomic", ["jmcomic"]),
            _make_manifest("comic.picacomic", "picacomic", ["picacomic"]),
            _make_manifest("video.javdb", "javdb", ["javdb"]),
            _make_manifest("video.no-config", "", ["video.no-config"]),
        ]
    )
    config_store = _FakeConfigStore(config_keys=["jmcomic", "picacomic", "config_only"])
    api = ProtocolAdapterAPI(gateway=gateway, config_store=config_store)

    assert api.list_available_adapters() == ["config_only", "javdb", "jmcomic", "picacomic"]


def test_protocol_adapter_api_reset_adapter_refreshes_runtime_caches():
    gateway = _FakeGateway()
    config_store = _FakeConfigStore()
    api = ProtocolAdapterAPI(gateway=gateway, config_store=config_store)
    original_store = api.get_config_manager()

    api.reset_adapter("jmcomic")

    assert config_store.reset_calls == [["jmcomic"]]
    assert api.get_config_manager() is not original_store

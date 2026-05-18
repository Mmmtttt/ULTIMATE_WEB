import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.host_service import ProtocolHostService


class _FakeConfigStore:
    def __init__(self, default_adapter="jmcomic"):
        self._default_adapter = default_adapter

    def get_default_adapter(self):
        return self._default_adapter


class _FakeGateway:
    def __init__(self, manifests=None):
        self._manifests = list(manifests or [])
        self.executed = []

    def get_manifest_by_lookup(self, lookup_name, capability=None):
        lookup = str(lookup_name or "").strip().lower()
        for manifest in self._manifests:
            candidates = {
                str(item or "").strip().lower()
                for item in manifest.list_lookup_names()
                if str(item or "").strip()
            }
            if lookup in candidates:
                return manifest
        return None

    def get_manifest_by_config_key(self, config_key):
        lookup = str(config_key or "").strip().lower()
        for manifest in self._manifests:
            if str(getattr(manifest, "config_key", "") or "").strip().lower() == lookup:
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
        return {"plugin_id": plugin_id, "capability": capability, "params": dict(params or {})}

    def get_query_status(self, plugin_id):
        return {"configured": True, "message": "", "missing_fields": [], "plugin_id": plugin_id}

    def list_manifests(self, media_type=None, capability=None):
        manifests = list(self._manifests)
        if media_type:
            manifests = [
                item
                for item in manifests
                if media_type in {str(mt or "").strip().lower() for mt in (getattr(item, "media_types", []) or [])}
            ]
        if capability:
            manifests = [item for item in manifests if item.has_capability(capability)]
        return manifests


def _make_manifest(plugin_id, config_key, lookup_names, media_types, capability_keys):
    return SimpleNamespace(
        plugin_id=plugin_id,
        config_key=config_key,
        media_types=list(media_types),
        list_lookup_names=lambda: list(lookup_names),
        has_capability=lambda capability: capability in set(capability_keys),
    )


def test_host_service_executes_comic_adapter_via_single_manifest_resolution():
    gateway = _FakeGateway(
        [
            _make_manifest(
                "comic.jmcomic",
                "jmcomic",
                ["jmcomic", "JM"],
                ["comic"],
                ["catalog.search"],
            )
        ]
    )
    service = ProtocolHostService(gateway=gateway, config_store=_FakeConfigStore())

    payload = service.execute_comic_adapter(
        "catalog.search",
        {"keyword": "alice", "page": 2, "max_pages": 3},
    )

    assert payload["plugin_id"] == "comic.jmcomic"
    assert gateway.executed == [
        {
            "plugin_id": "comic.jmcomic",
            "capability": "catalog.search",
            "params": {"keyword": "alice", "page": 2, "max_pages": 3},
            "context": {},
        }
    ]


def test_host_service_builds_video_client_from_protocol_manifest():
    gateway = _FakeGateway(
        [
            _make_manifest(
                "video.javdb",
                "javdb",
                ["javdb", "JAVDB"],
                ["video"],
                ["catalog.search", "catalog.detail"],
            )
        ]
    )
    service = ProtocolHostService(gateway=gateway, config_store=_FakeConfigStore())

    client = service.get_video_client("javdb")
    payload = client.search_videos("mio", page=1, max_pages=2)

    assert client.plugin_id == "video.javdb"
    assert payload["plugin_id"] == "video.javdb"
    assert gateway.executed[0]["capability"] == "catalog.search"

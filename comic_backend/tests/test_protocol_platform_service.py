import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.platform import Platform
from protocol.platform_service import PlatformService


class _FakeGateway:
    def __init__(self):
        self.executed = []
        self.legacy_clients = []

    def execute_plugin(self, plugin_id, capability, params=None, context=None):
        self.executed.append(
            {
                "plugin_id": plugin_id,
                "capability": capability,
                "params": dict(params or {}),
                "context": dict(context or {}),
            }
        )
        if capability == "asset.bundle.fetch":
            return {"detail": {"saved": 5}, "success": True}
        if capability == "asset.cover.fetch":
            return {"detail": {"saved": True}, "success": True}
        return {"ok": True}

    def get_legacy_client(self, plugin_id, *args, **kwargs):
        client = {
            "plugin_id": plugin_id,
            "args": args,
            "kwargs": kwargs,
        }
        self.legacy_clients.append(client)
        return client


def test_platform_service_routes_download_album_to_protocol_capability():
    service = PlatformService.__new__(PlatformService)
    service._gateway = _FakeGateway()
    service._initialized = True

    detail, success = service.download_album(
        Platform.JM,
        "1001",
        "D:/tmp/download",
        show_progress=False,
        decode_images=True,
    )

    assert success is True
    assert detail == {"saved": 5}
    assert service._gateway.executed == [
        {
            "plugin_id": "comic.jmcomic",
            "capability": "asset.bundle.fetch",
            "params": {
                "album_id": "1001",
                "download_dir": "D:/tmp/download",
                "show_progress": False,
                "extra": {"decode_images": True},
            },
            "context": {},
        }
    ]


def test_platform_service_uses_javdb_favorites_capability_for_basic_mode():
    service = PlatformService.__new__(PlatformService)
    service._gateway = _FakeGateway()
    service._initialized = True

    service.get_favorites_basic(Platform.JAVDB)

    assert service._gateway.executed == [
        {
            "plugin_id": "video.javdb",
            "capability": "collection.favorites",
            "params": {},
            "context": {},
        }
    ]

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.sync_directional_service import DirectionalSyncService


def test_peer_endpoint_adds_remote_space_mode_for_frontend_proxy():
    service = DirectionalSyncService()
    peer = {
        "remote_base_url": "https://192.168.1.88:5173",
        "remote_space_mode": "normal",
    }

    endpoint = service._peer_endpoint(peer, "/api/v1/sync/directional/inventory")

    assert endpoint == "https://192.168.1.88:5173/api/v1/sync/directional/inventory?space_mode=normal"


def test_endpoint_preserves_existing_query_and_space_mode():
    endpoint = DirectionalSyncService._endpoint(
        "https://host:5173",
        "/api/v1/sync/directional/delta?foo=bar",
        space_mode="private",
    )

    assert endpoint == "https://host:5173/api/v1/sync/directional/delta?foo=bar&space_mode=private"


def test_endpoint_does_not_duplicate_explicit_space_mode():
    endpoint = DirectionalSyncService._endpoint(
        "https://host:5173",
        "/api/v1/sync/directional/delta?space_mode=normal",
        space_mode="private",
    )

    assert endpoint == "https://host:5173/api/v1/sync/directional/delta?space_mode=normal"

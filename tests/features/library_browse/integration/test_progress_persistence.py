from __future__ import annotations

import json
import requests
import pytest

from tests.shared.test_constants import PRIMARY_COMIC_ID


def _load_comics(meta_dir):
    payload = json.loads((meta_dir / "comics_database.json").read_text(encoding="utf-8"))
    return payload.get("comics", [])


@pytest.mark.integration
def test_save_progress_updates_filesystem_and_response(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    detail_before = {
        "comic_id": PRIMARY_COMIC_ID,
        "current_page": None,
    }
    for comic in _load_comics(meta_dir):
        if comic.get("id") == PRIMARY_COMIC_ID:
            detail_before["current_page"] = comic.get("current_page")
            break

    assert detail_before["current_page"] == 1

    response = requests.put(
        f"{base_url}/api/v1/comic/progress",
        json={"comic_id": PRIMARY_COMIC_ID, "current_page": 2},
        timeout=5,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["comic_id"] == PRIMARY_COMIC_ID
    assert payload["data"]["current_page"] == 2

    comic_after = next((c for c in _load_comics(meta_dir) if c.get("id") == PRIMARY_COMIC_ID), None)
    assert comic_after is not None
    assert comic_after["current_page"] == 2

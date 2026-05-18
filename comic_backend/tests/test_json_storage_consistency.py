import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from infrastructure.persistence.json_storage import JsonStorage


def test_json_storage_singleton_uses_normalized_absolute_path(tmp_path):
    json_path = tmp_path / "sample.json"
    relative_like = json_path.parent / "." / json_path.name

    first = JsonStorage(str(json_path))
    second = JsonStorage(str(relative_like))

    assert first is second
    assert first.json_file == str(json_path.resolve())


def test_json_storage_creates_precise_default_video_recommendation_schema(tmp_path):
    json_path = tmp_path / "video_recommendations_database.json"
    storage = JsonStorage(str(json_path))

    payload = storage.read()

    assert payload["total_video_recommendations"] == 0
    assert payload["video_recommendations"] == []

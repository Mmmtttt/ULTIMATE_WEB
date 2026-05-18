import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from domain.recommendation import Recommendation
from domain.video_recommendation import VideoRecommendation


def test_recommendation_preserves_legacy_fields_while_using_base_content_rules():
    item = Recommendation(
        id="rec-001",
        title="Preview Item",
        author="Tester",
        total_page=5,
        current_page=2,
        score=8.0,
        tag_ids=["tag_b", "tag_a", "tag_a"],
        list_ids=["list_1", "list_1"],
    )

    item.add_tags(["tag_c", "tag_a"])
    assert item.author == "Tester"
    assert item.total_page == 5
    assert item.current_page == 2
    assert item.tag_ids == ["tag_b", "tag_a", "tag_c"]

    serialized = item.to_dict()
    assert serialized["author"] == "Tester"
    assert serialized["total_page"] == 5
    assert serialized["current_page"] == 2
    assert serialized["last_read_time"] == ""


def test_video_recommendation_uses_base_tag_normalization_and_roundtrips():
    item = VideoRecommendation.from_dict(
        {
            "id": "video-rec-001",
            "title": "Preview Video",
            "creator": "Actor A",
            "tag_ids": ["tag_2", "tag_1", "tag_1"],
            "list_ids": ["list_a", "list_a"],
            "actors": ["Actor A", "Actor A", "Actor B"],
            "code": "ABP-123",
        }
    )

    item.add_tags(["tag_3", "tag_2"])
    payload = item.to_dict()

    assert item.tag_ids == ["tag_2", "tag_1", "tag_3"]
    assert item.actors == ["Actor A", "Actor B"]
    assert payload["actors"] == ["Actor A", "Actor B"]
    assert payload["code"] == "ABP-123"

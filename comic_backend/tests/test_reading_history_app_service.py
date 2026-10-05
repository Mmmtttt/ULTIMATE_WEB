from application.reading_history_app_service import ReadingHistoryAppService


class FakeStorage:
    def __init__(self, initial=None):
        self.data = initial or {"history": {"comic": [], "video": []}}

    def read(self):
        return self.data

    def atomic_update(self, update_func, *args, **kwargs):
        del args, kwargs
        updated = update_func(self.data)
        if updated is None:
            return False
        self.data = updated
        return True


class FakeRepository:
    def __init__(self, items):
        self.items = items

    def get_by_id(self, entity_id):
        return self.items.get(entity_id)


class FakeContent:
    def __init__(self, entity_id, title):
        self.entity_id = entity_id
        self.title = title

    def to_dict(self):
        return {
            "id": self.entity_id,
            "title": self.title,
            "cover_path": f"/static/cover/{self.entity_id}.jpg",
            "score": 8,
            "tag_ids": [],
        }


def build_service(storage=None, comic_items=None, video_items=None):
    storage = storage or FakeStorage()
    return ReadingHistoryAppService(
        storage=storage,
        comic_repository=FakeRepository(comic_items or {}),
        recommendation_repository=FakeRepository(comic_items or {}),
        video_repository=FakeRepository(video_items or {}),
        video_recommendation_repository=FakeRepository(video_items or {}),
    ), storage


def test_record_history_keeps_comic_and_video_separate():
    service, storage = build_service(
        comic_items={"c1": FakeContent("c1", "漫画 1")},
        video_items={"v1": FakeContent("v1", "视频 1")},
    )

    assert service.record_visit("comic", "c1", "local").success is True
    assert service.record_visit("video", "v1", "local").success is True

    assert [item["id"] for item in storage.data["history"]["comic"]] == ["c1"]
    assert [item["id"] for item in storage.data["history"]["video"]] == ["v1"]


def test_record_history_deduplicates_same_source_and_moves_to_front():
    service, storage = build_service(
        comic_items={
            "c1": FakeContent("c1", "漫画 1"),
            "c2": FakeContent("c2", "漫画 2"),
        }
    )

    assert service.record_visit("comic", "c1", "local").success is True
    assert service.record_visit("comic", "c2", "local").success is True
    assert service.record_visit("comic", "c1", "local").success is True

    assert [item["id"] for item in storage.data["history"]["comic"]] == ["c1", "c2"]


def test_record_history_truncates_to_latest_thirty_per_type():
    comic_items = {
        f"c{i}": FakeContent(f"c{i}", f"漫画 {i}")
        for i in range(35)
    }
    service, storage = build_service(comic_items=comic_items)

    for i in range(35):
        assert service.record_visit("comic", f"c{i}", "local").success is True

    recorded_ids = [item["id"] for item in storage.data["history"]["comic"]]
    assert len(recorded_ids) == 30
    assert recorded_ids[0] == "c34"
    assert recorded_ids[-1] == "c5"


def test_record_history_rejects_missing_content():
    service, storage = build_service()

    result = service.record_visit("comic", "missing", "local")

    assert result.success is False
    assert storage.data["history"]["comic"] == []


def test_list_history_hydrates_existing_items_and_ignores_missing_items():
    storage = FakeStorage(
        {
            "history": {
                "comic": [
                    {"id": "c1", "source": "local", "visited_at": "2026-09-05T12:00:00"},
                    {"id": "missing", "source": "local", "visited_at": "2026-09-05T11:00:00"},
                ],
                "video": [],
            }
        }
    )
    service, _ = build_service(
        storage=storage,
        comic_items={"c1": FakeContent("c1", "漫画 1")},
    )

    result = service.list_history("comic")

    assert result.success is True
    assert result.data["total"] == 1
    assert result.data["items"][0]["id"] == "c1"
    assert result.data["items"][0]["content_type"] == "comic"
    assert result.data["items"][0]["source"] == "local"

import io

from application.softref_comic_reader import softref_comic_reader
from application.softref_reader_protocol import (
    get_softref_reader,
    register_softref_reader,
    require_softref_reader,
    softref_reader_registry,
)


class _DummyVideoSoftRefReader:
    content_type = "video"

    def is_soft_ref_content(self, content_id: str) -> bool:
        return str(content_id or "").startswith("VIDSOFT")

    def get_page_count(self, content_id: str) -> int:
        return 0

    def get_image_stream(self, content_id: str, page_num: int):
        return io.BytesIO(b""), "application/octet-stream"

    def set_archive_password(self, content_id: str, archive_fingerprint: str, password: str):
        return {"saved": True}

    def get_password_required_payload(self, content_id: str, exc: Exception):
        return {"content_id": content_id, "message": str(exc)}


def test_softref_comic_reader_registered_in_protocol_registry():
    reader = require_softref_reader("comic")
    assert reader is softref_comic_reader
    assert reader.content_type == "comic"
    assert hasattr(reader, "is_soft_ref_content")
    assert hasattr(reader, "get_page_count")
    assert hasattr(reader, "get_image_stream")


def test_softref_registry_supports_registering_new_content_type():
    dummy_reader = _DummyVideoSoftRefReader()
    register_softref_reader("video", dummy_reader)

    resolved = get_softref_reader("video")
    assert resolved is dummy_reader
    assert "video" in softref_reader_registry.list_content_types()
    assert resolved.is_soft_ref_content("VIDSOFT001")

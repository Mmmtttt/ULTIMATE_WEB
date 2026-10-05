from pathlib import Path

from application.lan_transfer_app_service import LanTransferAppService


class FakeStorage:
    def __init__(self, initial=None):
        self.data = initial or {"items": []}

    def read(self):
        return self.data

    def atomic_update(self, update_func, *args, **kwargs):
        del args, kwargs
        updated = update_func(self.data)
        if updated is None:
            return False
        self.data = updated
        return True


def test_publish_text_creates_downloadable_text_item():
    storage = FakeStorage()
    service = LanTransferAppService(storage=storage)

    result = service.publish_text("hello lan", "note.txt")

    assert result.success is True
    assert result.data["kind"] == "text"
    assert result.data["name"] == "note.txt"
    assert result.data["text"] == "hello lan"

    download = service.resolve_download(result.data["id"])
    assert download.success is True
    assert download.data["content"] == "hello lan"


def test_register_server_file_does_not_copy_or_delete_original(tmp_path):
    server_file = tmp_path / "server-file.txt"
    server_file.write_text("from server", encoding="utf-8")
    storage = FakeStorage()
    service = LanTransferAppService(storage=storage)

    result = service.register_server_file(str(server_file))
    assert result.success is True
    assert result.data["kind"] == "server_file"
    assert result.data["size"] == len("from server")

    download = service.resolve_download(result.data["id"])
    assert download.success is True
    assert Path(download.data["path"]) == server_file

    delete_result = service.delete_item(result.data["id"])
    assert delete_result.success is True
    assert server_file.exists()


def test_transfer_items_are_limited_to_latest_eighty():
    storage = FakeStorage()
    service = LanTransferAppService(storage=storage)

    for index in range(85):
        assert service.publish_text(f"text-{index}", f"{index}.txt").success is True

    items = storage.data["items"]
    assert len(items) == 80
    assert items[0]["name"] == "84.txt"
    assert items[-1]["name"] == "5.txt"


def test_missing_server_file_is_rejected(tmp_path):
    service = LanTransferAppService(storage=FakeStorage())

    result = service.register_server_file(str(tmp_path / "missing.zip"))

    assert result.success is False

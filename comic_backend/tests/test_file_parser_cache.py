import importlib
import importlib.util
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

utils_root = BACKEND_ROOT / "utils"
existing_utils = sys.modules.get("utils")
existing_utils_file = str(getattr(existing_utils, "__file__", "") or "")
if not existing_utils_file.startswith(str(utils_root)):
    spec = importlib.util.spec_from_file_location(
        "utils",
        utils_root / "__init__.py",
        submodule_search_locations=[str(utils_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["utils"] = module
    spec.loader.exec_module(module)


def test_parse_comic_images_reuses_short_lived_cache(tmp_path, monkeypatch):
    file_parser_module = importlib.import_module("utils.file_parser")
    parser = file_parser_module.FileParser()
    parser.IMAGE_CACHE_TTL_SECONDS = 3600

    comic_dir = tmp_path / "comic"
    comic_dir.mkdir()
    (comic_dir / "002.jpg").write_bytes(b"not-a-real-image")
    (comic_dir / "001.jpg").write_bytes(b"not-a-real-image")

    monkeypatch.setattr(parser, "_get_comic_dir", lambda _comic_id: str(comic_dir))

    sort_calls = {"count": 0}
    original_sort = parser.natural_sort_paths

    def counting_sort(paths, base_dir):
        sort_calls["count"] += 1
        return original_sort(paths, base_dir)

    monkeypatch.setattr(parser, "natural_sort_paths", counting_sort)

    first = parser.parse_comic_images("LOCAL-CACHE-CASE")
    second = parser.parse_comic_images("LOCAL-CACHE-CASE")

    assert first == second
    assert [Path(item).name for item in first] == ["001.jpg", "002.jpg"]
    assert sort_calls["count"] == 1

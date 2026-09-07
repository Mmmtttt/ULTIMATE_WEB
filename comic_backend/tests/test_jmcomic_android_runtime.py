import importlib.util
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = BACKEND_ROOT / "third_party" / "JMComic-Crawler-Python"
LIB_SRC_DIR = PLUGIN_ROOT / "lib" / "src"


def _load_jmcomic_api_module(monkeypatch):
    for path in (str(PLUGIN_ROOT), str(LIB_SRC_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)
    for name in ("jmcomic_api_android_test", "android_runtime", "jmcomic"):
        sys.modules.pop(name, None)

    monkeypatch.setenv("BACKEND_RUNTIME_PROFILE", "android")
    spec = importlib.util.spec_from_file_location(
        "jmcomic_api_android_test",
        PLUGIN_ROOT / "jmcomic_api.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load jmcomic_api.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_android_build_option_uses_safe_download_policy(monkeypatch, tmp_path):
    module = _load_jmcomic_api_module(monkeypatch)

    option = module._build_option(str(tmp_path), decode_images=True)

    assert option.download.dir == str(tmp_path)
    assert option.download.image.decode is True
    assert option.download.image.suffix == ".png"
    assert option.download.threading.image == 1
    assert option.download.threading.photo == 1


def test_android_build_option_allows_worker_overrides(monkeypatch, tmp_path):
    module = _load_jmcomic_api_module(monkeypatch)
    monkeypatch.setenv("JMCOMIC_ANDROID_IMAGE_WORKERS", "2")
    monkeypatch.setenv("JMCOMIC_ANDROID_PHOTO_WORKERS", "3")
    monkeypatch.setenv("JMCOMIC_ANDROID_IMAGE_SUFFIX", "jpg")

    option = module._build_option(str(tmp_path), decode_images=False)

    assert option.download.image.decode is False
    assert option.download.image.suffix == ".jpg"
    assert option.download.threading.image == 2
    assert option.download.threading.photo == 3

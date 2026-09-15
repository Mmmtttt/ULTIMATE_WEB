import gc
import json
import logging
import os
import platform
import sys
import threading
import time
import traceback


_ANDROID_LOG_HANDLER = None
_ACTIVE_LOG_PATH = None
_LOG_PATHS = []
_LOG_LOCK = threading.RLock()
_SAFE_DOWNLOADER_CLASS = None


class _SafeLogFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "topic"):
            record.topic = "python"
        return super().format(record)


class _FsyncFileHandler(logging.FileHandler):
    """Flush every log record to disk so abrupt process/device death keeps useful traces."""

    def emit(self, record):
        super().emit(record)
        try:
            self.flush()
            if self.stream is not None:
                os.fsync(self.stream.fileno())
        except Exception:
            # Diagnostics must never break the download path.
            pass


def _configure_jm_file_logging(log_path):
    global _ANDROID_LOG_HANDLER, _ACTIVE_LOG_PATH

    log_path = os.path.abspath(log_path)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    with _LOG_LOCK:
        from jmcomic.jm_config import jm_logger

        old = _ANDROID_LOG_HANDLER
        if old is not None:
            try:
                jm_logger.removeHandler(old)
                old.close()
            except Exception:
                pass

        handler = _FsyncFileHandler(log_path, mode="a", encoding="utf-8")
        handler._android_demo_file_handler = True
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            _SafeLogFormatter(
                "[%(asctime)s] [%(threadName)s] %(levelname)s [%(topic)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        jm_logger.addHandler(handler)
        jm_logger.setLevel(logging.INFO)

        _ANDROID_LOG_HANDLER = handler
        _ACTIVE_LOG_PATH = log_path
        if log_path not in _LOG_PATHS:
            _LOG_PATHS.append(log_path)


def _log(topic, message, level=logging.INFO, exc_info=False):
    try:
        from jmcomic.jm_config import jm_logger

        jm_logger.log(
            level,
            message,
            extra={"topic": topic},
            exc_info=exc_info,
        )
    except Exception:
        # Last-resort fallback for failures while the logging system itself is being set up.
        try:
            if _ACTIVE_LOG_PATH:
                with open(_ACTIVE_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{topic}] {message}\n")
                    f.flush()
                    os.fsync(f.fileno())
        except Exception:
            pass


def _mib(value):
    return round(float(value) / (1024 * 1024), 1)


def _resource_snapshot():
    """Return a compact process/Java/native memory snapshot for the log."""
    parts = []

    try:
        wanted = {"VmRSS", "VmHWM", "VmSize", "VmSwap", "Threads"}
        with open("/proc/self/status", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                key = line.split(":", 1)[0]
                if key in wanted:
                    parts.append(line.strip())
    except Exception as exc:
        parts.append(f"proc_status_error={exc!r}")

    try:
        from java.lang import Runtime

        runtime = Runtime.getRuntime()
        java_total = int(runtime.totalMemory())
        java_free = int(runtime.freeMemory())
        java_max = int(runtime.maxMemory())
        java_used = java_total - java_free
        parts.append(
            f"java_heap={_mib(java_used)}MiB/{_mib(java_max)}MiB "
            f"(total={_mib(java_total)}MiB free={_mib(java_free)}MiB)"
        )
    except Exception as exc:
        parts.append(f"java_heap_error={exc!r}")

    try:
        from android.os import Debug

        parts.append(
            f"native_heap={_mib(int(Debug.getNativeHeapAllocatedSize()))}MiB"
        )
    except Exception as exc:
        parts.append(f"native_heap_error={exc!r}")

    return "; ".join(parts)


def _looks_like_webp(data):
    return (
        isinstance(data, (bytes, bytearray))
        and len(data) >= 12
        and data[:4] == b"RIFF"
        and data[8:12] == b"WEBP"
    )


def _decode_webp_with_android(data):
    """Decode WebP with Android BitmapFactory, then hand PNG bytes back to Pillow."""
    from io import BytesIO

    from android.graphics import Bitmap, BitmapFactory
    from java import jarray, jbyte
    from java.io import ByteArrayOutputStream
    from PIL import Image

    raw_size = len(data)
    t0 = time.perf_counter()
    bitmap = None
    output = None

    _log(
        "android.webp.begin",
        f"WebP fallback start: input={raw_size} bytes; {_resource_snapshot()}",
    )

    try:
        java_bytes = jarray(jbyte)(data)
        t_java_bytes = time.perf_counter()

        bitmap = BitmapFactory.decodeByteArray(java_bytes, 0, len(java_bytes))
        # Release the duplicated Java input byte array as early as possible.
        del java_bytes
        t_bitmap = time.perf_counter()

        if bitmap is None:
            raise ValueError("Android BitmapFactory 无法解码该 WebP 图片")

        width = int(bitmap.getWidth())
        height = int(bitmap.getHeight())
        try:
            bitmap_alloc = int(bitmap.getAllocationByteCount())
        except Exception:
            bitmap_alloc = width * height * 4

        _log(
            "android.webp.bitmap",
            f"Bitmap decoded: {width}x{height}, approx={_mib(bitmap_alloc)}MiB, "
            f"python_to_java_ms={(t_java_bytes - t0) * 1000:.1f}, "
            f"bitmap_decode_ms={(t_bitmap - t_java_bytes) * 1000:.1f}; "
            f"{_resource_snapshot()}",
        )

        output = ByteArrayOutputStream()
        ok = bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
        t_png = time.perf_counter()
        if not ok:
            raise ValueError("Android Bitmap.compress(PNG) 失败")

        png_size = int(output.size())

        # The bitmap is by far the largest Java/native allocation. Release it before
        # duplicating PNG bytes into Python/Pillow memory.
        bitmap.recycle()
        bitmap = None

        java_png = output.toByteArray()
        output.close()
        output = None
        png_bytes = bytes(java_png)
        del java_png
        t_python_png = time.perf_counter()

        image = Image.open(BytesIO(png_bytes))
        image.load()
        del png_bytes
        t_pillow = time.perf_counter()

        _log(
            "android.webp.end",
            f"WebP fallback done: {width}x{height}, input={raw_size} bytes, "
            f"intermediate_png={png_size} bytes, android_png_ms={(t_png - t_bitmap) * 1000:.1f}, "
            f"java_to_python_ms={(t_python_png - t_png) * 1000:.1f}, "
            f"pillow_png_decode_ms={(t_pillow - t_python_png) * 1000:.1f}, "
            f"total_ms={(t_pillow - t0) * 1000:.1f}; {_resource_snapshot()}",
        )
        return image

    except Exception:
        _log(
            "android.webp.failed",
            f"WebP fallback failed after {(time.perf_counter() - t0) * 1000:.1f} ms; "
            f"input={raw_size} bytes; {_resource_snapshot()}",
            level=logging.ERROR,
            exc_info=True,
        )
        raise
    finally:
        if bitmap is not None:
            try:
                bitmap.recycle()
            except Exception:
                pass
        if output is not None:
            try:
                output.close()
            except Exception:
                pass


def _install_android_webp_fallback():
    """Patch jmcomic's image open path only for real WebP byte streams."""
    from PIL import UnidentifiedImageError
    from jmcomic.jm_toolkit import JmImageTool

    if getattr(JmImageTool, "_android_webp_fallback_installed", False):
        return

    original_open_image = JmImageTool.open_image

    def patched_open_image(cls, fp):
        try:
            return original_open_image(fp)
        except UnidentifiedImageError:
            # jmcomic passes downloaded image bytes here. If this isn't actually
            # a WebP stream, keep the original exception so CDN/HTTP problems
            # aren't accidentally hidden by the Android fallback.
            if isinstance(fp, str):
                raise

            raw = bytes(fp)
            if not _looks_like_webp(raw):
                _log(
                    "android.image.invalid",
                    f"Pillow rejected non-WebP bytes: size={len(raw)}, head={raw[:32]!r}",
                    level=logging.ERROR,
                )
                raise

            return _decode_webp_with_android(raw)

    JmImageTool.open_image = classmethod(patched_open_image)
    JmImageTool._android_webp_fallback_installed = True


def _get_android_safe_downloader_class():
    global _SAFE_DOWNLOADER_CLASS
    if _SAFE_DOWNLOADER_CLASS is not None:
        return _SAFE_DOWNLOADER_CLASS

    from jmcomic.jm_downloader import JmDownloader

    class AndroidSafeDownloader(JmDownloader):
        """JmDownloader with per-photo logs and aggressive resource diagnostics."""

        def __init__(self, option):
            super().__init__(option)
            self.android_log_paths = []
            self._image_started_at = {}

        def before_album(self, album):
            _log(
                "android.album.begin",
                f"Album ready: id={getattr(album, 'id', None)}, title={getattr(album, 'name', None)!r}, "
                f"photos={len(album)}, page_count={getattr(album, 'page_count', None)}; "
                f"{_resource_snapshot()}",
            )
            return super().before_album(album)

        def before_photo(self, photo):
            # This is the exact directory in which this photo/chapter's images are saved.
            image_dir = self.option.decide_image_save_dir(photo, ensure_exists=True)
            log_path = os.path.join(image_dir, "jmcomic_android.log")
            _configure_jm_file_logging(log_path)
            if log_path not in self.android_log_paths:
                self.android_log_paths.append(log_path)

            _log(
                "android.photo.begin",
                f"Photo start: id={getattr(photo, 'id', None)}, name={getattr(photo, 'name', None)!r}, "
                f"images={len(photo)}, image_dir={image_dir!r}, "
                f"threading.image={self.option.download.threading.image}, "
                f"threading.photo={self.option.download.threading.photo}, "
                f"output_suffix={self.option.download.image.suffix!r}; {_resource_snapshot()}",
            )
            return super().before_photo(photo)

        def before_image(self, image, img_save_path):
            self._image_started_at[id(image)] = time.perf_counter()
            _log(
                "android.image.begin",
                f"Image start: index={getattr(image, 'index', None)}, "
                f"url={getattr(image, 'img_url', None)!r}, save={img_save_path!r}; "
                f"{_resource_snapshot()}",
            )
            return super().before_image(image, img_save_path)

        def after_image(self, image, img_save_path):
            result = super().after_image(image, img_save_path)
            started = self._image_started_at.pop(id(image), None)
            duration_ms = None if started is None else (time.perf_counter() - started) * 1000
            try:
                file_size = os.path.getsize(img_save_path)
            except Exception:
                file_size = None

            collected = gc.collect()
            _log(
                "android.image.end",
                f"Image saved: index={getattr(image, 'index', None)}, save={img_save_path!r}, "
                f"file_size={file_size}, duration_ms={duration_ms}, gc_collected={collected}; "
                f"{_resource_snapshot()}",
            )
            return result

        def after_photo(self, photo):
            result = super().after_photo(photo)
            _log(
                "android.photo.end",
                f"Photo complete: id={getattr(photo, 'id', None)}, name={getattr(photo, 'name', None)!r}; "
                f"{_resource_snapshot()}",
            )
            return result

        def after_album(self, album):
            result = super().after_album(album)
            _log(
                "android.album.end",
                f"Album complete: id={getattr(album, 'id', None)}; {_resource_snapshot()}",
            )
            return result

    AndroidSafeDownloader.__name__ = "AndroidSafeDownloader"
    _SAFE_DOWNLOADER_CLASS = AndroidSafeDownloader
    return AndroidSafeDownloader


def diagnostics():
    info = {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }

    try:
        import curl_cffi
        info["curl_cffi"] = getattr(curl_cffi, "__version__", "unknown")
    except Exception:
        info["curl_cffi_error"] = traceback.format_exc()

    try:
        import PIL
        from PIL import features

        info["pillow"] = getattr(PIL, "__version__", "unknown")
        info["pillow_webp"] = bool(features.check("webp"))
    except Exception:
        info["pillow_error"] = traceback.format_exc()

    try:
        from android.graphics import BitmapFactory

        info["android_bitmapfactory"] = "available"
    except Exception:
        info["android_bitmapfactory_error"] = traceback.format_exc()

    try:
        import jmcomic

        info["jmcomic"] = getattr(jmcomic, "__version__", "import ok")
        _install_android_webp_fallback()
        info["android_webp_fallback"] = "installed"
        defaults = jmcomic.JmOption.default()
        info["jmcomic_default_image_threads"] = defaults.download.threading.image
        info["android_safe_image_threads"] = 1
        info["android_safe_photo_threads"] = 1
        info["android_output_suffix"] = ".png"
    except Exception:
        info["jmcomic_error"] = traceback.format_exc()

    info["resources"] = _resource_snapshot()
    return json.dumps(info, ensure_ascii=False, indent=2)


def download_album_by_id(jm_id, output_dir):
    global _LOG_PATHS

    jm_id = str(jm_id).strip()
    if not jm_id.isdigit():
        return json.dumps(
            {"ok": False, "error": f"无效 JM ID: {jm_id!r}"},
            ensure_ascii=False,
            indent=2,
        )

    os.makedirs(output_dir, exist_ok=True)
    _LOG_PATHS = []

    try:
        import jmcomic

        # Start a bootstrap log before album metadata is available. Once a chapter
        # starts, logging switches to jmcomic_android.log inside the actual image dir.
        bootstrap_log = os.path.join(output_dir, f"JM{jm_id}_android_bootstrap.log")
        _configure_jm_file_logging(bootstrap_log)

        _log(
            "android.download.begin",
            f"Download request: JM{jm_id}, output_dir={output_dir!r}, "
            f"python={sys.version.split()[0]}, jmcomic={getattr(jmcomic, '__version__', 'unknown')}; "
            f"{_resource_snapshot()}",
        )

        # Chaquopy's Pillow build doesn't include WebP. JM serves many pages as
        # WebP, so route genuine WebP bytes through Android's BitmapFactory.
        _install_android_webp_fallback()

        # IMPORTANT: jmcomic 2.7.5 defaults to 30 image threads. That is suitable
        # for desktop networking, but disastrous here because each WebP fallback
        # temporarily allocates a Java Bitmap + PNG buffer + Pillow image. Serialize
        # both photo and image work until resource measurements prove higher values safe.
        # Also save as PNG, because this Pillow build cannot encode WebP either.
        option = jmcomic.JmOption.construct({
            "dir_rule": {
                "base_dir": output_dir,
            },
            "download": {
                "threading": {
                    "image": 1,
                    "photo": 1,
                },
                "image": {
                    "decode": True,
                    "suffix": ".png",
                },
            },
        })

        _log(
            "android.download.config",
            "Android safe mode enabled: image_threads=1, photo_threads=1, "
            "decode=True, final_suffix='.png'",
        )

        downloader_cls = _get_android_safe_downloader_class()
        result = jmcomic.download_album(jm_id, option, downloader=downloader_cls)
        album = result.detail
        downloader = result.downloader

        log_paths = list(dict.fromkeys(_LOG_PATHS + getattr(downloader, "android_log_paths", [])))
        manifest_paths = list(getattr(result.manifest, "image_filepath_list", []) or [])

        _log(
            "android.download.end",
            f"Download complete: JM{jm_id}, images={len(manifest_paths)}, "
            f"duration={getattr(result, 'duration', None)}; {_resource_snapshot()}",
        )

        payload = {
            "ok": True,
            "jm_id": jm_id,
            "title": getattr(album, "title", None),
            "save_path": getattr(album, "save_path", output_dir),
            "downloaded_images": len(manifest_paths),
            "duration_seconds": getattr(result, "duration", None),
            "log_files": log_paths,
            "message": "下载完成（Android 安全模式：单线程解码，最终保存为 PNG）",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        _log(
            "android.download.failed",
            f"Download failed: JM{jm_id}; {_resource_snapshot()}",
            level=logging.ERROR,
            exc_info=True,
        )
        return json.dumps(
            {
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "log_files": list(_LOG_PATHS),
                "active_log": _ACTIVE_LOG_PATH,
            },
            ensure_ascii=False,
            indent=2,
        )

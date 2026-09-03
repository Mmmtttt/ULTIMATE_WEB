import json
import os
import platform
import sys
import traceback


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

    java_bytes = jarray(jbyte)(data)
    bitmap = BitmapFactory.decodeByteArray(java_bytes, 0, len(java_bytes))
    if bitmap is None:
        raise ValueError("Android BitmapFactory 无法解码该 WebP 图片")

    output = ByteArrayOutputStream()
    try:
        ok = bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)
        if not ok:
            raise ValueError("Android Bitmap.compress(PNG) 失败")
        png_bytes = bytes(output.toByteArray())
    finally:
        bitmap.recycle()
        output.close()

    image = Image.open(BytesIO(png_bytes))
    # Pillow is lazy by default. Load now so the in-memory PNG stream can be released.
    image.load()
    return image


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
                raise

            return _decode_webp_with_android(raw)

    JmImageTool.open_image = classmethod(patched_open_image)
    JmImageTool._android_webp_fallback_installed = True


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
    except Exception:
        info["jmcomic_error"] = traceback.format_exc()

    return json.dumps(info, ensure_ascii=False, indent=2)


def download_album_by_id(jm_id, output_dir):
    try:
        jm_id = str(jm_id).strip()
        if not jm_id.isdigit():
            raise ValueError(f"无效 JM ID: {jm_id!r}")

        os.makedirs(output_dir, exist_ok=True)

        import jmcomic

        # Chaquopy's Pillow build doesn't include every desktop image codec.
        # JM currently serves many pages as WebP, so route only genuine WebP
        # byte streams through Android's native BitmapFactory decoder.
        _install_android_webp_fallback()

        # 只覆盖下载根目录，其余使用 jmcomic 默认配置。
        # 当前默认网络层会走 curl_cffi，因此该调用同时验证了 native wheel 是否可用。
        option = jmcomic.JmOption.construct({
            "dir_rule": {
                "base_dir": output_dir,
            },
        })

        result = jmcomic.download_album(jm_id, option)
        album = result.detail

        payload = {
            "ok": True,
            "jm_id": jm_id,
            "title": getattr(album, "title", None),
            "save_path": getattr(album, "save_path", output_dir),
            "duration_seconds": getattr(result, "duration", None),
            "message": "下载完成",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            },
            ensure_ascii=False,
            indent=2,
        )

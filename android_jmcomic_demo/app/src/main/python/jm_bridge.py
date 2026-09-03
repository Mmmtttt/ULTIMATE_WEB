import json
import os
import platform
import sys
import traceback


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
        import jmcomic
        info["jmcomic"] = getattr(jmcomic, "__version__", "import ok")
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

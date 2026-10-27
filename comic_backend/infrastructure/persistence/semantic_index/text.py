from __future__ import annotations

import threading
from typing import Optional

_lock = threading.Lock()
_t2s = None  # False = 不可用（未安装 opencc），None = 未初始化


def _converter():
    global _t2s
    if _t2s is None:
        with _lock:
            if _t2s is None:
                try:
                    from opencc import OpenCC  # 可选依赖：简体/繁体归一

                    _t2s = OpenCC("t2s")
                except Exception:
                    _t2s = False
    return _t2s


def normalize(text: str) -> str:
    """检索用的文本归一：转小写 + 繁体转简体（opencc 缺失时只做小写）。"""
    value = str(text or "").strip().lower()
    if not value:
        return ""
    converter = _converter()
    if converter:
        try:
            value = converter.convert(value)
        except Exception:
            pass
    return value


def normalize_text(value: Optional[str]) -> str:
    return normalize(value or "")

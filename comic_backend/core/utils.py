import time
import uuid
from datetime import datetime


def generate_id(prefix: str) -> str:
    timestamp = int(time.time() * 1000)
    return f"{prefix}_{timestamp}"


def generate_uuid() -> str:
    return uuid.uuid4().hex


def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def get_current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_total_page(total_page, default: int = 0) -> int:
    """Normalize total page count to a usable non-negative integer."""
    try:
        normalized = int(total_page)
    except (TypeError, ValueError):
        return default

    # Some upstream platforms may occasionally return negative page counts.
    if normalized < 0:
        normalized = abs(normalized)

    return normalized


def validate_score(score) -> tuple:
    if not isinstance(score, (int, float)):
        return False, "评分必须是数字"
    
    from core.constants import MIN_SCORE, MAX_SCORE, SCORE_PRECISION
    
    if score < MIN_SCORE or score > MAX_SCORE:
        return False, f"评分范围{MIN_SCORE}-{MAX_SCORE}"
    
    if (score * 2) % 1 != 0:
        return False, f"评分精度{SCORE_PRECISION}"
    
    return True, "验证通过"


def get_preview_pages(total_page: int) -> list:
    if total_page <= 0:
        return []
    if total_page <= 10:
        return list(range(1, total_page + 1))

    pages = []
    # 前 5 页
    for i in range(1, 6):
        pages.append(i)
    # 中间均匀采样
    step = max(1, (total_page - 5) // 5)
    for p in range(5 + step, total_page, step):
        if len(pages) < 9:
            pages.append(p)
    # 最后一页
    pages.append(total_page)
    return sorted(pages)

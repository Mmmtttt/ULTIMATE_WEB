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
    pages = []
    if total_page >= 1:
        pages.append(1)
    if total_page >= 5:
        pages.append(5)
    if total_page >= 10:
        pages.append(10)
    if total_page > 10:
        pages.append(total_page)
    return pages

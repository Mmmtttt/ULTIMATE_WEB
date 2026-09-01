from __future__ import annotations

import time
from typing import Optional

from flask import g, has_request_context


def start_request_timer() -> None:
    if has_request_context():
        g.request_start_perf = time.perf_counter()


def request_elapsed_ms() -> Optional[float]:
    if not has_request_context():
        return None
    started = getattr(g, "request_start_perf", None)
    if started is None:
        return None
    return (time.perf_counter() - float(started)) * 1000

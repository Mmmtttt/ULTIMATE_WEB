import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.logger import (
    access_logger,
    app_logger,
    configure_debug_mode,
    is_debug_mode,
)


def test_debug_mode_switches_application_and_access_log_levels():
    try:
        assert configure_debug_mode(True) is True
        assert is_debug_mode() is True
        assert app_logger.level < 20
        assert access_logger.level < 20

        assert configure_debug_mode(False) is False
        assert is_debug_mode() is False
        assert app_logger.level == 20
        assert access_logger.level == 30
    finally:
        configure_debug_mode(False)

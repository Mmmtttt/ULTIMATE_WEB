import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.config.entity import UserConfig


def test_reader_preferences_round_trip_through_user_config():
    config = UserConfig.from_dict({
        "double_page_mode": True,
        "double_page_leading_blank": False,
        "tap_page_turn_mode": "right",
        "tap_page_turn_in_webtoon": False,
        "double_tap_action": "menu",
        "auto_read": True,
        "auto_read_interval": 1500,
        "no_reader_animation": True,
        "read_filter_opacity": 0.35,
        "reader_side_padding": 15,
    })

    payload = config.to_dict()
    restored = UserConfig.from_dict(payload)

    assert restored.double_page_mode is True
    assert restored.double_page_leading_blank is False
    assert restored.tap_page_turn_mode == "right"
    assert restored.tap_page_turn_in_webtoon is False
    assert restored.double_tap_action == "menu"
    assert restored.auto_read is True
    assert restored.auto_read_interval == 1500
    assert restored.no_reader_animation is True
    assert restored.read_filter_opacity == 0.35
    assert restored.reader_side_padding == 15


def test_reader_preferences_reject_invalid_ranges_without_partial_save():
    config = UserConfig()

    assert config.update(auto_read_interval=999) is False
    assert config.auto_read_interval == 5000
    assert config.update(read_filter_opacity=0.9) is False
    assert config.read_filter_opacity == 0.0
    assert config.update(reader_side_padding=31) is False
    assert config.reader_side_padding == 0

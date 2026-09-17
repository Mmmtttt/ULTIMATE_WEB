from dataclasses import dataclass
from typing import Optional


@dataclass
class CacheConfig:
    recommendation_cache_max_size_mb: int = 5120
    cache_ttl_seconds: int = 3600
    
    @classmethod
    def from_dict(cls, data: dict) -> "CacheConfig":
        if not data:
            return cls()
        return cls(
            recommendation_cache_max_size_mb=data.get("recommendation_cache_max_size_mb", 5120),
            cache_ttl_seconds=data.get("cache_ttl_seconds", 3600)
        )
    
    def to_dict(self) -> dict:
        return {
            "recommendation_cache_max_size_mb": self.recommendation_cache_max_size_mb,
            "cache_ttl_seconds": self.cache_ttl_seconds
        }
    
    def update(self, **kwargs) -> bool:
        if 'recommendation_cache_max_size_mb' in kwargs:
            value = kwargs['recommendation_cache_max_size_mb']
            if not isinstance(value, int) or value < 100 or value > 51200:
                return False
            self.recommendation_cache_max_size_mb = value
        
        if 'cache_ttl_seconds' in kwargs:
            value = kwargs['cache_ttl_seconds']
            if not isinstance(value, int) or value < 60 or value > 86400:
                return False
            self.cache_ttl_seconds = value
        
        return True


@dataclass
class UserConfig:
    default_page_mode: str = "up_down"
    default_background: str = "white"
    auto_hide_toolbar: bool = True
    show_page_number: bool = True
    auto_download_preview_assets_for_preview_import: bool = False
    single_page_browsing: bool = False
    double_page_mode: bool = False
    double_page_leading_blank: bool = True
    tap_page_turn_mode: str = "full"
    tap_page_turn_in_webtoon: bool = True
    double_tap_action: str = "zoom"
    auto_read: bool = False
    auto_read_interval: int = 5000
    no_reader_animation: bool = False
    read_filter_opacity: float = 0.0
    reader_side_padding: int = 0
    debug_mode: bool = False
    cache_config: CacheConfig = None
    
    def __post_init__(self):
        if self.cache_config is None:
            self.cache_config = CacheConfig()
    
    VALID_PAGE_MODES = ["left_right", "up_down"]
    VALID_BACKGROUNDS = ["white", "dark", "sepia"]
    VALID_TAP_PAGE_TURN_MODES = ["full", "left", "right"]
    VALID_DOUBLE_TAP_ACTIONS = ["zoom", "menu"]
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserConfig":
        if not data:
            return cls()
        
        cache_config_data = data.get("cache_config")
        cache_config = CacheConfig.from_dict(cache_config_data) if cache_config_data else CacheConfig()
        
        return cls(
            default_page_mode=data.get("default_page_mode", "up_down"),
            default_background=data.get("default_background", "white"),
            auto_hide_toolbar=data.get("auto_hide_toolbar", True),
            show_page_number=data.get("show_page_number", True),
            auto_download_preview_assets_for_preview_import=data.get(
                "auto_download_preview_assets_for_preview_import",
                False
            ),
            single_page_browsing=data.get("single_page_browsing", False),
            double_page_mode=data.get("double_page_mode", False),
            double_page_leading_blank=data.get("double_page_leading_blank", True),
            tap_page_turn_mode=data.get("tap_page_turn_mode", "full"),
            tap_page_turn_in_webtoon=data.get("tap_page_turn_in_webtoon", True),
            double_tap_action=data.get("double_tap_action", "zoom"),
            auto_read=data.get("auto_read", False),
            auto_read_interval=data.get("auto_read_interval", 5000),
            no_reader_animation=data.get("no_reader_animation", False),
            read_filter_opacity=data.get("read_filter_opacity", 0.0),
            reader_side_padding=data.get("reader_side_padding", 0),
            debug_mode=bool(data.get("debug_mode", False)),
            cache_config=cache_config
        )
    
    def to_dict(self) -> dict:
        return {
            "default_page_mode": self.default_page_mode,
            "default_background": self.default_background,
            "auto_hide_toolbar": self.auto_hide_toolbar,
            "show_page_number": self.show_page_number,
            "auto_download_preview_assets_for_preview_import": self.auto_download_preview_assets_for_preview_import,
            "single_page_browsing": self.single_page_browsing,
            "double_page_mode": self.double_page_mode,
            "double_page_leading_blank": self.double_page_leading_blank,
            "tap_page_turn_mode": self.tap_page_turn_mode,
            "tap_page_turn_in_webtoon": self.tap_page_turn_in_webtoon,
            "double_tap_action": self.double_tap_action,
            "auto_read": self.auto_read,
            "auto_read_interval": self.auto_read_interval,
            "no_reader_animation": self.no_reader_animation,
            "read_filter_opacity": self.read_filter_opacity,
            "reader_side_padding": self.reader_side_padding,
            "debug_mode": self.debug_mode,
            "cache_config": self.cache_config.to_dict() if self.cache_config else CacheConfig().to_dict()
        }
    
    def update(self, **kwargs) -> bool:
        if 'default_page_mode' in kwargs:
            value = kwargs['default_page_mode']
            if value not in self.VALID_PAGE_MODES:
                return False
            self.default_page_mode = value
        
        if 'default_background' in kwargs:
            value = kwargs['default_background']
            if value not in self.VALID_BACKGROUNDS:
                return False
            self.default_background = value
        
        if 'auto_hide_toolbar' in kwargs:
            self.auto_hide_toolbar = bool(kwargs['auto_hide_toolbar'])
        
        if 'show_page_number' in kwargs:
            self.show_page_number = bool(kwargs['show_page_number'])

        if 'auto_download_preview_assets_for_preview_import' in kwargs:
            self.auto_download_preview_assets_for_preview_import = bool(
                kwargs['auto_download_preview_assets_for_preview_import']
            )

        if 'single_page_browsing' in kwargs:
            self.single_page_browsing = bool(kwargs['single_page_browsing'])

        if 'double_page_mode' in kwargs:
            self.double_page_mode = bool(kwargs['double_page_mode'])

        if 'double_page_leading_blank' in kwargs:
            self.double_page_leading_blank = bool(kwargs['double_page_leading_blank'])

        if 'tap_page_turn_mode' in kwargs:
            value = kwargs['tap_page_turn_mode']
            if value not in self.VALID_TAP_PAGE_TURN_MODES:
                return False
            self.tap_page_turn_mode = value

        if 'tap_page_turn_in_webtoon' in kwargs:
            self.tap_page_turn_in_webtoon = bool(kwargs['tap_page_turn_in_webtoon'])

        if 'double_tap_action' in kwargs:
            value = kwargs['double_tap_action']
            if value not in self.VALID_DOUBLE_TAP_ACTIONS:
                return False
            self.double_tap_action = value

        if 'auto_read' in kwargs:
            self.auto_read = bool(kwargs['auto_read'])

        if 'auto_read_interval' in kwargs:
            value = kwargs['auto_read_interval']
            if not isinstance(value, int) or value < 1000 or value > 30000:
                return False
            self.auto_read_interval = value

        if 'no_reader_animation' in kwargs:
            self.no_reader_animation = bool(kwargs['no_reader_animation'])

        if 'read_filter_opacity' in kwargs:
            value = kwargs['read_filter_opacity']
            if not isinstance(value, (int, float)) or value < 0 or value > 0.8:
                return False
            self.read_filter_opacity = float(value)

        if 'reader_side_padding' in kwargs:
            value = kwargs['reader_side_padding']
            if not isinstance(value, int) or value < 0 or value > 30:
                return False
            self.reader_side_padding = value

        if 'debug_mode' in kwargs:
            self.debug_mode = bool(kwargs['debug_mode'])
        
        if 'cache_config' in kwargs:
            cache_config_data = kwargs['cache_config']
            if isinstance(cache_config_data, dict):
                if not self.cache_config:
                    self.cache_config = CacheConfig()
                if not self.cache_config.update(**cache_config_data):
                    return False
        
        return True
    
    def reset(self):
        self.default_page_mode = "up_down"
        self.default_background = "white"
        self.auto_hide_toolbar = True
        self.show_page_number = True
        self.auto_download_preview_assets_for_preview_import = False
        self.single_page_browsing = False
        self.double_page_mode = False
        self.double_page_leading_blank = True
        self.tap_page_turn_mode = "full"
        self.tap_page_turn_in_webtoon = True
        self.double_tap_action = "zoom"
        self.auto_read = False
        self.auto_read_interval = 5000
        self.no_reader_animation = False
        self.read_filter_opacity = 0.0
        self.reader_side_padding = 0
        self.debug_mode = False
        self.cache_config = CacheConfig()


DEFAULT_CONFIG = UserConfig()

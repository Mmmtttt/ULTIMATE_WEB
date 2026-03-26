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
    cache_config: CacheConfig = None
    
    def __post_init__(self):
        if self.cache_config is None:
            self.cache_config = CacheConfig()
    
    VALID_PAGE_MODES = ["left_right", "up_down"]
    VALID_BACKGROUNDS = ["white", "dark", "sepia"]
    
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
        self.cache_config = CacheConfig()


DEFAULT_CONFIG = UserConfig()

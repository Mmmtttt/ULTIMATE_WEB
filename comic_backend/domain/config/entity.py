from dataclasses import dataclass
from typing import Optional


# 检索引擎：
#   catalog  —— 默认。JSON 文档 + SQLite catalog index（原有行为，全平台可用）
#   semantic —— 可选。语义索引（标签 + 关键词 + 向量三路 RRF 融合），仅桌面端提供
SEARCH_ENGINE_CATALOG = "catalog"
SEARCH_ENGINE_SEMANTIC = "semantic"
VALID_SEARCH_ENGINES = [SEARCH_ENGINE_CATALOG, SEARCH_ENGINE_SEMANTIC]


@dataclass
class VisionConfig:
    """识图补全用的多模态接口配置（OpenAI 兼容 chat/completions）。"""

    base_url: str = ""
    api_key: str = ""
    model: str = ""
    max_gap: int = 8  # 采样间隔上限（页）：页数越多间隔越大，但不超过这个值
    max_images: int = 48  # 单本最多送几张图，兜底保护
    timeout_seconds: int = 120
    prompt: str = ""
    # 识图前先发给模型的上下文文件（默认用项目内置的 prompts/semantic_vision_context.md）
    prompt_file: str = ""
    context_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "VisionConfig":
        if not data:
            return cls()
        return cls(
            base_url=str(data.get("base_url") or "").strip(),
            api_key=str(data.get("api_key") or "").strip(),
            model=str(data.get("model") or "").strip(),
            max_gap=int(data.get("max_gap") or 8),
            max_images=int(data.get("max_images") or 48),
            timeout_seconds=int(data.get("timeout_seconds") or 120),
            prompt=str(data.get("prompt") or ""),
            prompt_file=str(data.get("prompt_file") or "").strip(),
            context_enabled=bool(data.get("context_enabled", True)),
        )

    def to_dict(self, mask_key: bool = False) -> dict:
        return {
            "base_url": self.base_url,
            "api_key": mask_api_key(self.api_key) if mask_key else self.api_key,
            "model": self.model,
            "max_gap": self.max_gap,
            "max_images": self.max_images,
            "timeout_seconds": self.timeout_seconds,
            "prompt": self.prompt,
            "prompt_file": self.prompt_file,
            "context_enabled": self.context_enabled,
        }

    def update(self, **kwargs) -> bool:
        if "base_url" in kwargs:
            self.base_url = str(kwargs.get("base_url") or "").strip()
        if "api_key" in kwargs:
            value = str(kwargs.get("api_key") or "").strip()
            # 前端回传掩码时表示「保持不变」
            if value and not _is_masked_key(value):
                self.api_key = value
            elif not value:
                self.api_key = ""
        if "model" in kwargs:
            self.model = str(kwargs.get("model") or "").strip()
        if "max_gap" in kwargs:
            try:
                value = int(kwargs.get("max_gap"))
            except (TypeError, ValueError):
                return False
            if value < 1 or value > 8:
                return False
            self.max_gap = value
        if "max_images" in kwargs:
            try:
                value = int(kwargs.get("max_images"))
            except (TypeError, ValueError):
                return False
            if value < 1 or value > 96:
                return False
            self.max_images = value
        if "timeout_seconds" in kwargs:
            try:
                value = int(kwargs.get("timeout_seconds"))
            except (TypeError, ValueError):
                return False
            if value < 10 or value > 600:
                return False
            self.timeout_seconds = value
        if "prompt" in kwargs:
            self.prompt = str(kwargs.get("prompt") or "")
        if "prompt_file" in kwargs:
            self.prompt_file = str(kwargs.get("prompt_file") or "").strip()
        if "context_enabled" in kwargs:
            self.context_enabled = bool(kwargs.get("context_enabled"))
        return True

    @property
    def ready(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def mask_api_key(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}{'*' * 6}{text[-4:]}"


def _is_masked_key(value: str) -> bool:
    return "*" in str(value or "")


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
    debug_mode: bool = False
    search_engine: str = SEARCH_ENGINE_CATALOG
    cache_config: CacheConfig = None
    vision_config: VisionConfig = None
    
    def __post_init__(self):
        if self.cache_config is None:
            self.cache_config = CacheConfig()
        if self.vision_config is None:
            self.vision_config = VisionConfig()
    
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
            debug_mode=bool(data.get("debug_mode", False)),
            search_engine=_normalize_search_engine(data.get("search_engine")) or SEARCH_ENGINE_CATALOG,
            cache_config=cache_config,
            vision_config=VisionConfig.from_dict(data.get("vision_config") or {}),
        )
    
    def to_dict(self) -> dict:
        return {
            "default_page_mode": self.default_page_mode,
            "default_background": self.default_background,
            "auto_hide_toolbar": self.auto_hide_toolbar,
            "show_page_number": self.show_page_number,
            "auto_download_preview_assets_for_preview_import": self.auto_download_preview_assets_for_preview_import,
            "single_page_browsing": self.single_page_browsing,
            "debug_mode": self.debug_mode,
            "search_engine": self.search_engine,
            "cache_config": self.cache_config.to_dict() if self.cache_config else CacheConfig().to_dict(),
            "vision_config": self.vision_config.to_dict() if self.vision_config else VisionConfig().to_dict(),
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

        if 'debug_mode' in kwargs:
            self.debug_mode = bool(kwargs['debug_mode'])

        if 'search_engine' in kwargs:
            value = _normalize_search_engine(kwargs['search_engine'])
            if value not in VALID_SEARCH_ENGINES:
                return False
            self.search_engine = value
        
        if 'cache_config' in kwargs:
            cache_config_data = kwargs['cache_config']
            if isinstance(cache_config_data, dict):
                if not self.cache_config:
                    self.cache_config = CacheConfig()
                if not self.cache_config.update(**cache_config_data):
                    return False

        if 'vision_config' in kwargs:
            vision_config_data = kwargs['vision_config']
            if isinstance(vision_config_data, dict):
                if not self.vision_config:
                    self.vision_config = VisionConfig()
                if not self.vision_config.update(**vision_config_data):
                    return False
        
        return True
    
    def reset(self):
        self.default_page_mode = "up_down"
        self.default_background = "white"
        self.auto_hide_toolbar = True
        self.show_page_number = True
        self.auto_download_preview_assets_for_preview_import = False
        self.single_page_browsing = False
        self.debug_mode = False
        self.search_engine = SEARCH_ENGINE_CATALOG
        self.cache_config = CacheConfig()
        self.vision_config = VisionConfig()


def _normalize_search_engine(value) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in VALID_SEARCH_ENGINES:
        return normalized
    # 兼容前端可能传入的真假值：True → 语义，False → 原样
    if isinstance(value, bool):
        return SEARCH_ENGINE_SEMANTIC if value else SEARCH_ENGINE_CATALOG
    return ""


DEFAULT_CONFIG = UserConfig()

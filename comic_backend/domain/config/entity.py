from dataclasses import dataclass
from typing import Optional


@dataclass
class UserConfig:
    default_page_mode: str = "left_right"
    default_background: str = "white"
    auto_hide_toolbar: bool = True
    show_page_number: bool = True
    
    VALID_PAGE_MODES = ["left_right", "up_down"]
    VALID_BACKGROUNDS = ["white", "dark", "sepia"]
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserConfig":
        if not data:
            return cls()
        
        return cls(
            default_page_mode=data.get("default_page_mode", "left_right"),
            default_background=data.get("default_background", "white"),
            auto_hide_toolbar=data.get("auto_hide_toolbar", True),
            show_page_number=data.get("show_page_number", True)
        )
    
    def to_dict(self) -> dict:
        return {
            "default_page_mode": self.default_page_mode,
            "default_background": self.default_background,
            "auto_hide_toolbar": self.auto_hide_toolbar,
            "show_page_number": self.show_page_number
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
        
        return True
    
    def reset(self):
        self.default_page_mode = "left_right"
        self.default_background = "white"
        self.auto_hide_toolbar = True
        self.show_page_number = True


DEFAULT_CONFIG = UserConfig()

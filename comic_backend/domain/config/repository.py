from abc import ABC, abstractmethod
from .entity import UserConfig


class ConfigRepository(ABC):
    @abstractmethod
    def get(self) -> UserConfig:
        pass
    
    @abstractmethod
    def save(self, config: UserConfig) -> bool:
        pass

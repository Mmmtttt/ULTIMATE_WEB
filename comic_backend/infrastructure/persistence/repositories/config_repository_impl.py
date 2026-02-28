from domain.config import UserConfig, ConfigRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import error_logger


class ConfigJsonRepository(ConfigRepository):
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def get(self) -> UserConfig:
        try:
            data = self._storage.read()
            config_data = data.get("user_config", {})
            return UserConfig.from_dict(config_data)
        except Exception as e:
            error_logger.error(f"获取配置失败: {e}")
            return UserConfig()
    
    def save(self, config: UserConfig) -> bool:
        try:
            data = self._storage.read()
            data["user_config"] = config.to_dict()
            
            from core.utils import get_current_time
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"保存配置失败: {e}")
            return False

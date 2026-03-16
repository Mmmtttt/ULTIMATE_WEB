from domain.config import ConfigRepository, UserConfig
from core.constants import JSON_FILE, USER_CONFIG_JSON_FILE
from infrastructure.logger import error_logger
from infrastructure.persistence.json_storage import JsonStorage


class ConfigJsonRepository(ConfigRepository):
    def __init__(self, storage: JsonStorage = None, legacy_storage: JsonStorage = None):
        self._storage = storage or JsonStorage(USER_CONFIG_JSON_FILE)
        self._legacy_storage = legacy_storage or JsonStorage(JSON_FILE)

    @staticmethod
    def _extract_user_config(data: dict) -> dict:
        if not isinstance(data, dict):
            return {}

        user_config = data.get("user_config")
        if isinstance(user_config, dict):
            return user_config

        # Backward compatibility: very old files may store config at root level.
        if "default_page_mode" in data or "default_background" in data:
            return data

        return {}

    def get(self) -> UserConfig:
        try:
            data = self._storage.read()
            config_data = self._extract_user_config(data)
            if config_data:
                return UserConfig.from_dict(config_data)

            # First-run migration from legacy comics_database.json.
            legacy_data = self._legacy_storage.read()
            legacy_config = self._extract_user_config(legacy_data)
            config = UserConfig.from_dict(legacy_config)
            if legacy_config:
                self.save(config)
            return config
        except Exception as e:
            error_logger.error(f"获取配置失败: {e}")
            return UserConfig()

    def save(self, config: UserConfig) -> bool:
        try:
            data = self._storage.read()
            if not isinstance(data, dict):
                data = {}

            data["user_config"] = config.to_dict()

            from core.utils import get_current_time
            data["last_updated"] = get_current_time()

            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"保存配置失败: {e}")
            return False

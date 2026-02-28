from domain.config import UserConfig, ConfigRepository
from infrastructure.persistence.repositories import ConfigJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger


class ConfigAppService:
    def __init__(self, config_repo: ConfigRepository = None):
        self._config_repo = config_repo or ConfigJsonRepository()
    
    def get_config(self) -> ServiceResult:
        try:
            config = self._config_repo.get()
            app_logger.info("获取配置成功")
            return ServiceResult.ok(config.to_dict())
        except Exception as e:
            error_logger.error(f"获取配置失败: {e}")
            return ServiceResult.error("获取配置失败")
    
    def update_config(self, **kwargs) -> ServiceResult:
        try:
            config = self._config_repo.get()
            
            if not config.update(**kwargs):
                return ServiceResult.error("配置参数验证失败")
            
            if not self._config_repo.save(config):
                return ServiceResult.error("保存配置失败")
            
            app_logger.info(f"更新配置成功: {kwargs}")
            return ServiceResult.ok(config.to_dict(), "配置保存成功")
        except Exception as e:
            error_logger.error(f"更新配置失败: {e}")
            return ServiceResult.error("更新配置失败")
    
    def reset_config(self) -> ServiceResult:
        try:
            config = self._config_repo.get()
            config.reset()
            
            if not self._config_repo.save(config):
                return ServiceResult.error("重置配置失败")
            
            app_logger.info("重置配置成功")
            return ServiceResult.ok(config.to_dict(), "配置已重置为默认值")
        except Exception as e:
            error_logger.error(f"重置配置失败: {e}")
            return ServiceResult.error("重置配置失败")
    
    def update_page_mode(self, page_mode: str) -> ServiceResult:
        return self.update_config(default_page_mode=page_mode)
    
    def update_background(self, background: str) -> ServiceResult:
        return self.update_config(default_background=background)

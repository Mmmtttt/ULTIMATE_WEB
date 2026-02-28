import json
import os
import time
import shutil
import uuid
from core.constants import JSON_FILE, BACKUP_SUFFIX
from infrastructure.logger import app_logger, error_logger


class JsonStorage:
    _instance = None
    
    def __new__(cls, json_file: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, json_file: str = None):
        if self._initialized:
            return
        
        self.json_file = json_file or JSON_FILE
        self._lock_file = self.json_file + '.lock'
        self._initialized = True
    
    def _acquire_lock(self, timeout: int = 5) -> bool:
        start_time = time.time()
        while os.path.exists(self._lock_file):
            if time.time() - start_time > timeout:
                try:
                    os.remove(self._lock_file)
                    error_logger.warning(f"锁文件超时，强制删除: {self._lock_file}")
                except:
                    pass
                break
            time.sleep(0.1)
        
        try:
            with open(self._lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            error_logger.error(f"创建锁文件失败: {e}")
            return False
    
    def _release_lock(self):
        try:
            if os.path.exists(self._lock_file):
                os.remove(self._lock_file)
        except Exception as e:
            error_logger.error(f"删除锁文件失败: {e}")
    
    def read(self) -> dict:
        try:
            if not os.path.exists(self.json_file):
                return self._create_empty_data()
            
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            app_logger.info(f"JSON 文件读取成功: {self.json_file}")
            return data
        except json.JSONDecodeError as e:
            error_logger.error(f"JSON 文件损坏: {e}")
            return self.restore_backup()
        except Exception as e:
            error_logger.error(f"读取 JSON 文件失败: {e}")
            return self._create_empty_data()
    
    def write(self, data: dict, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            try:
                if not self._acquire_lock():
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        error_logger.error("获取文件锁失败")
                        return False
                
                try:
                    dir_path = os.path.dirname(self.json_file)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    backup_file = self.json_file + BACKUP_SUFFIX
                    if os.path.exists(self.json_file):
                        try:
                            shutil.copy2(self.json_file, backup_file)
                            app_logger.info(f"创建 JSON 备份: {backup_file}")
                        except Exception as e:
                            error_logger.warning(f"创建备份失败: {e}")
                    
                    temp_path = os.path.join(dir_path if dir_path else '.', f'comic_db_{uuid.uuid4().hex}.tmp')
                    
                    try:
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        if os.path.exists(self.json_file):
                            os.replace(temp_path, self.json_file)
                        else:
                            os.rename(temp_path, self.json_file)
                        
                        app_logger.info(f"JSON 文件写入成功: {self.json_file}")
                        return True
                    except Exception as e:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        raise e
                        
                finally:
                    self._release_lock()
                    
            except PermissionError as e:
                error_logger.error(f"权限错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                return False
            except Exception as e:
                error_logger.error(f"写入 JSON 文件失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                return False
        
        return False
    
    def _create_empty_data(self) -> dict:
        return {
            "collection_name": "我的收藏集",
            "user": "用户名",
            "total_comics": 0,
            "last_updated": time.strftime("%Y-%m-%d"),
            "tags": [],
            "lists": [],
            "comics": [],
            "user_config": {
                "default_page_mode": "left_right",
                "default_background": "white"
            }
        }
    
    def restore_backup(self) -> dict:
        backup_file = self.json_file + BACKUP_SUFFIX
        try:
            if os.path.exists(backup_file):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                app_logger.info(f"从备份恢复数据: {backup_file}")
                self.write(data)
                return data
            else:
                app_logger.warning("备份文件不存在")
                return self._create_empty_data()
        except Exception as e:
            error_logger.error(f"从备份恢复失败: {e}")
            return self._create_empty_data()

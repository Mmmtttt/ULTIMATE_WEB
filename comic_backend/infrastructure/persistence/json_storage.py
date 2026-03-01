import json
import os
import time
import shutil
import uuid
from core.constants import JSON_FILE, BACKUP_SUFFIX
from infrastructure.logger import app_logger, error_logger


class JsonStorage:
    _instances = {}
    
    def __new__(cls, json_file: str = None):
        file_key = json_file or JSON_FILE
        if file_key not in cls._instances:
            cls._instances[file_key] = super().__new__(cls)
            cls._instances[file_key]._initialized = False
            cls._instances[file_key]._file_key = file_key
        return cls._instances[file_key]
    
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
                    # 使用绝对路径
                    json_file_abs = os.path.abspath(self.json_file)
                    dir_path = os.path.dirname(json_file_abs)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    backup_file = json_file_abs + BACKUP_SUFFIX
                    if os.path.exists(json_file_abs):
                        try:
                            shutil.copy2(json_file_abs, backup_file)
                            app_logger.info(f"创建 JSON 备份: {backup_file}")
                        except Exception as e:
                            error_logger.warning(f"创建备份失败: {e}")
                    
                    temp_path = os.path.join(dir_path if dir_path else '.', f'comic_db_{uuid.uuid4().hex}.tmp')
                    
                    try:
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        if os.path.exists(json_file_abs):
                            os.replace(temp_path, json_file_abs)
                        else:
                            os.rename(temp_path, json_file_abs)
                        
                        app_logger.info(f"JSON 文件写入成功: {json_file_abs}")
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
        is_recommendation = "recommendations" in self.json_file
        comics_key = "recommendations" if is_recommendation else "comics"
        total_key = "total_recommendations" if is_recommendation else "total_comics"
        
        return {
            "collection_name": "推荐漫画" if is_recommendation else "我的收藏集",
            "user": "用户名",
            total_key: 0,
            "last_updated": time.strftime("%Y-%m-%d"),
            "tags": [],
            "lists": [],
            comics_key: [],
            "user_config": {
                "default_page_mode": "left_right",
                "default_background": "dark" if is_recommendation else "white"
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
    
    def atomic_update(self, update_func, max_retries: int = 3) -> bool:
        """
        原子性更新数据
        
        在持有锁的情况下执行读取-修改-写入操作，防止并发竞争
        
        Args:
            update_func: 更新函数，接收当前数据，返回更新后的数据
            max_retries: 最大重试次数
        
        Returns:
            是否成功
        """
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
                    # 在锁保护下读取数据
                    if not os.path.exists(self.json_file):
                        data = self._create_empty_data()
                    else:
                        with open(self.json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    
                    # 执行更新
                    data = update_func(data)
                    if data is None:
                        return False
                    
                    # 在锁保护下写入数据
                    json_file_abs = os.path.abspath(self.json_file)
                    dir_path = os.path.dirname(json_file_abs)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    # 创建备份
                    backup_file = json_file_abs + BACKUP_SUFFIX
                    if os.path.exists(json_file_abs):
                        try:
                            shutil.copy2(json_file_abs, backup_file)
                        except Exception as e:
                            error_logger.warning(f"创建备份失败: {e}")
                    
                    # 写入临时文件然后原子替换
                    temp_path = os.path.join(dir_path if dir_path else '.', f'comic_db_{uuid.uuid4().hex}.tmp')
                    
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    if os.path.exists(json_file_abs):
                        os.replace(temp_path, json_file_abs)
                    else:
                        os.rename(temp_path, json_file_abs)
                    
                    app_logger.info(f"JSON 文件原子更新成功: {json_file_abs}")
                    return True
                    
                finally:
                    self._release_lock()
                    
            except Exception as e:
                error_logger.error(f"原子更新失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                return False
        
        return False

import json
import os
import time
import tempfile
import shutil
from config import Config
from utils.logger import app_logger, error_logger

class JsonHandler:
    def __init__(self, json_file=None):
        self.json_file = json_file or Config.JSON_FILE
        self._lock_file = self.json_file + '.lock'
    
    def _acquire_lock(self, timeout=5):
        """获取文件锁（简单的超时机制）"""
        start_time = time.time()
        while os.path.exists(self._lock_file):
            if time.time() - start_time > timeout:
                # 超时，强制删除锁文件
                try:
                    os.remove(self._lock_file)
                    error_logger.warning(f"锁文件超时，强制删除: {self._lock_file}")
                except:
                    pass
                break
            time.sleep(0.1)
        
        # 创建锁文件
        try:
            with open(self._lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception as e:
            error_logger.error(f"创建锁文件失败: {e}")
            return False
    
    def _release_lock(self):
        """释放文件锁"""
        try:
            if os.path.exists(self._lock_file):
                os.remove(self._lock_file)
        except Exception as e:
            error_logger.error(f"删除锁文件失败: {e}")
    
    def read_json(self):
        """读取 JSON 文件，处理文件不存在或损坏的情况"""
        try:
            if not os.path.exists(self.json_file):
                # 创建空的 JSON 结构
                empty_data = {
                    "collection_name": "我的收藏集",
                    "user": "用户名",
                    "total_comics": 0,
                    "last_updated": time.strftime("%Y-%m-%d"),
                    "tags": [],
                    "lists": [],
                    "comics": [],
                    "user_config": {
                        "preload_num": 3,
                        "default_page_mode": "left_right",
                        "default_background": "white"
                    }
                }
                app_logger.info(f"JSON 文件不存在，创建空数据结构: {self.json_file}")
                return empty_data
            
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            app_logger.info(f"JSON 文件读取成功: {self.json_file}")
            return data
        except json.JSONDecodeError as e:
            error_logger.error(f"JSON 文件损坏: {e}")
            # 尝试从备份恢复
            return self.restore_backup()
        except Exception as e:
            error_logger.error(f"读取 JSON 文件失败: {e}")
            return {
                "collection_name": "我的收藏集",
                "user": "用户名",
                "total_comics": 0,
                "last_updated": time.strftime("%Y-%m-%d"),
                "tags": [],
                "lists": [],
                "comics": [],
                "user_config": {
                    "preload_num": 3,
                    "default_page_mode": "left_right",
                    "default_background": "white"
                }
            }
    
    def write_json(self, data, max_retries=3):
        """原子性写入 JSON 文件，自动备份，带重试机制"""
        for attempt in range(max_retries):
            try:
                # 获取锁
                if not self._acquire_lock():
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        error_logger.error("获取文件锁失败")
                        return False
                
                try:
                    # 确保目录存在
                    dir_path = os.path.dirname(self.json_file)
                    if dir_path:
                        os.makedirs(dir_path, exist_ok=True)
                    
                    # 创建备份（如果文件存在）
                    backup_file = self.json_file + Config.BACKUP_SUFFIX
                    if os.path.exists(self.json_file):
                        try:
                            shutil.copy2(self.json_file, backup_file)
                            app_logger.info(f"创建 JSON 备份: {backup_file}")
                        except Exception as e:
                            error_logger.warning(f"创建备份失败: {e}")
                    
                    # 使用临时文件写入（原子操作）
                    import uuid
                    temp_path = os.path.join(dir_path if dir_path else '.', f'comic_db_{uuid.uuid4().hex}.tmp')
                    
                    try:
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        # 原子性替换文件
                        if os.path.exists(self.json_file):
                            os.replace(temp_path, self.json_file)
                        else:
                            os.rename(temp_path, self.json_file)
                        
                        app_logger.info(f"JSON 文件写入成功: {self.json_file}")
                        return True
                    except Exception as e:
                        # 清理临时文件
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        raise e
                        
                finally:
                    # 释放锁
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
    
    def generate_id(self, prefix):
        """生成唯一 ID"""
        timestamp = int(time.time() * 1000)
        return f"{prefix}_{timestamp}"
    
    def restore_backup(self):
        """从备份恢复数据"""
        backup_file = self.json_file + Config.BACKUP_SUFFIX
        try:
            if os.path.exists(backup_file):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                app_logger.info(f"从备份恢复数据: {backup_file}")
                # 恢复到主文件
                self.write_json(data)
                return data
            else:
                app_logger.warning("备份文件不存在")
                return {
                    "collection_name": "我的收藏集",
                    "user": "用户名",
                    "total_comics": 0,
                    "last_updated": time.strftime("%Y-%m-%d"),
                    "tags": [],
                    "lists": [],
                    "comics": [],
                    "user_config": {
                        "preload_num": 3,
                        "default_page_mode": "left_right",
                        "default_background": "white"
                    }
                }
        except Exception as e:
            error_logger.error(f"从备份恢复失败: {e}")
            return {
                "collection_name": "我的收藏集",
                "user": "用户名",
                "total_comics": 0,
                "last_updated": time.strftime("%Y-%m-%d"),
                "tags": [],
                "lists": [],
                "comics": [],
                "user_config": {
                    "preload_num": 3,
                    "default_page_mode": "left_right",
                    "default_background": "white"
                }
            }

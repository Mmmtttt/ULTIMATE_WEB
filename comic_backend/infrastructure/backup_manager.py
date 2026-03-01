"""
三级定时备份管理器
- 备份一：每10分钟备份一次（写入前数据库的内容）
- 备份二：每小时备份一次（写入备份一的内容）
- 备份三：每天备份一次（写入备份二的内容）

推荐页和主页的备份完全独立
"""

import os
import json
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE, BACKUP_SUFFIX
from infrastructure.logger import app_logger, error_logger


class TieredBackupManager:
    """
    三级定时备份管理器
    
    备份策略：
    - Tier 1 (10分钟): 保存最近的数据库状态
    - Tier 2 (1小时): 保存Tier 1的内容，提供更长时间的历史
    - Tier 3 (1天): 保存Tier 2的内容，提供最长期的历史
    """
    
    def __init__(self, json_file: str):
        """
        初始化备份管理器
        
        Args:
            json_file: 要备份的JSON文件路径
        """
        self.json_file = json_file
        self.base_name = Path(json_file).stem  # 如: comics_database 或 recommendations_database
        self.backup_dir = Path(json_file).parent / "backup" / self.base_name
        
        # 三级备份路径
        self.tier1_file = self.backup_dir / f"{self.base_name}_tier1.bkp"      # 10分钟
        self.tier2_file = self.backup_dir / f"{self.base_name}_tier2.bkp"      # 1小时
        self.tier3_file = self.backup_dir / f"{self.base_name}_tier3.bkp"      # 1天
        
        # 时间戳文件（记录上次备份时间）
        self.tier1_time_file = self.backup_dir / f"{self.base_name}_tier1.time"
        self.tier2_time_file = self.backup_dir / f"{self.base_name}_tier2.time"
        self.tier3_time_file = self.backup_dir / f"{self.base_name}_tier3.time"
        
        # 备份间隔（秒）
        self.TIER1_INTERVAL = 10 * 60       # 10分钟
        self.TIER2_INTERVAL = 60 * 60       # 1小时
        self.TIER3_INTERVAL = 24 * 60 * 60  # 1天
        
        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 定时器线程
        self._timer = None
        self._running = False
        self._lock = threading.Lock()
        
        app_logger.info(f"[BackupManager] 初始化完成: {self.base_name}")
    
    def _get_last_backup_time(self, time_file: Path) -> datetime:
        """获取上次备份时间"""
        try:
            if time_file.exists():
                with open(time_file, 'r') as f:
                    timestamp = float(f.read().strip())
                    return datetime.fromtimestamp(timestamp)
        except Exception as e:
            error_logger.error(f"读取备份时间失败: {e}")
        return datetime.min
    
    def _set_backup_time(self, time_file: Path):
        """设置备份时间"""
        try:
            with open(time_file, 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            error_logger.error(f"写入备份时间失败: {e}")
    
    def _should_backup(self, time_file: Path, interval: int) -> bool:
        """检查是否应该执行备份"""
        last_backup = self._get_last_backup_time(time_file)
        elapsed = (datetime.now() - last_backup).total_seconds()
        return elapsed >= interval
    
    def _copy_file(self, src: Path, dst: Path) -> bool:
        """安全复制文件"""
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            return True
        except Exception as e:
            error_logger.error(f"复制文件失败 {src} -> {dst}: {e}")
            return False
    
    def perform_backup(self):
        """
        执行三级备份
        
        备份逻辑：
        1. Tier 1: 每10分钟从原始数据库备份
        2. Tier 2: 每小时从Tier 1备份
        3. Tier 3: 每天从Tier 2备份
        """
        with self._lock:
            try:
                json_path = Path(self.json_file)
                if not json_path.exists():
                    app_logger.warning(f"[BackupManager] 源文件不存在: {self.json_file}")
                    return
                
                # Tier 1: 10分钟备份（从原始数据库）
                if self._should_backup(self.tier1_time_file, self.TIER1_INTERVAL):
                    if self._copy_file(json_path, self.tier1_file):
                        self._set_backup_time(self.tier1_time_file)
                        app_logger.info(f"[BackupManager] Tier 1 备份完成: {self.base_name}")
                
                # Tier 2: 1小时备份（从Tier 1）
                if self._should_backup(self.tier2_time_file, self.TIER2_INTERVAL):
                    if self.tier1_file.exists():
                        if self._copy_file(self.tier1_file, self.tier2_file):
                            self._set_backup_time(self.tier2_time_file)
                            app_logger.info(f"[BackupManager] Tier 2 备份完成: {self.base_name}")
                
                # Tier 3: 1天备份（从Tier 2）
                if self._should_backup(self.tier3_time_file, self.TIER3_INTERVAL):
                    if self.tier2_file.exists():
                        if self._copy_file(self.tier2_file, self.tier3_file):
                            self._set_backup_time(self.tier3_time_file)
                            app_logger.info(f"[BackupManager] Tier 3 备份完成: {self.base_name}")
                
            except Exception as e:
                error_logger.error(f"[BackupManager] 备份失败: {e}")
    
    def start(self):
        """启动定时备份"""
        if self._running:
            return
        
        self._running = True
        self._schedule_backup()
        app_logger.info(f"[BackupManager] 定时备份已启动: {self.base_name}")
    
    def stop(self):
        """停止定时备份"""
        self._running = False
        if self._timer:
            self._timer.cancel()
        app_logger.info(f"[BackupManager] 定时备份已停止: {self.base_name}")
    
    def _schedule_backup(self):
        """调度下一次备份"""
        if not self._running:
            return
        
        # 执行备份
        self.perform_backup()
        
        # 计算下次备份时间（每1分钟检查一次）
        next_check = 60  # 1分钟
        
        self._timer = threading.Timer(next_check, self._schedule_backup)
        self._timer.daemon = True
        self._timer.start()
    
    def restore_from_tier(self, tier: int) -> bool:
        """
        从指定层级恢复备份
        
        Args:
            tier: 备份层级 (1, 2, 或 3)
        
        Returns:
            恢复是否成功
        """
        tier_files = {
            1: self.tier1_file,
            2: self.tier2_file,
            3: self.tier3_file
        }
        
        if tier not in tier_files:
            error_logger.error(f"[BackupManager] 无效的备份层级: {tier}")
            return False
        
        backup_file = tier_files[tier]
        
        try:
            if not backup_file.exists():
                app_logger.warning(f"[BackupManager] 备份文件不存在: {backup_file}")
                return False
            
            # 先备份当前文件
            json_path = Path(self.json_file)
            if json_path.exists():
                current_backup = str(json_path) + ".restore_backup"
                shutil.copy2(str(json_path), current_backup)
            
            # 恢复备份
            shutil.copy2(str(backup_file), str(json_path))
            app_logger.info(f"[BackupManager] 从 Tier {tier} 恢复成功: {self.base_name}")
            return True
            
        except Exception as e:
            error_logger.error(f"[BackupManager] 恢复失败: {e}")
            return False
    
    def get_backup_info(self) -> dict:
        """获取备份信息"""
        def get_file_info(file_path: Path) -> dict:
            if not file_path.exists():
                return {"exists": False}
            stat = file_path.stat()
            return {
                "exists": True,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return {
            "database": self.base_name,
            "tier1": get_file_info(self.tier1_file),
            "tier2": get_file_info(self.tier2_file),
            "tier3": get_file_info(self.tier3_file)
        }


class BackupManagerFactory:
    """备份管理器工厂 - 管理所有数据库的备份"""
    
    _instance = None
    _managers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_manager(self, json_file: str) -> TieredBackupManager:
        """获取或创建备份管理器"""
        if json_file not in self._managers:
            self._managers[json_file] = TieredBackupManager(json_file)
        return self._managers[json_file]
    
    def start_all(self):
        """启动所有备份管理器"""
        # 主页数据库
        home_manager = self.get_manager(JSON_FILE)
        home_manager.start()
        
        # 推荐页数据库
        rec_manager = self.get_manager(RECOMMENDATION_JSON_FILE)
        rec_manager.start()
        
        app_logger.info("[BackupManagerFactory] 所有备份管理器已启动")
    
    def stop_all(self):
        """停止所有备份管理器"""
        for manager in self._managers.values():
            manager.stop()
        app_logger.info("[BackupManagerFactory] 所有备份管理器已停止")
    
    def get_all_info(self) -> dict:
        """获取所有备份信息"""
        return {
            json_file: manager.get_backup_info()
            for json_file, manager in self._managers.items()
        }


# 全局工厂实例
backup_factory = BackupManagerFactory()


def init_backup_system():
    """初始化备份系统"""
    backup_factory.start_all()


def shutdown_backup_system():
    """关闭备份系统"""
    backup_factory.stop_all()

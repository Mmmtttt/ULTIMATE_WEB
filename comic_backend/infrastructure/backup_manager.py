"""
三级定时备份管理器
- 备份一：每10分钟备份一次（写入前数据库的内容）
- 备份二：每小时备份一次（写入备份一的内容）
- 备份三：每天备份一次（写入备份二的内容）

推荐页和主页的备份完全独立

优化：支持多版本备份，每个层级最多保留指定数量的备份文件
"""

import os
import json
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from core.constants import JSON_FILE, RECOMMENDATION_JSON_FILE, TAGS_JSON_FILE, LISTS_JSON_FILE, BACKUP_SUFFIX
from infrastructure.logger import app_logger, error_logger


class TieredBackupManager:
    """
    三级定时备份管理器
    
    备份策略：
    - Tier 1 (10分钟): 保存最近的数据库状态
    - Tier 2 (1小时): 保存Tier 1的内容，提供更长时间的历史
    - Tier 3 (1天): 保存Tier 2的内容，提供最长期的历史
    
    每个层级保留多个版本，防止频繁覆盖
    """
    
    # 每个层级保留的备份文件数量
    MAX_TIER1_BACKUPS = 3   # 10分钟级保留3个（30分钟内的历史）
    MAX_TIER2_BACKUPS = 3   # 1小时级保留3个（3小时内的历史）
    MAX_TIER3_BACKUPS = 3   # 1天级保留3个（3天内的历史）
    
    def __init__(self, json_file: str, max_tier1: int = None, max_tier2: int = None, max_tier3: int = None):
        """
        初始化备份管理器
        
        Args:
            json_file: 要备份的JSON文件路径
            max_tier1: Tier1最大备份数（默认3）
            max_tier2: Tier2最大备份数（默认3）
            max_tier3: Tier3最大备份数（默认3）
        """
        self.json_file = json_file
        self.base_name = Path(json_file).stem
        self.backup_dir = Path(json_file).parent / "backup" / self.base_name
        
        self.MAX_TIER1_BACKUPS = max_tier1 or 3
        self.MAX_TIER2_BACKUPS = max_tier2 or 3
        self.MAX_TIER3_BACKUPS = max_tier3 or 3
        
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
        
        app_logger.info(f"[BackupManager] 初始化完成: {self.base_name}, "
                       f"备份策略: Tier1={self.MAX_TIER1_BACKUPS}, "
                       f"Tier2={self.MAX_TIER2_BACKUPS}, Tier3={self.MAX_TIER3_BACKUPS}")
    
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
    
    def _get_tier_files(self, tier: int) -> list:
        """获取指定层级的所有备份文件"""
        pattern = f"{self.base_name}_tier{tier}_*.bkp"
        files = sorted(self.backup_dir.glob(pattern), key=lambda x: x.stat().st_mtime)
        return files
    
    def _rotate_backups(self, tier: int, max_backups: int):
        """轮转备份文件，保留最新N个"""
        files = self._get_tier_files(tier)
        while len(files) >= max_backups:
            oldest = files.pop(0)
            try:
                oldest.unlink()
                app_logger.info(f"[BackupManager] 删除过期备份: {oldest}")
            except Exception as e:
                error_logger.error(f"[BackupManager] 删除过期备份失败: {e}")
    
    def _get_next_backup_name(self, tier: int) -> Path:
        """获取下一个备份文件名（带时间戳）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.backup_dir / f"{self.base_name}_tier{tier}_{timestamp}.bkp"
    
    def perform_backup(self):
        """
        执行三级备份
        
        备份逻辑：
        1. Tier 1: 每10分钟从原始数据库备份，保留3个版本
        2. Tier 2: 每小时从Tier 1备份，保留3个版本
        3. Tier 3: 每天从Tier 2备份，保留3个版本
        """
        with self._lock:
            try:
                json_path = Path(self.json_file)
                if not json_path.exists():
                    app_logger.warning(f"[BackupManager] 源文件不存在: {self.json_file}")
                    return
                
                # Tier 1: 10分钟备份（从原始数据库）
                if self._should_backup(self.tier1_time_file, self.TIER1_INTERVAL):
                    new_tier1 = self._get_next_backup_name(1)
                    if self._copy_file(json_path, new_tier1):
                        self._set_backup_time(self.tier1_time_file)
                        self._rotate_backups(1, self.MAX_TIER1_BACKUPS)
                        app_logger.info(f"[BackupManager] Tier 1 备份完成: {self.base_name}")
                
                # Tier 2: 1小时备份（从最新的Tier 1）
                if self._should_backup(self.tier2_time_file, self.TIER2_INTERVAL):
                    tier1_files = self._get_tier_files(1)
                    if tier1_files:
                        latest_tier1 = tier1_files[-1]
                        new_tier2 = self._get_next_backup_name(2)
                        if self._copy_file(latest_tier1, new_tier2):
                            self._set_backup_time(self.tier2_time_file)
                            self._rotate_backups(2, self.MAX_TIER2_BACKUPS)
                            app_logger.info(f"[BackupManager] Tier 2 备份完成: {self.base_name}")
                
                # Tier 3: 1天备份（从最新的Tier 2）
                if self._should_backup(self.tier3_time_file, self.TIER3_INTERVAL):
                    tier2_files = self._get_tier_files(2)
                    if tier2_files:
                        latest_tier2 = tier2_files[-1]
                        new_tier3 = self._get_next_backup_name(3)
                        if self._copy_file(latest_tier2, new_tier3):
                            self._set_backup_time(self.tier3_time_file)
                            self._rotate_backups(3, self.MAX_TIER3_BACKUPS)
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
    
    def restore_from_tier(self, tier: int, version_index: int = -1) -> bool:
        """
        从指定层级恢复备份
        
        Args:
            tier: 备份层级 (1, 2, 或 3)
            version_index: 版本索引，-1表示最新版本，0表示最旧的版本
        
        Returns:
            恢复是否成功
        """
        tier_files = self._get_tier_files(tier)
        
        if not tier_files:
            error_logger.error(f"[BackupManager] Tier {tier} 没有备份文件")
            return False
        
        if version_index < 0 or version_index >= len(tier_files):
            backup_file = tier_files[-1]
        else:
            backup_file = tier_files[version_index]
        
        try:
            if not backup_file.exists():
                app_logger.warning(f"[BackupManager] 备份文件不存在: {backup_file}")
                return False
            
            json_path = Path(self.json_file)
            if json_path.exists():
                current_backup = str(json_path) + ".restore_backup"
                shutil.copy2(str(json_path), current_backup)
            
            shutil.copy2(str(backup_file), str(json_path))
            app_logger.info(f"[BackupManager] 从 Tier {tier} 恢复成功: {backup_file.name}")
            return True
            
        except Exception as e:
            error_logger.error(f"[BackupManager] 恢复失败: {e}")
            return False
    
    def get_backup_info(self) -> dict:
        """获取备份信息"""
        def get_tier_info(tier: int, max_backups: int) -> dict:
            files = self._get_tier_files(tier)
            return {
                "count": len(files),
                "max_backups": max_backups,
                "files": [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for f in files
                ]
            }
        
        return {
            "database": self.base_name,
            "tier1": get_tier_info(1, self.MAX_TIER1_BACKUPS),
            "tier2": get_tier_info(2, self.MAX_TIER2_BACKUPS),
            "tier3": get_tier_info(3, self.MAX_TIER3_BACKUPS)
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
        
        # 标签库数据库
        tags_manager = self.get_manager(TAGS_JSON_FILE)
        tags_manager.start()
        
        # 清单库数据库
        lists_manager = self.get_manager(LISTS_JSON_FILE)
        lists_manager.start()
        
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

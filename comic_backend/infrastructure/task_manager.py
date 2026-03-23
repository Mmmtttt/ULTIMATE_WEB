"""
异步任务管理器
用于管理漫画导入等耗时任务
"""

import os
import json
import time
import threading
import uuid
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass, asdict
from core.constants import (
    IMPORT_TASKS_JSON_FILE,
    JSON_FILE,
    RECOMMENDATION_JSON_FILE,
)
from infrastructure.logger import app_logger, error_logger


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 等待中
    PROCESSING = "processing" # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class ImportTask:
    """导入任务"""
    task_id: str
    status: TaskStatus
    platform: str
    import_type: str  # by_id, by_search, by_list, by_favorite
    target: str       # home, recommendation
    comic_id: Optional[str]
    keyword: Optional[str]
    comic_ids: Optional[List[str]]
    title: str        # 漫画标题（用于显示）
    progress: int     # 0-100
    total_pages: int
    downloaded_pages: int
    message: str      # 状态描述
    create_time: str
    start_time: Optional[str]
    complete_time: Optional[str]
    error_msg: Optional[str]
    result: Optional[Dict]  # 导入结果

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data


class TaskManager:
    """任务管理器（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    COMIC_RECENT_IMPORT_TAG_ID = "tag_recent_import"
    COMIC_RECENT_IMPORT_TAG_NAME = "最近导入"
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, task_file: str = None):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.task_file = task_file or IMPORT_TASKS_JSON_FILE
        self._tasks: Dict[str, ImportTask] = {}
        self._task_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.task_file), exist_ok=True)
        
        # 加载已有任务
        self._load_tasks()
        
        # 启动工作线程
        self._start_worker()
        
        self._initialized = True
        app_logger.info("任务管理器初始化完成")
    
    def _load_tasks(self):
        """加载任务列表"""
        if os.path.exists(self.task_file):
            try:
                with open(self.task_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_data in data.get('tasks', []):
                        task = ImportTask(
                            task_id=task_data['task_id'],
                            status=TaskStatus(task_data['status']),
                            platform=task_data['platform'],
                            import_type=task_data['import_type'],
                            target=task_data['target'],
                            comic_id=task_data.get('comic_id'),
                            keyword=task_data.get('keyword'),
                            comic_ids=task_data.get('comic_ids'),
                            title=task_data.get('title', '未知漫画'),
                            progress=task_data.get('progress', 0),
                            total_pages=task_data.get('total_pages', 0),
                            downloaded_pages=task_data.get('downloaded_pages', 0),
                            message=task_data.get('message', ''),
                            create_time=task_data['create_time'],
                            start_time=task_data.get('start_time'),
                            complete_time=task_data.get('complete_time'),
                            error_msg=task_data.get('error_msg'),
                            result=task_data.get('result')
                        )
                        self._tasks[task.task_id] = task
                app_logger.info(f"加载任务完成，共 {len(self._tasks)} 个任务")
            except Exception as e:
                error_logger.error(f"加载任务失败: {e}")
    
    def _save_tasks(self):
        """保存任务列表"""
        try:
            with self._task_lock:
                data = {
                    'tasks': [task.to_dict() for task in self._tasks.values()],
                    'last_updated': time.strftime("%Y-%m-%dT%H:%M:%S")
                }
                with open(self.task_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            error_logger.error(f"保存任务失败: {e}")
    
    def _start_worker(self):
        """启动工作线程"""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._running = True
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            app_logger.info("任务工作线程已启动")
    
    def _worker_loop(self):
        """工作线程循环"""
        last_timeout_check = 0
        
        while self._running:
            try:
                # 每30秒检查一次超时任务
                current_time = time.time()
                if current_time - last_timeout_check > 30:
                    self._check_timeout_tasks()
                    last_timeout_check = current_time
                
                # 查找待处理的任务
                pending_task = None
                with self._task_lock:
                    for task in self._tasks.values():
                        if task.status == TaskStatus.PENDING:
                            pending_task = task
                            break
                
                if pending_task:
                    self._process_task(pending_task)
                else:
                    # 没有任务时休眠
                    time.sleep(1)
                    
            except Exception as e:
                error_logger.error(f"工作线程异常: {e}")
                time.sleep(1)
    
    def _check_timeout_tasks(self):
        """检查并处理超时任务"""
        try:
            with self._task_lock:
                current_time = time.time()
                for task in self._tasks.values():
                    if task.status == TaskStatus.PROCESSING:
                        # 检查任务是否超时（超过10分钟）
                        if task.start_time:
                            try:
                                start_timestamp = time.mktime(time.strptime(task.start_time, "%Y-%m-%dT%H:%M:%S"))
                                if current_time - start_timestamp > 600:  # 10分钟
                                    task.status = TaskStatus.FAILED
                                    task.complete_time = time.strftime("%Y-%m-%dT%H:%M:%S")
                                    task.error_msg = "任务执行超时"
                                    task.message = "导入失败: 任务执行超时"
                                    error_logger.error(f"任务超时: {task.task_id}")
                            except Exception as e:
                                error_logger.error(f"检查任务超时失败: {e}")
            
            # 保存更新后的任务状态
            self._save_tasks()
        except Exception as e:
            error_logger.error(f"检查超时任务失败: {e}")
    
    def _process_task(self, task: ImportTask):
        """处理单个任务"""
        app_logger.info(f"开始处理任务: {task.task_id}, 漫画: {task.title}")
        
        # 更新任务状态
        task.status = TaskStatus.PROCESSING
        task.start_time = time.strftime("%Y-%m-%dT%H:%M:%S")
        task.message = "正在导入..."
        self._save_tasks()
        
        try:
            # 执行导入
            result = self._execute_import(task)
            
            if result.get('success'):
                task.status = TaskStatus.COMPLETED
                task.complete_time = time.strftime("%Y-%m-%dT%H:%M:%S")
                task.progress = 100
                task.message = "导入完成"
                task.result = result
                app_logger.info(f"任务完成: {task.task_id}")
            else:
                task.status = TaskStatus.FAILED
                task.complete_time = time.strftime("%Y-%m-%dT%H:%M:%S")
                task.error_msg = result.get('error', '导入失败')
                task.message = f"导入失败: {task.error_msg}"
                error_logger.error(f"任务失败: {task.task_id}, 错误: {task.error_msg}")
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.complete_time = time.strftime("%Y-%m-%dT%H:%M:%S")
            task.error_msg = str(e)
            task.message = f"导入异常: {str(e)}"
            error_logger.error(f"任务异常: {task.task_id}, 错误: {e}")
        
        self._save_tasks()
    
    def _execute_import(self, task: ImportTask) -> Dict:
        """执行导入操作"""
        import sys
        import os
        
        # 添加项目路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from third_party.platform_service import get_platform_service
        from core.platform import Platform
        from infrastructure.persistence.json_storage import JsonStorage
        from core.constants import TAGS_JSON_FILE
        from core.utils import normalize_total_page
        
        try:
            platform = Platform(task.platform)
            platform_service = get_platform_service()
            
            # 从独立的标签数据库读取tag
            tag_storage = JsonStorage(TAGS_JSON_FILE)
            tag_db_data = tag_storage.read()
            existing_tags = tag_db_data.get('tags', [])
            
            # 获取漫画/推荐漫画数据库文件
            db_file = JSON_FILE if task.target == 'home' else RECOMMENDATION_JSON_FILE
            storage = JsonStorage(db_file)
            db_data = storage.read()
            from core.utils import normalize_total_page
            
            # 使用 PlatformService 获取数据
            # 搜索或获取详情
            if task.import_type == 'by_id':
                result = platform_service.get_album_by_id(platform, task.comic_id)
                albums = result.get('albums', [])
            elif task.import_type == 'by_search':
                result = platform_service.search_albums(platform, task.keyword, max_pages=1, fast_mode=False)
                albums = result.get('albums', [])
            elif task.import_type == 'by_list':
                # 批量导入：遍历所有ID
                albums = []
                comic_ids = task.comic_ids or []
                total_comics = len(comic_ids)
                for idx, comic_id in enumerate(comic_ids):
                    try:
                        result = platform_service.get_album_by_id(platform, comic_id)
                        if result.get('albums'):
                            albums.extend(result['albums'])
                        
                        # 更新任务信息 - 显示漫画进度
                        task.title = f"批量导入 ({idx+1}/{total_comics})"
                        task.message = f"正在处理第 {idx+1}/{total_comics} 部漫画..."
                        task.progress = int((idx + 1) / total_comics * 50) if total_comics > 0 else 0
                        self._save_tasks()
                    except Exception as e:
                        error_logger.error(f"获取漫画 {comic_id} 详情失败: {e}")
                        continue
            else:
                return {'success': False, 'error': '不支持的导入类型'}
            
            if not albums:
                return {'success': False, 'error': '未找到漫画'}
            
            # 如果是批量导入，更新任务标题
            if task.import_type == 'by_list':
                task.title = f"批量导入 ({len(albums)} 部漫画)"
                task.total_pages = len(albums)
                self._save_tasks()
            else:
                # 更新任务信息
                album = albums[0]
                task.title = album.get('title', '未知漫画')
                task.total_pages = normalize_total_page(album.get('pages', 0))
                self._save_tasks()
            
            # 转换数据
            converted_data = self._convert_to_standard_format(albums, existing_tags, platform)
            
            # 如果是主页导入，需要下载图片
            if task.target == 'home':
                from core.platform import get_original_id
                from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR
                
                total_comics = len(converted_data.get('comics', []))
                for idx, comic in enumerate(converted_data.get('comics', [])):
                    try:
                        original_id = get_original_id(comic['id'])
                        
                        # 如果是批量导入，更新进度 - 显示漫画进度
                        if task.import_type == 'by_list':
                            task.message = f"正在下载第 {idx+1}/{total_comics} 部漫画..."
                            task.progress = int(50 + (idx + 1) / total_comics * 40) if total_comics > 0 else 50
                            task.downloaded_pages = idx + 1
                            task.total_pages = total_comics
                            self._save_tasks()
                        
                        # 使用 PlatformService 下载漫画
                        download_dir = JM_PICTURES_DIR if platform == Platform.JM else PK_PICTURES_DIR
                        detail, success = platform_service.download_album(
                            platform,
                            original_id,
                            download_dir=download_dir,
                            show_progress=False
                        )
                        
                        if success:
                            comic['total_page'] = normalize_total_page(
                                detail.get('local_pages', detail.get('pages_count', comic['total_page'])),
                                default=normalize_total_page(comic.get('total_page', 0))
                            )
                        
                    except Exception as e:
                        error_logger.error(f"下载漫画失败: {e}")
            
            # 保存到数据库
            actual_imported_count = self._save_to_database(converted_data, task.target)
            
            return {
                'success': True,
                'imported_count': actual_imported_count,
                'title': task.title
            }
            
        except Exception as e:
            error_logger.error(f"执行导入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _convert_to_standard_format(self, albums: List[Dict], existing_tags: List[Dict], platform) -> Dict:
        """将平台数据转换为系统标准格式"""
        from core.platform import add_platform_prefix, get_original_id, PLATFORM_PREFIXES, Platform
        from datetime import datetime
        import os
        import requests
        from PIL import Image
        from io import BytesIO
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        from core.utils import get_preview_pages, normalize_total_page
        
        tag_name_to_id = {}
        existing_tag_ids = set()
        max_tag_num = 0
        
        for tag in existing_tags:
            tag_name_to_id[tag["name"]] = tag["id"]
            existing_tag_ids.add(tag["id"])
            if tag["id"].startswith("tag_"):
                try:
                    num = int(tag["id"][4:])
                    max_tag_num = max(max_tag_num, num)
                except ValueError:
                    pass
        
        new_tags = []
        comics = []
        
        # 使用 PlatformService 获取预览图片 URL
        from third_party.platform_service import get_platform_service
        platform_service = get_platform_service()
        
        for album in albums:
            comic_tag_ids = []
            seen_tags = set()
            
            for tag_name in album.get("tags", []):
                if tag_name in seen_tags:
                    continue
                seen_tags.add(tag_name)
                
                if tag_name not in tag_name_to_id:
                    max_tag_num += 1
                    new_id = f"tag_{max_tag_num:03d}"
                    
                    while new_id in existing_tag_ids:
                        max_tag_num += 1
                        new_id = f"tag_{max_tag_num:03d}"
                    
                    tag_name_to_id[tag_name] = new_id
                    existing_tag_ids.add(new_id)
                    new_tags.append({
                        "id": new_id,
                        "name": tag_name,
                        "create_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })
                
                comic_tag_ids.append(tag_name_to_id[tag_name])
            
            album_id = str(album.get("album_id", ""))
            cover_url = album.get("cover_url", "")
            local_cover_path = self._download_cover(album_id, cover_url, platform)
            
            comic = {
                "id": add_platform_prefix(platform, album_id),
                "title": album.get("title", ""),
                "title_jp": album.get("title_jp", ""),
                "author": album.get("author", ""),
                "desc": album.get("desc", ""),
                "cover_path": local_cover_path if local_cover_path else cover_url,
                "total_page": normalize_total_page(album.get("pages", 0)),
                "current_page": 1,
                "score": None,
                "tag_ids": comic_tag_ids,
                "list_ids": [],
                "create_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "last_read_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "is_deleted": False,
                "preview_image_urls": [],
                "preview_pages": []
            }
            
            # 使用 PlatformService 获取预览图片 URL
            try:
                total_page = normalize_total_page(comic.get('total_page', 0))
                preview_pages = get_preview_pages(total_page)
                
                # 获取预览图片 URL
                preview_urls = platform_service.get_preview_image_urls(platform, album_id, preview_pages)
                
                # 存储预览图片 URL 和页码
                comic['preview_image_urls'] = preview_urls
                comic['preview_pages'] = preview_pages
                
                from infrastructure.logger import app_logger
                app_logger.info(f"获取推荐页预览图片成功: {album_id}, 共 {len(preview_urls)} 张")
            except Exception as e:
                from infrastructure.logger import error_logger
                error_logger.error(f"获取推荐页预览图片失败 {album_id}: {e}")
                comic['preview_image_urls'] = []
                comic['preview_pages'] = []
            
            comics.append(comic)
        
        return {
            "comics": comics,
            "tags": new_tags
        }
    
    def _download_cover(self, album_id: str, cover_url: str, platform) -> str:
        """下载封面图片并保存到本地
        
        使用 PlatformService 统一处理不同平台的封面下载
        """
        import os
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        from core.platform import Platform, PLATFORM_PREFIXES
        from third_party.platform_service import get_platform_service
        
        if not album_id:
            return ""
        
        try:
            cover_dir = JM_COVER_DIR if platform == Platform.JM else PK_COVER_DIR
            os.makedirs(cover_dir, exist_ok=True)
            cover_path = os.path.join(cover_dir, f"{album_id}.jpg")
            
            # 已有本地封面，直接返回
            if os.path.exists(cover_path):
                platform_prefix = PLATFORM_PREFIXES.get(platform, "")
                return f"/static/cover/{platform_prefix}/{album_id}.jpg" if platform_prefix else f"/static/cover/{album_id}.jpg"
            
            # 使用 PlatformService 下载封面
            platform_service = get_platform_service()
            detail, success = platform_service.download_cover(
                platform,
                album_id,
                save_path=cover_path,
                show_progress=False
            )
            
            if success and os.path.exists(cover_path):
                platform_prefix = PLATFORM_PREFIXES.get(platform, "")
                local_path = f"/static/cover/{platform_prefix}/{album_id}.jpg" if platform_prefix else f"/static/cover/{album_id}.jpg"
                app_logger.info(f"封面下载成功: {album_id} -> {local_path}")
                return local_path
            else:
                error_logger.warning(f"封面下载失败: {album_id}")
                return ""
            
        except Exception as e:
            error_logger.error(f"下载封面失败 {album_id}: {e}")
            return ""

    @staticmethod
    def _normalize_tag_content_type(tag: Dict[str, Any]) -> str:
        value = str((tag or {}).get("content_type", "comic") or "").strip().lower()
        return value or "comic"

    def _ensure_comic_recent_import_tag_id(self, tag_db_data: Dict[str, Any]) -> Optional[str]:
        from datetime import datetime

        tags = tag_db_data.setdefault("tags", [])
        if not isinstance(tags, list):
            tags = []
            tag_db_data["tags"] = tags

        configured = next(
            (
                tag for tag in tags
                if isinstance(tag, dict)
                and str(tag.get("id", "")).strip() == self.COMIC_RECENT_IMPORT_TAG_ID
            ),
            None,
        )
        if configured and self._normalize_tag_content_type(configured) == "comic":
            if str(configured.get("name", "")).strip() != self.COMIC_RECENT_IMPORT_TAG_NAME:
                configured["name"] = self.COMIC_RECENT_IMPORT_TAG_NAME
            configured["content_type"] = "comic"
            return self.COMIC_RECENT_IMPORT_TAG_ID

        for tag in tags:
            if not isinstance(tag, dict):
                continue
            if self._normalize_tag_content_type(tag) != "comic":
                continue
            if str(tag.get("name", "")).strip() == self.COMIC_RECENT_IMPORT_TAG_NAME:
                tag_id = str(tag.get("id", "")).strip()
                if tag_id:
                    return tag_id

        new_tag_id = self.COMIC_RECENT_IMPORT_TAG_ID
        existing_ids = {
            str(tag.get("id", "")).strip()
            for tag in tags
            if isinstance(tag, dict)
        }
        if new_tag_id in existing_ids:
            suffix = 1
            while f"{new_tag_id}_{suffix}" in existing_ids:
                suffix += 1
            new_tag_id = f"{new_tag_id}_{suffix}"

        tags.append(
            {
                "id": new_tag_id,
                "name": self.COMIC_RECENT_IMPORT_TAG_NAME,
                "content_type": "comic",
                "create_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        app_logger.info(f"创建漫画系统标签: {self.COMIC_RECENT_IMPORT_TAG_NAME} ({new_tag_id})")
        return new_tag_id
    
    def _save_to_database(self, converted_data: Dict, target: str) -> int:
        """保存到数据库"""
        from infrastructure.persistence.json_storage import JsonStorage
        from core.constants import TAGS_JSON_FILE
        from core.utils import normalize_total_page
        
        if target == 'home':
            json_file = JSON_FILE
            comics_key = 'comics'
            total_key = 'total_comics'
        else:
            json_file = RECOMMENDATION_JSON_FILE
            comics_key = 'recommendations'
            total_key = 'total_recommendations'
        
        storage = JsonStorage(json_file)
        db_data = storage.read()
        
        # 保存漫画/推荐漫画数据
        new_comics = converted_data.get('comics', [])
        existing_ids = {c['id'] for c in db_data.get(comics_key, [])}
        actual_new_comics = [comic for comic in new_comics if comic['id'] not in existing_ids]
        
        # 处理tag保存到独立的标签数据库
        tag_storage = JsonStorage(TAGS_JSON_FILE)
        tag_db_data = tag_storage.read()

        recent_import_tag_id = ""
        if actual_new_comics:
            recent_import_tag_id = self._ensure_comic_recent_import_tag_id(tag_db_data) or ""

            # 清除旧漫画的最近导入tag
            if recent_import_tag_id:
                for comic in db_data.get(comics_key, []):
                    if recent_import_tag_id in comic.get('tag_ids', []):
                        comic['tag_ids'].remove(recent_import_tag_id)
                app_logger.info(f"清除旧漫画的'{self.COMIC_RECENT_IMPORT_TAG_NAME}'标签")
        
        # 添加新漫画并设置最近导入tag
        for comic in actual_new_comics:
            comic['total_page'] = normalize_total_page(comic.get('total_page', 0))
            if recent_import_tag_id and recent_import_tag_id not in comic.get('tag_ids', []):
                comic.setdefault('tag_ids', []).append(recent_import_tag_id)
            
            db_data.setdefault(comics_key, []).append(comic)
            existing_ids.add(comic['id'])
        
        if actual_new_comics and recent_import_tag_id:
            app_logger.info(f"为 {len(actual_new_comics)} 个新漫画添加'{self.COMIC_RECENT_IMPORT_TAG_NAME}'标签")
        
        # 保存新tag到主数据库
        new_tags = converted_data.get('tags', [])
        existing_tag_ids = {t['id'] for t in tag_db_data.get('tags', [])}
        for tag in new_tags:
            if tag['id'] not in existing_tag_ids:
                tag_db_data.setdefault('tags', []).append(tag)
                existing_tag_ids.add(tag['id'])
        
        # 更新tag_last_updated
        tag_db_data['last_updated'] = time.strftime("%Y-%m-%d")
        tag_storage.write(tag_db_data)
        
        # 更新漫画/推荐漫画数据
        db_data[total_key] = len(db_data.get(comics_key, []))
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        storage.write(db_data)
        return len(actual_new_comics)
    
    def create_task(
        self,
        platform: str,
        import_type: str,
        target: str,
        comic_id: Optional[str] = None,
        keyword: Optional[str] = None,
        comic_ids: Optional[List[str]] = None
    ) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        
        task = ImportTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            platform=platform,
            import_type=import_type,
            target=target,
            comic_id=comic_id,
            keyword=keyword,
            comic_ids=comic_ids,
            title="等待导入...",
            progress=0,
            total_pages=0,
            downloaded_pages=0,
            message="等待处理...",
            create_time=time.strftime("%Y-%m-%dT%H:%M:%S"),
            start_time=None,
            complete_time=None,
            error_msg=None,
            result=None
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
        
        self._save_tasks()
        app_logger.info(f"创建任务: {task_id}")
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[ImportTask]:
        """获取任务信息"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self, limit: int = 50) -> List[ImportTask]:
        """获取所有任务（按时间倒序）"""
        tasks = sorted(
            self._tasks.values(),
            key=lambda t: t.create_time,
            reverse=True
        )
        return tasks[:limit]
    
    def get_active_tasks(self) -> List[ImportTask]:
        """获取进行中的任务"""
        return [
            task for task in self._tasks.values()
            if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
        ]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.message = "已取消"
            task.complete_time = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save_tasks()
            return True
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            with self._task_lock:
                del self._tasks[task_id]
            self._save_tasks()
            return True
        return False
    
    def clear_completed_tasks(self, keep_count: int = 20) -> int:
        """清理已完成的任务，保留最近N个"""
        with self._task_lock:
            completed_tasks = [
                (tid, t) for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            
            # 按完成时间排序
            completed_tasks.sort(key=lambda x: x[1].complete_time or '', reverse=True)
            
            # 删除旧任务
            deleted_count = 0
            for tid, _ in completed_tasks[keep_count:]:
                del self._tasks[tid]
                deleted_count += 1
            
            if deleted_count > 0:
                self._save_tasks()
            
            return deleted_count


# 全局任务管理器实例
task_manager = TaskManager()

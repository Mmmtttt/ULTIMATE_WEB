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
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, task_file: str = "data/meta_data/import_tasks.json"):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.task_file = task_file
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
        
        from third_party.adapter_factory import AdapterFactory
        from core.platform import Platform
        from infrastructure.persistence.json_storage import JsonStorage
        
        try:
            platform = Platform(task.platform)
            
            # 获取适配器
            db_file = 'data/meta_data/comics_database.json' if task.target == 'home' else 'data/meta_data/recommendations_database.json'
            storage = JsonStorage(db_file)
            db_data = storage.read()
            existing_tags = db_data.get('tags', [])
            
            # 将Platform对象转换为适配器名称
            adapter_name = 'jmcomic' if platform == Platform.JM else 'jmcomic'  # 暂时只支持JM
            # 传递空配置字典，因为JMComicAdapter不需要标签作为配置
            adapter = AdapterFactory.get_adapter(adapter_name, {})
            
            # 搜索或获取详情
            if task.import_type == 'by_id':
                result = adapter.get_album_by_id(task.comic_id)
                albums = result.get('albums', [])
            elif task.import_type == 'by_search':
                result = adapter.search_albums(task.keyword, max_pages=1)
                albums = result.get('albums', [])
            elif task.import_type == 'by_list':
                # 批量导入：遍历所有ID
                albums = []
                comic_ids = task.comic_ids or []
                total_comics = len(comic_ids)
                for idx, comic_id in enumerate(comic_ids):
                    try:
                        result = adapter.get_album_by_id(comic_id)
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
                task.total_pages = album.get('pages', 0)
                self._save_tasks()
            
            # 转换数据
            converted_data = self._convert_to_standard_format(albums, existing_tags, platform)
            
            # 如果是主页导入，需要下载图片
            if task.target == 'home':
                from core.platform import get_original_id
                from core.constants import JM_PICTURES_DIR
                
                total_comics = len(converted_data.get('comics', []))
                for idx, comic in enumerate(converted_data.get('comics', [])):
                    try:
                        original_id = get_original_id(comic['id'])
                        album_id = int(original_id)
                        
                        # 如果是批量导入，更新进度 - 显示漫画进度
                        if task.import_type == 'by_list':
                            task.message = f"正在下载第 {idx+1}/{total_comics} 部漫画..."
                            task.progress = int(50 + (idx + 1) / total_comics * 40) if total_comics > 0 else 50
                            task.downloaded_pages = idx + 1
                            task.total_pages = total_comics
                            self._save_tasks()
                        
                        # 下载漫画
                        jmcomic_path = os.path.join(
                            os.path.dirname(__file__), '..', 
                            'third_party', 'JMComic-Crawler-Python'
                        )
                        if jmcomic_path not in sys.path:
                            sys.path.insert(0, jmcomic_path)
                        
                        from jmcomic_api import download_album
                        
                        detail, success = download_album(
                            album_id,
                            download_dir=JM_PICTURES_DIR,
                            show_progress=False,
                            decode_images=True
                        )
                        
                        if success:
                            comic['total_page'] = detail.get('local_pages', comic['total_page'])
                        
                    except Exception as e:
                        error_logger.error(f"下载漫画失败: {e}")
            
            # 保存到数据库
            self._save_to_database(converted_data, task.target)
            
            return {
                'success': True,
                'imported_count': len(converted_data.get('comics', [])),
                'title': task.title
            }
            
        except Exception as e:
            error_logger.error(f"执行导入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _convert_to_standard_format(self, albums: List[Dict], existing_tags: List[Dict], platform) -> Dict:
        """将平台数据转换为系统标准格式"""
        from core.platform import add_platform_prefix, get_original_id, PLATFORM_PREFIXES
        from datetime import datetime
        import os
        import requests
        from PIL import Image
        from io import BytesIO
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        
        # 标签去重和ID生成
        tag_name_to_id = {}
        tag_id_counter = 1
        
        # 处理已有标签
        for tag in existing_tags:
            tag_name_to_id[tag["name"]] = tag["id"]
        
        new_tags = []
        comics = []
        
        for album in albums:
            # 处理标签
            comic_tag_ids = []
            for tag_name in album.get("tags", []):
                if tag_name not in tag_name_to_id:
                    # 新标签
                    tag_id = f"tag_{tag_id_counter:03d}"
                    tag_name_to_id[tag_name] = tag_id
                    new_tags.append({
                        "id": tag_id,
                        "name": tag_name,
                        "create_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    })
                    tag_id_counter += 1
                comic_tag_ids.append(tag_name_to_id[tag_name])
            
            # 下载并保存封面
            album_id = str(album.get("album_id", ""))
            cover_url = album.get("cover_url", "")
            local_cover_path = self._download_cover(album_id, cover_url, platform)
            
            # 构建标准漫画格式
            comic = {
                "id": add_platform_prefix(platform, album_id),
                "title": album.get("title", ""),
                "title_jp": album.get("title_jp", ""),
                "author": album.get("author", ""),
                "desc": album.get("desc", ""),
                "cover_path": local_cover_path if local_cover_path else cover_url,
                "total_page": album.get("pages", 0),
                "current_page": 1,
                "score": None,
                "tag_ids": comic_tag_ids,
                "list_ids": [],
                "create_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "last_read_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "is_deleted": False
            }
            comics.append(comic)
        
        return {
            "comics": comics,
            "tags": new_tags
        }
    
    def _download_cover(self, album_id: str, cover_url: str, platform) -> str:
        """下载封面图片并保存到本地"""
        import os
        import requests
        from PIL import Image
        from io import BytesIO
        from core.constants import JM_COVER_DIR, PK_COVER_DIR, COVER_WIDTH, COVER_QUALITY
        from core.platform import Platform, PLATFORM_PREFIXES
        
        if not cover_url:
            return ""
        
        try:
            # 确定封面目录
            if platform == Platform.JM:
                cover_dir = JM_COVER_DIR
            elif platform == Platform.PK:
                cover_dir = PK_COVER_DIR
            else:
                return ""
            
            # 确保封面目录存在
            os.makedirs(cover_dir, exist_ok=True)
            
            # 封面保存路径
            cover_path = os.path.join(cover_dir, f"{album_id}.jpg")
            
            # 如果封面已存在，直接返回本地路径
            if os.path.exists(cover_path):
                platform_prefix = PLATFORM_PREFIXES.get(platform, "")
                if platform_prefix:
                    return f"/static/cover/{platform_prefix}/{album_id}.jpg"
                else:
                    return f"/static/cover/{album_id}.jpg"
            
            # 下载封面
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(cover_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 处理图片
            with Image.open(BytesIO(response.content)) as img:
                # 转换为RGB模式（处理RGBA等格式）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # 计算缩放比例
                width, height = img.size
                ratio = COVER_WIDTH / width
                new_height = int(height * ratio)
                
                # 缩放图片
                resized_img = img.resize((COVER_WIDTH, new_height), Image.LANCZOS)
                
                # 保存为JPEG格式
                resized_img.save(cover_path, 'JPEG', quality=COVER_QUALITY)
            
            platform_prefix = PLATFORM_PREFIXES.get(platform, "")
            if platform_prefix:
                local_path = f"/static/cover/{platform_prefix}/{album_id}.jpg"
            else:
                local_path = f"/static/cover/{album_id}.jpg"
            app_logger.info(f"封面下载成功: {album_id} -> {local_path}")
            return local_path
            
        except Exception as e:
            error_logger.error(f"下载封面失败 {album_id}: {e}")
            return ""
    
    def _save_to_database(self, converted_data: Dict, target: str):
        """保存到数据库"""
        from infrastructure.persistence.json_storage import JsonStorage
        
        if target == 'home':
            json_file = 'data/meta_data/comics_database.json'
            comics_key = 'comics'
            total_key = 'total_comics'
        else:
            json_file = 'data/meta_data/recommendations_database.json'
            comics_key = 'recommendations'
            total_key = 'total_recommendations'
        
        storage = JsonStorage(json_file)
        db_data = storage.read()
        
        # 添加新漫画
        new_comics = converted_data.get('comics', [])
        existing_ids = {c['id'] for c in db_data.get(comics_key, [])}
        
        for comic in new_comics:
            if comic['id'] not in existing_ids:
                db_data.setdefault(comics_key, []).append(comic)
                existing_ids.add(comic['id'])
        
        # 添加新标签
        new_tags = converted_data.get('tags', [])
        existing_tag_ids = {t['id'] for t in db_data.get('tags', [])}
        for tag in new_tags:
            if tag['id'] not in existing_tag_ids:
                db_data.setdefault('tags', []).append(tag)
                existing_tag_ids.add(tag['id'])
        
        # 更新统计
        db_data[total_key] = len(db_data.get(comics_key, []))
        db_data['last_updated'] = time.strftime("%Y-%m-%d")
        
        storage.write(db_data)
    
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

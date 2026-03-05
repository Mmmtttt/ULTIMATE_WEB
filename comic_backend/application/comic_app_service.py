from typing import List, Optional
import os
from domain.comic import Comic, ComicRepository
from domain.tag import TagRepository
from infrastructure.persistence.repositories import ComicJsonRepository, TagJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, get_preview_pages

FAVORITES_LIST_ID = "list_favorites"


class ComicAppService:
    def __init__(
        self,
        comic_repo: ComicRepository = None,
        tag_repo: TagRepository = None
    ):
        self._comic_repo = comic_repo or ComicJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
    
    def get_comic_list(
        self,
        sort_type: str = None,
        min_score: float = None,
        max_score: float = None
    ) -> ServiceResult:
        try:
            app_logger.info(f"[get_comic_list] sort_type={sort_type}, min_score={min_score}, max_score={max_score}")
            comics = self._comic_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 过滤掉已删除的漫画
            comics = [c for c in comics if not c.is_deleted]
            
            if min_score is not None:
                comics = [c for c in comics if c.score is not None and c.score >= min_score]
            if max_score is not None:
                comics = [c for c in comics if c.score is not None and c.score <= max_score]
            
            app_logger.info(f"[get_comic_list] 排序前漫画数量: {len(comics)}")
            if sort_type:
                app_logger.info(f"[get_comic_list] 执行排序: {sort_type}")
            
            if sort_type == "create_time":
                comics = sorted(comics, key=lambda c: c.create_time or "", reverse=True)
            elif sort_type == "score":
                comics = sorted(comics, key=lambda c: c.score or 0, reverse=True)
            elif sort_type == "read_time":
                comics = sorted(comics, key=lambda c: c.last_read_time or "", reverse=True)
            elif sort_type == "read_status":
                def read_status_sort_key(c):
                    is_read = c.current_page >= c.total_page if c.total_page > 0 else False
                    return (is_read, -(c.score or 0))
                comics = sorted(comics, key=read_status_sort_key)
            
            app_logger.info(f"[get_comic_list] 排序后漫画数量: {len(comics)}")
            
            comic_list = []
            for c in comics:
                # 确保封面存在（特别是 PK 平台，必要时用第 1 张图片生成）
                try:
                    self._ensure_cover(c)
                except Exception as e:
                    error_logger.error(f"确保漫画封面失败（列表）: {c.id}, {e}")
                
                is_favorited = FAVORITES_LIST_ID in c.list_ids
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "desc": c.desc,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "current_page": c.current_page,
                    "score": c.score,
                    "tag_ids": c.tag_ids,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "last_read_time": c.last_read_time,
                    "create_time": c.create_time,
                    "is_favorited": is_favorited
                }
                comic_list.append(comic_info)
            
            app_logger.info(f"获取漫画列表成功，共 {len(comic_list)} 个漫画")
            return ServiceResult.ok(comic_list)
        except Exception as e:
            error_logger.error(f"获取漫画列表失败: {e}")
            return ServiceResult.error("获取漫画列表失败")
    
    def get_comic_detail(self, comic_id: str) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            # 确保封面存在（如果缺失或文件不存在，用第 1 张图片生成）
            try:
                self._ensure_cover(comic)
            except Exception as e:
                error_logger.error(f"确保漫画封面失败（详情）: {comic_id}, {e}")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            preview_pages = get_preview_pages(comic.total_page)
            
            is_favorited = FAVORITES_LIST_ID in comic.list_ids
            
            detail = {
                "id": comic.id,
                "title": comic.title,
                "title_jp": comic.title_jp,
                "author": comic.author,
                "desc": comic.desc,
                "cover_path": comic.cover_path,
                "total_page": comic.total_page,
                "current_page": comic.current_page,
                "score": comic.score,
                "tag_ids": comic.tag_ids,
                "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in comic.tag_ids],
                "preview_images": [f"/api/v1/comic/image?comic_id={comic_id}&page_num={p}" for p in preview_pages],
                "preview_pages": preview_pages,
                "last_read_time": comic.last_read_time,
                "create_time": comic.create_time,
                "list_ids": comic.list_ids,
                "is_favorited": is_favorited
            }
            
            app_logger.info(f"获取漫画详情成功: {comic_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取漫画详情失败: {e}")
            return ServiceResult.error("获取漫画详情失败")
    
    def update_score(self, comic_id: str, score: float) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if not comic.update_score(score):
                return ServiceResult.error("评分验证失败")
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("保存评分失败")
            
            app_logger.info(f"更新漫画评分成功: {comic_id}, 评分: {score}")
            return ServiceResult.ok({"comic_id": comic_id, "score": score}, "评分保存成功")
        except Exception as e:
            error_logger.error(f"更新漫画评分失败: {e}")
            return ServiceResult.error("更新评分失败")
    
    def update_progress(self, comic_id: str, current_page: int) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if not comic.update_progress(current_page):
                return ServiceResult.error("页码超出范围")
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("保存进度失败")
            
            app_logger.info(f"保存阅读进度成功: {comic_id}, 页码: {current_page}")
            return ServiceResult.ok({"comic_id": comic_id, "current_page": current_page}, "进度保存成功")
        except Exception as e:
            error_logger.error(f"保存阅读进度失败: {e}")
            return ServiceResult.error("保存进度失败")
    
    def bind_tags(self, comic_id: str, tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.bind_tags(tag_ids)
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("绑定标签失败")
            
            app_logger.info(f"绑定漫画标签成功: {comic_id}, 标签: {tag_ids}")
            return ServiceResult.ok({"comic_id": comic_id, "tag_ids": tag_ids}, "标签绑定成功")
        except Exception as e:
            error_logger.error(f"绑定漫画标签失败: {e}")
            return ServiceResult.error("绑定标签失败")
    
    def update_meta(self, comic_id: str, meta: dict) -> ServiceResult:
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.update_meta(meta)
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("更新元数据失败")
            
            app_logger.info(f"更新漫画元数据成功: {comic_id}")
            return ServiceResult.ok(comic.to_dict(), "更新成功")
        except Exception as e:
            error_logger.error(f"更新漫画元数据失败: {e}")
            return ServiceResult.error("更新元数据失败")
    
    def search(self, keyword: str) -> ServiceResult:
        try:
            comics = self._comic_repo.search(keyword)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            results = []
            for c in comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids]
                }
                results.append(comic_info)
            
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"搜索失败: {e}")
            return ServiceResult.error("搜索失败")
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> ServiceResult:
        try:
            comics = self._comic_repo.filter_by_tags(include_tags, exclude_tags)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            results = []
            for c in comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids]
                }
                results.append(comic_info)
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def batch_add_tags(self, comic_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.add_tags(tag_ids)
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为{updated_count}个漫画添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, comic_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.remove_tags(tag_ids)
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功从{updated_count}个漫画移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
    
    def get_trash_list(self) -> ServiceResult:
        """获取回收站漫画列表"""
        try:
            comics = self._comic_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            # 只获取已删除的漫画
            trash_comics = [c for c in comics if c.is_deleted]
            
            comic_list = []
            for c in trash_comics:
                comic_info = {
                    "id": c.id,
                    "title": c.title,
                    "author": c.author,
                    "cover_path": c.cover_path,
                    "total_page": c.total_page,
                    "score": c.score,
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.tag_ids],
                    "create_time": c.create_time
                }
                comic_list.append(comic_info)
            
            app_logger.info(f"获取回收站列表成功，共 {len(comic_list)} 个漫画")
            return ServiceResult.ok(comic_list)
        except Exception as e:
            error_logger.error(f"获取回收站列表失败: {e}")
            return ServiceResult.error("获取回收站列表失败")
    
    def move_to_trash(self, comic_id: str) -> ServiceResult:
        """移动漫画到回收站"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.move_to_trash()
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("移入回收站失败")
            
            app_logger.info(f"漫画移入回收站: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已移入回收站")
        except Exception as e:
            error_logger.error(f"移入回收站失败: {e}")
            return ServiceResult.error("移入回收站失败")
    
    def restore_from_trash(self, comic_id: str) -> ServiceResult:
        """从回收站恢复漫画"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic.restore_from_trash()
            
            if not self._comic_repo.save(comic):
                return ServiceResult.error("恢复失败")
            
            app_logger.info(f"漫画从回收站恢复: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已从回收站恢复")
        except Exception as e:
            error_logger.error(f"从回收站恢复失败: {e}")
            return ServiceResult.error("从回收站恢复失败")
    
    def batch_move_to_trash(self, comic_ids: List[str]) -> ServiceResult:
        """批量移动漫画到回收站"""
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.move_to_trash()
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量移入回收站成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已将{updated_count}个漫画移入回收站")
        except Exception as e:
            error_logger.error(f"批量移入回收站失败: {e}")
            return ServiceResult.error("批量移入回收站失败")
    
    def batch_restore_from_trash(self, comic_ids: List[str]) -> ServiceResult:
        """批量从回收站恢复漫画"""
        try:
            updated_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    comic.restore_from_trash()
                    if self._comic_repo.save(comic):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量从回收站恢复成功: {updated_count}个漫画")
            return ServiceResult.ok({"updated_count": updated_count}, f"已恢复{updated_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量从回收站恢复失败: {e}")
            return ServiceResult.error("批量从回收站恢复失败")
    
    def delete_permanently(self, comic_id: str) -> ServiceResult:
        """永久删除漫画"""
        try:
            comic = self._comic_repo.get_by_id(comic_id)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            self._cleanup_comic_files(comic)
            
            if not self._comic_repo.delete(comic_id):
                return ServiceResult.error("永久删除失败")
            
            app_logger.info(f"漫画已永久删除: {comic_id}")
            return ServiceResult.ok({"comic_id": comic_id}, "已永久删除")
        except Exception as e:
            error_logger.error(f"永久删除失败: {e}")
            return ServiceResult.error("永久删除失败")
    
    def _cleanup_comic_files(self, comic):
        """清理漫画相关的所有文件"""
        import shutil
        from core.platform import get_platform_from_id
        from core.constants import COVER_DIR
        from utils.file_parser import file_parser
        
        platform = get_platform_from_id(comic.id)
        
        pictures_dir = None
        try:
            pictures_dir = file_parser._get_comic_dir(comic.id)
        except Exception as e:
            error_logger.error(f"推断漫画图片目录失败: {e}")
        
        if pictures_dir and os.path.exists(pictures_dir):
            try:
                shutil.rmtree(pictures_dir)
                app_logger.info(f"已删除漫画图片目录: {pictures_dir}")
            except Exception as e:
                error_logger.error(f"删除漫画图片目录失败: {e}")
        
        if comic.cover_path:
            cover_path_full = os.path.join(COVER_DIR, comic.cover_path)
            if os.path.exists(cover_path_full):
                try:
                    os.remove(cover_path_full)
                    app_logger.info(f"已删除漫画封面: {cover_path_full}")
                except Exception as e:
                    error_logger.error(f"删除漫画封面失败: {e}")
    
    def batch_delete_permanently(self, comic_ids: List[str]) -> ServiceResult:
        """批量永久删除漫画"""
        try:
            deleted_count = 0
            for comic_id in comic_ids:
                comic = self._comic_repo.get_by_id(comic_id)
                if comic:
                    self._cleanup_comic_files(comic)
                if self._comic_repo.delete(comic_id):
                    deleted_count += 1
            
            if deleted_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            app_logger.info(f"批量永久删除成功: {deleted_count}个漫画")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"已永久删除{deleted_count}个漫画")
        except Exception as e:
            error_logger.error(f"批量永久删除失败: {e}")
            return ServiceResult.error("批量永久删除失败")
    
    def _ensure_cover(self, comic: Comic):
        """
        确保漫画有可用封面：
        - 如果本地封面文件不存在，则尝试用第 1 张图片生成封面
        - 成功后会更新并持久化 cover_path
        """
        from core.platform import get_platform_from_id, get_original_id, Platform
        from core.constants import JM_COVER_DIR, PK_COVER_DIR
        from utils.file_parser import file_parser
        from utils.image_handler import ImageHandler
        
        platform = get_platform_from_id(comic.id)
        if platform not in (Platform.JM, Platform.PK):
            return
        
        original_id = get_original_id(comic.id)
        
        # 计算本地封面文件应在的路径
        if platform == Platform.JM:
            cover_dir = JM_COVER_DIR
            expected_prefix = "JM"
        else:
            cover_dir = PK_COVER_DIR
            expected_prefix = "PK"
        
        cover_full_path = os.path.join(cover_dir, f"{original_id}.jpg")
        
        # 如果本地封面文件已经存在，只需确保 cover_path 正确即可
        if os.path.exists(cover_full_path):
            expected_url = f"/static/cover/{expected_prefix}/{original_id}.jpg"
            if comic.cover_path != expected_url:
                comic.cover_path = expected_url
                self._comic_repo.save(comic)
            return
        
        # 本地没有封面文件：用第 1 张图片生成封面
        image_paths = file_parser.parse_comic_images(comic.id)
        if not image_paths:
            return
        
        handler = ImageHandler()
        new_cover_path = handler.generate_cover(comic.id, image_paths[0])
        if new_cover_path and comic.cover_path != new_cover_path:
            comic.cover_path = new_cover_path
            self._comic_repo.save(comic)
    
    def organize_database(self) -> ServiceResult:
        """整理数据库"""
        try:
            from infrastructure.persistence.json_storage import JsonStorage
            from core.platform import remove_platform_prefix, Platform
            from core.constants import JSON_FILE, JM_PICTURES_DIR, JM_COVER_DIR
            from utils.file_parser import file_parser
            from utils.image_handler import ImageHandler
            import os
            import requests
            from PIL import Image
            from io import BytesIO
            
            app_logger.info("开始整理数据库...")
            
            # 整理主页数据库
            storage = JsonStorage(JSON_FILE)
            db_data = storage.read()
            comics = db_data.get('comics', [])
            
            total_comics = len(comics)
            processed_comics = 0
            downloaded_covers = 0
            pk_generated_covers = 0
            re_downloaded_comics = 0
            
            app_logger.info(f"主页数据库中共有 {total_comics} 个漫画")
            
            # 遍历所有漫画
            for comic in comics:
                comic_id = comic['id']
                processed_comics += 1
                
                if processed_comics % 10 == 0:
                    app_logger.info(f"已处理 {processed_comics}/{total_comics} 个漫画")
                
                platform, original_id = remove_platform_prefix(comic_id)
                
                # 检查封面
                cover_path = comic.get('cover_path', '')
                if platform == Platform.JM and (not cover_path or cover_path.startswith('http')):
                    # JM：下载远程封面到本地
                        cover_url = f"https://cdn-msp3.18comic.vip/media/albums/{original_id}.jpg"
                        local_cover_path = os.path.join(JM_COVER_DIR, f"{original_id}.jpg")
                        
                        # 检查本地是否已有封面文件
                        if os.path.exists(local_cover_path):
                            # 本地已有封面，直接更新数据库
                            comic['cover_path'] = f"/static/cover/JM/{original_id}.jpg"
                            downloaded_covers += 1
                            app_logger.info(f"封面已存在，更新数据库: {comic_id} (累计: {downloaded_covers})")
                        else:
                            # 本地没有封面，下载并保存
                            try:
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                }
                                response = requests.get(cover_url, headers=headers, timeout=30)
                                response.raise_for_status()
                                
                                with Image.open(BytesIO(response.content)) as img:
                                    if img.mode in ('RGBA', 'P'):
                                        img = img.convert('RGB')
                                    img.save(local_cover_path, 'JPEG', quality=95)
                                
                                comic['cover_path'] = f"/static/cover/JM/{original_id}.jpg"
                                downloaded_covers += 1
                                app_logger.info(f"下载封面成功: {comic_id} (累计: {downloaded_covers})")
                            except Exception as e:
                                error_logger.error(f"下载封面失败 {comic_id}: {e}")
                elif platform == Platform.PK:
                    # PK：优先使用本地第一张图片生成封面
                    try:
                        image_paths = file_parser.parse_comic_images(comic_id)
                        if image_paths:
                            image_handler = ImageHandler()
                            new_cover_path = image_handler.generate_cover(comic_id, image_paths[0])
                            if new_cover_path:
                                comic['cover_path'] = new_cover_path
                                pk_generated_covers += 1
                                app_logger.info(f"为 PK 漫画生成封面成功: {comic_id} (累计: {pk_generated_covers})")
                    except Exception as e:
                        error_logger.error(f"为 PK 漫画生成封面失败 {comic_id}: {e}")
                    
                # 检查漫画页数
                total_page = comic.get('total_page', 0)
                if total_page > 0:
                    try:
                        image_paths = file_parser.parse_comic_images(comic_id)
                        if len(image_paths) < total_page:
                            # 重新下载漫画
                            import sys
                            jmcomic_path = os.path.join(os.path.dirname(__file__), '..', 'third_party', 'JMComic-Crawler-Python')
                            if jmcomic_path not in sys.path:
                                sys.path.insert(0, jmcomic_path)
                            
                            from jmcomic_api import download_album
                            
                            detail, success = download_album(
                                original_id,
                                download_dir=JM_PICTURES_DIR,
                                show_progress=False,
                                decode_images=True
                            )
                            
                            if success:
                                re_downloaded_comics += 1
                                app_logger.info(f"重新下载漫画成功: {comic_id} (累计: {re_downloaded_comics})")
                    except Exception as e:
                        error_logger.error(f"重新下载漫画失败 {comic_id}: {e}")
            
            # 保存主页数据库
            storage.write(db_data)
            
            # 整理推荐页数据库
            app_logger.info("开始整理推荐页数据库...")
            from core.constants import RECOMMENDATION_JSON_FILE
            
            rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            recommendations = rec_data.get('recommendations', [])
            
            total_recommendations = len(recommendations)
            processed_recommendations = 0
            rec_downloaded_covers = 0
            
            app_logger.info(f"推荐页数据库中共有 {total_recommendations} 个漫画")
            
            # 遍历所有推荐漫画
            for comic in recommendations:
                comic_id = comic['id']
                processed_recommendations += 1
                
                if processed_recommendations % 10 == 0:
                    app_logger.info(f"已处理 {processed_recommendations}/{total_recommendations} 个推荐漫画")
                
                platform, original_id = remove_platform_prefix(comic_id)
                
                # 检查封面（推荐页只检查封面，不检查漫画页数）
                cover_path = comic.get('cover_path', '')
                if not cover_path or cover_path.startswith('http'):
                    # 下载封面
                    if platform == Platform.JM:
                        cover_url = f"https://cdn-msp3.18comic.vip/media/albums/{original_id}.jpg"
                        local_cover_path = os.path.join(JM_COVER_DIR, f"{original_id}.jpg")
                        
                        # 检查本地是否已有封面文件
                        if os.path.exists(local_cover_path):
                            # 本地已有封面，直接更新数据库
                            comic['cover_path'] = f"/static/cover/JM/{original_id}.jpg"
                            rec_downloaded_covers += 1
                            app_logger.info(f"推荐页封面已存在，更新数据库: {comic_id} (累计: {rec_downloaded_covers})")
                        else:
                            # 本地没有封面，下载并保存
                            try:
                                headers = {
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                }
                                response = requests.get(cover_url, headers=headers, timeout=30)
                                response.raise_for_status()
                                
                                with Image.open(BytesIO(response.content)) as img:
                                    if img.mode in ('RGBA', 'P'):
                                        img = img.convert('RGB')
                                    img.save(local_cover_path, 'JPEG', quality=95)
                                
                                comic['cover_path'] = f"/static/cover/JM/{original_id}.jpg"
                                rec_downloaded_covers += 1
                                app_logger.info(f"下载推荐页封面成功: {comic_id} (累计: {rec_downloaded_covers})")
                            except Exception as e:
                                error_logger.error(f"下载推荐页封面失败 {comic_id}: {e}")
            
            # 保存推荐页数据库
            rec_storage.write(rec_data)
            
            app_logger.info(f"数据库整理完成！")
            app_logger.info(f"主页 - 处理漫画总数: {total_comics}")
            app_logger.info(f"主页 - 下载封面数量(JM): {downloaded_covers}")
            app_logger.info(f"主页 - 生成封面数量(PK): {pk_generated_covers}")
            app_logger.info(f"主页 - 重新下载漫画数量: {re_downloaded_comics}")
            app_logger.info(f"推荐页 - 处理漫画总数: {total_recommendations}")
            app_logger.info(f"推荐页 - 下载封面数量: {rec_downloaded_covers}")
            
            return ServiceResult.ok({
                "home": {
                    "total_comics": total_comics,
                    "downloaded_covers": downloaded_covers,
                    "re_downloaded_comics": re_downloaded_comics
                },
                "recommendation": {
                    "total_comics": total_recommendations,
                    "downloaded_covers": rec_downloaded_covers
                }
            }, "数据库整理完成")
        except Exception as e:
            error_logger.error(f"整理数据库失败: {e}")
            return ServiceResult.error("整理数据库失败")

import time
from utils import json_handler
from utils.logger import app_logger, error_logger


class ServiceResult:
    def __init__(self, success, data=None, message=""):
        self.success = success
        self.data = data
        self.message = message
    
    @staticmethod
    def ok(data=None, message="操作成功"):
        return ServiceResult(True, data, message)
    
    @staticmethod
    def error(message="操作失败"):
        return ServiceResult(False, None, message)
    
    def to_dict(self):
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message
        }


class ComicService:
    def __init__(self):
        self.json_handler = json_handler
    
    def get_comic_list(self):
        try:
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            tag_map = {t['id']: t['name'] for t in tags}
            
            comic_list = []
            for c in comics:
                comic_info = {
                    "id": c['id'],
                    "title": c['title'],
                    "author": c.get('author', ''),
                    "desc": c.get('desc', ''),
                    "cover_path": c['cover_path'],
                    "total_page": c['total_page'],
                    "current_page": c['current_page'],
                    "score": c.get('score'),
                    "tag_ids": c.get('tag_ids', []),
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in c.get('tag_ids', [])],
                    "last_read_time": c.get('last_read_time', '')
                }
                comic_list.append(comic_info)
            
            app_logger.info(f"获取漫画列表成功，共 {len(comic_list)} 个漫画")
            return ServiceResult.ok(comic_list)
        except Exception as e:
            error_logger.error(f"获取漫画列表失败: {e}")
            return ServiceResult.error("获取漫画列表失败")
    
    def get_comic_detail(self, comic_id):
        try:
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            tag_map = {t['id']: t['name'] for t in tags}
            
            comic = next((c for c in comics if c['id'] == comic_id), None)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            preview_pages = self._get_preview_pages(comic['total_page'])
            
            detail = {
                "id": comic['id'],
                "title": comic['title'],
                "title_jp": comic.get('title_jp', ''),
                "author": comic.get('author', ''),
                "desc": comic.get('desc', ''),
                "cover_path": comic['cover_path'],
                "total_page": comic['total_page'],
                "current_page": comic['current_page'],
                "score": comic.get('score'),
                "tag_ids": comic.get('tag_ids', []),
                "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in comic.get('tag_ids', [])],
                "preview_images": [f"/api/v1/comic/image?comic_id={comic_id}&page_num={p}" for p in preview_pages],
                "preview_pages": preview_pages,
                "last_read_time": comic.get('last_read_time', ''),
                "create_time": comic.get('create_time', '')
            }
            
            app_logger.info(f"获取漫画详情成功: {comic_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取漫画详情失败: {e}")
            return ServiceResult.error("获取漫画详情失败")
    
    def _get_preview_pages(self, total_page):
        pages = []
        if total_page >= 1:
            pages.append(1)
        if total_page >= 5:
            pages.append(5)
        if total_page >= 10:
            pages.append(10)
        if total_page > 10:
            pages.append(total_page)
        return pages
    
    def update_score(self, comic_id, score):
        try:
            valid, msg = self._validate_score(score)
            if not valid:
                return ServiceResult.error(msg)
            
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            
            comic = next((c for c in comics if c['id'] == comic_id), None)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic['score'] = score
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("保存评分失败")
            
            app_logger.info(f"更新漫画评分成功: {comic_id}, 评分: {score}")
            return ServiceResult.ok({"comic_id": comic_id, "score": score}, "评分保存成功")
        except Exception as e:
            error_logger.error(f"更新漫画评分失败: {e}")
            return ServiceResult.error("更新评分失败")
    
    def _validate_score(self, score):
        if not isinstance(score, (int, float)):
            return False, "评分必须是数字"
        
        if score < 1 or score > 12:
            return False, "评分范围1-12"
        
        if (score * 2) % 1 != 0:
            return False, "评分精度0.5"
        
        return True, "验证通过"
    
    def bind_tags(self, comic_id, tag_ids):
        try:
            if not isinstance(tag_ids, list):
                return ServiceResult.error("tag_ids必须是数组")
            
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            existing_tag_ids = {t['id'] for t in tags}
            
            for tag_id in tag_ids:
                if tag_id not in existing_tag_ids:
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            comic = next((c for c in comics if c['id'] == comic_id), None)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            comic['tag_ids'] = tag_ids
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("绑定标签失败")
            
            app_logger.info(f"绑定漫画标签成功: {comic_id}, 标签: {tag_ids}")
            return ServiceResult.ok({"comic_id": comic_id, "tag_ids": tag_ids}, "标签绑定成功")
        except Exception as e:
            error_logger.error(f"绑定漫画标签失败: {e}")
            return ServiceResult.error("绑定标签失败")
    
    def update_meta(self, comic_id, meta):
        try:
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            
            comic = next((c for c in comics if c['id'] == comic_id), None)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if 'title' in meta and meta['title']:
                comic['title'] = meta['title']
            if 'author' in meta:
                comic['author'] = meta['author']
            if 'desc' in meta:
                comic['desc'] = meta['desc']
            if 'cover_path' in meta and meta['cover_path']:
                comic['cover_path'] = meta['cover_path']
            
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("更新元数据失败")
            
            app_logger.info(f"更新漫画元数据成功: {comic_id}")
            return ServiceResult.ok(comic, "更新成功")
        except Exception as e:
            error_logger.error(f"更新漫画元数据失败: {e}")
            return ServiceResult.error("更新元数据失败")
    
    def update_progress(self, comic_id, current_page):
        try:
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            
            comic = next((c for c in comics if c['id'] == comic_id), None)
            if not comic:
                return ServiceResult.error("漫画不存在")
            
            if current_page < 1 or current_page > comic['total_page']:
                return ServiceResult.error("页码超出范围")
            
            comic['current_page'] = current_page
            comic['last_read_time'] = time.strftime("%Y-%m-%dT%H:%M:%S")
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("保存进度失败")
            
            app_logger.info(f"保存阅读进度成功: {comic_id}, 页码: {current_page}")
            return ServiceResult.ok({"comic_id": comic_id, "current_page": current_page}, "进度保存成功")
        except Exception as e:
            error_logger.error(f"保存阅读进度失败: {e}")
            return ServiceResult.error("保存进度失败")
    
    def batch_add_tags(self, comic_ids, tag_ids):
        try:
            if not isinstance(comic_ids, list) or not comic_ids:
                return ServiceResult.error("comic_ids必须是非空数组")
            if not isinstance(tag_ids, list) or not tag_ids:
                return ServiceResult.error("tag_ids必须是非空数组")
            
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            existing_tag_ids = {t['id'] for t in tags}
            
            for tag_id in tag_ids:
                if tag_id not in existing_tag_ids:
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            comic_map = {c['id']: c for c in comics}
            updated_count = 0
            
            for comic_id in comic_ids:
                if comic_id not in comic_map:
                    continue
                
                comic = comic_map[comic_id]
                current_tags = set(comic.get('tag_ids', []))
                current_tags.update(tag_ids)
                comic['tag_ids'] = list(current_tags)
                updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("批量添加标签失败")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为{updated_count}个漫画添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, comic_ids, tag_ids):
        try:
            if not isinstance(comic_ids, list) or not comic_ids:
                return ServiceResult.error("comic_ids必须是非空数组")
            if not isinstance(tag_ids, list) or not tag_ids:
                return ServiceResult.error("tag_ids必须是非空数组")
            
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            
            comic_map = {c['id']: c for c in comics}
            updated_count = 0
            
            for comic_id in comic_ids:
                if comic_id not in comic_map:
                    continue
                
                comic = comic_map[comic_id]
                current_tags = set(comic.get('tag_ids', []))
                current_tags.difference_update(tag_ids)
                comic['tag_ids'] = list(current_tags)
                updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效的漫画")
            
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("批量移除标签失败")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个漫画, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功从{updated_count}个漫画移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")

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


class TagService:
    def __init__(self):
        self.json_handler = json_handler
    
    def create_tag(self, tag_name):
        try:
            if not tag_name or not tag_name.strip():
                return ServiceResult.error("标签名称不能为空")
            
            tag_name = tag_name.strip()
            data = self.json_handler.read_json()
            tags = data.get('tags', [])
            
            existing = next((t for t in tags if t['name'] == tag_name), None)
            if existing:
                app_logger.warning(f"标签名称已存在: {tag_name}")
                return ServiceResult.error("标签名称已存在")
            
            tag_id = f"tag_{int(time.time() * 1000)}"
            new_tag = {
                "id": tag_id,
                "name": tag_name,
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            tags.append(new_tag)
            data['tags'] = tags
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("创建标签失败")
            
            app_logger.info(f"创建标签成功: {tag_id}, 名称: {tag_name}")
            return ServiceResult.ok(new_tag, "标签创建成功")
        except Exception as e:
            error_logger.error(f"创建标签失败: {e}")
            return ServiceResult.error("创建标签失败")
    
    def get_tag_list(self):
        try:
            data = self.json_handler.read_json()
            tags = data.get('tags', [])
            comics = data.get('comics', [])
            
            tag_count = {}
            for comic in comics:
                for tag_id in comic.get('tag_ids', []):
                    tag_count[tag_id] = tag_count.get(tag_id, 0) + 1
            
            tag_list = []
            for tag in tags:
                tag_info = {
                    "id": tag['id'],
                    "name": tag['name'],
                    "comic_count": tag_count.get(tag['id'], 0),
                    "create_time": tag.get('create_time', '')
                }
                tag_list.append(tag_info)
            
            app_logger.info(f"获取标签列表成功，共 {len(tag_list)} 个标签")
            return ServiceResult.ok(tag_list)
        except Exception as e:
            error_logger.error(f"获取标签列表失败: {e}")
            return ServiceResult.error("获取标签列表失败")
    
    def update_tag(self, tag_id, tag_name):
        try:
            if not tag_name or not tag_name.strip():
                return ServiceResult.error("标签名称不能为空")
            
            tag_name = tag_name.strip()
            data = self.json_handler.read_json()
            tags = data.get('tags', [])
            
            tag = next((t for t in tags if t['id'] == tag_id), None)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            existing = next((t for t in tags if t['name'] == tag_name and t['id'] != tag_id), None)
            if existing:
                return ServiceResult.error("标签名称已存在")
            
            tag['name'] = tag_name
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("更新标签失败")
            
            app_logger.info(f"更新标签成功: {tag_id}, 新名称: {tag_name}")
            return ServiceResult.ok(tag, "标签更新成功")
        except Exception as e:
            error_logger.error(f"更新标签失败: {e}")
            return ServiceResult.error("更新标签失败")
    
    def delete_tag(self, tag_id):
        try:
            data = self.json_handler.read_json()
            tags = data.get('tags', [])
            comics = data.get('comics', [])
            
            tag = next((t for t in tags if t['id'] == tag_id), None)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            tags = [t for t in tags if t['id'] != tag_id]
            data['tags'] = tags
            
            for comic in comics:
                if tag_id in comic.get('tag_ids', []):
                    comic['tag_ids'] = [tid for tid in comic.get('tag_ids', []) if tid != tag_id]
            
            data['comics'] = comics
            data['last_updated'] = time.strftime("%Y-%m-%d")
            
            if not self.json_handler.write_json(data):
                return ServiceResult.error("删除标签失败")
            
            app_logger.info(f"删除标签成功: {tag_id}")
            return ServiceResult.ok({"tag_id": tag_id}, "标签删除成功")
        except Exception as e:
            error_logger.error(f"删除标签失败: {e}")
            return ServiceResult.error("删除标签失败")
    
    def get_comics_by_tag(self, tag_id):
        try:
            data = self.json_handler.read_json()
            tags = data.get('tags', [])
            comics = data.get('comics', [])
            tag_map = {t['id']: t['name'] for t in tags}
            
            tag = next((t for t in tags if t['id'] == tag_id), None)
            if not tag:
                return ServiceResult.error("标签不存在")
            
            filtered_comics = []
            for comic in comics:
                if tag_id in comic.get('tag_ids', []):
                    comic_info = {
                        "id": comic['id'],
                        "title": comic['title'],
                        "author": comic.get('author', ''),
                        "cover_path": comic['cover_path'],
                        "total_page": comic['total_page'],
                        "current_page": comic['current_page'],
                        "score": comic.get('score'),
                        "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in comic.get('tag_ids', [])]
                    }
                    filtered_comics.append(comic_info)
            
            app_logger.info(f"获取标签下漫画成功: {tag_id}, 共 {len(filtered_comics)} 个漫画")
            return ServiceResult.ok(filtered_comics)
        except Exception as e:
            error_logger.error(f"获取标签下漫画失败: {e}")
            return ServiceResult.error("获取标签下漫画失败")

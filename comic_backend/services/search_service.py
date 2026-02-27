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


class SearchService:
    def __init__(self):
        self.json_handler = json_handler
    
    def search_by_keyword(self, keyword):
        try:
            if not keyword or not keyword.strip():
                return ServiceResult.error("搜索关键词不能为空")
            
            keyword = keyword.strip().lower()
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            tag_map = {t['id']: t['name'] for t in tags}
            
            app_logger.info(f"开始搜索: 关键词='{keyword}', 漫画数={len(comics)}, 标签数={len(tags)}")
            
            matched_tag_ids = set()
            for tag in tags:
                if keyword in tag['name'].lower():
                    matched_tag_ids.add(tag['id'])
                    app_logger.debug(f"标签匹配: {tag['name']} (ID: {tag['id']})")
            
            app_logger.info(f"匹配到的标签ID: {matched_tag_ids}")
            
            results = []
            matched_comic_ids = set()
            
            for comic in comics:
                if comic['id'] == keyword:
                    if comic['id'] not in matched_comic_ids:
                        results.insert(0, self._format_comic(comic, tag_map))
                        matched_comic_ids.add(comic['id'])
                        app_logger.debug(f"ID匹配: {comic['id']}")
                    continue
            
            for comic in comics:
                if comic['id'] in matched_comic_ids:
                    continue
                if keyword in comic['title'].lower():
                    results.append(self._format_comic(comic, tag_map))
                    matched_comic_ids.add(comic['id'])
                    app_logger.debug(f"标题匹配: {comic['title']}")
            
            for comic in comics:
                if comic['id'] in matched_comic_ids:
                    continue
                author = comic.get('author', '')
                if author and keyword in author.lower():
                    results.append(self._format_comic(comic, tag_map))
                    matched_comic_ids.add(comic['id'])
                    app_logger.debug(f"作者匹配: {author}")
            
            for comic in comics:
                if comic['id'] in matched_comic_ids:
                    continue
                comic_tag_ids = set(comic.get('tag_ids', []))
                if matched_tag_ids and (comic_tag_ids & matched_tag_ids):
                    results.append(self._format_comic(comic, tag_map))
                    matched_comic_ids.add(comic['id'])
                    app_logger.debug(f"标签匹配: 漫画 {comic['id']}, 标签交集: {comic_tag_ids & matched_tag_ids}")
            
            app_logger.info(f"搜索完成: 关键词 '{keyword}', 结果数量: {len(results)}, 匹配漫画ID: {matched_comic_ids}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"搜索失败: {e}")
            return ServiceResult.error("搜索失败")
    
    def filter_by_tags(self, include_tag_ids=None, exclude_tag_ids=None):
        try:
            data = self.json_handler.read_json()
            comics = data.get('comics', [])
            tags = data.get('tags', [])
            tag_map = {t['id']: t['name'] for t in tags}
            
            include_tag_ids = include_tag_ids or []
            exclude_tag_ids = exclude_tag_ids or []
            
            results = []
            for comic in comics:
                comic_tag_ids = set(comic.get('tag_ids', []))
                
                if include_tag_ids:
                    if not all(tid in comic_tag_ids for tid in include_tag_ids):
                        continue
                
                if exclude_tag_ids:
                    if any(tid in comic_tag_ids for tid in exclude_tag_ids):
                        continue
                
                results.append(self._format_comic(comic, tag_map))
            
            app_logger.info(f"筛选成功: 包含标签 {include_tag_ids}, 排除标签 {exclude_tag_ids}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def _format_comic(self, comic, tag_map):
        return {
            "id": comic['id'],
            "title": comic['title'],
            "author": comic.get('author', ''),
            "desc": comic.get('desc', ''),
            "cover_path": comic['cover_path'],
            "total_page": comic['total_page'],
            "current_page": comic['current_page'],
            "score": comic.get('score'),
            "tag_ids": comic.get('tag_ids', []),
            "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in comic.get('tag_ids', [])],
            "last_read_time": comic.get('last_read_time', '')
        }

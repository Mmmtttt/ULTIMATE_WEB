"""
JAVDB API 简化包装器
"""

import json
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote
from pathlib import Path

from curl_cffi import requests
from bs4 import BeautifulSoup


class SimpleJavdbClient:
    """简化的 JAVDB 客户端"""
    
    DOMAINS = [
        'https://javdb.com',
        'https://javdb570.com',
        'https://javdb372.com',
    ]
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    def __init__(self, domain_index: int = 0):
        self.domain_index = domain_index
        self.base_url = self.DOMAINS[domain_index]
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._load_cookies()
    
    def _load_cookies(self):
        """加载cookies"""
        cookie_file = Path(__file__).parent / 'javdb-api-scraper' / 'cookies.json'
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    self.session.cookies.update(cookies)
            except Exception:
                pass
    
    def _switch_domain(self):
        """切换域名"""
        self.domain_index = (self.domain_index + 1) % len(self.DOMAINS)
        self.base_url = self.DOMAINS[self.domain_index]
    
    def _request(self, path: str, retry: int = 3) -> Optional[requests.Response]:
        """发送请求"""
        url = urljoin(self.base_url, path)
        
        for i in range(retry):
            try:
                response = self.session.get(url, impersonate='chrome', timeout=30, allow_redirects=True)
                
                if response.status_code == 200:
                    return response
                
                if response.status_code in [403, 503]:
                    self._switch_domain()
                    url = urljoin(self.base_url, path)
                    continue
                
            except Exception:
                time.sleep(2)
        
        return None
    
    def search_videos(self, keyword: str, max_pages: int = 1) -> List[Dict]:
        """搜索视频"""
        videos = []
        
        for page in range(1, max_pages + 1):
            encoded_keyword = quote(keyword)
            path = f"/search?q={encoded_keyword}&page={page}"
            
            response = self._request(path)
            if not response:
                continue
            
            soup = BeautifulSoup(response.text, 'lxml')
            items = soup.select('div.item a')
            
            for item in items:
                try:
                    work = self._parse_work_item(item)
                    if work:
                        videos.append(work)
                except Exception:
                    continue
        
        return videos
    
    def _parse_work_item(self, item) -> Optional[Dict]:
        """解析搜索结果项"""
        video_id = item.get('href', '').split('/')[-1]
        if not video_id:
            return None
        
        img_tag = item.select_one('img')
        cover = img_tag.get('src', '') if img_tag else ''
        
        title_tag = item.select_one('.video-title')
        title = title_tag.get_text(strip=True) if title_tag else ''
        
        code_tag = item.select_one('.uid')
        code = code_tag.get_text(strip=True) if code_tag else ''
        
        return {
            'id': video_id,
            'title': title,
            'code': code,
            'cover': cover
        }
    
    def get_video_detail(self, video_id: str) -> Optional[Dict]:
        """获取视频详情"""
        path = f"/v/{video_id}"
        
        response = self._request(path)
        if not response:
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = ''
        title_tag = soup.select_one('h2.title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        code = ''
        code_tag = soup.select_one('.video-meta-panel .value')
        if code_tag:
            code = code_tag.get_text(strip=True)
        
        date = ''
        date_tag = soup.select_one('.video-meta-panel .panel-block:nth-child(2) .value')
        if date_tag:
            date = date_tag.get_text(strip=True)
        
        series = ''
        series_tag = soup.select_one('.video-meta-panel .panel-block:nth-child(3) .value')
        if series_tag:
            series = series_tag.get_text(strip=True)
        
        actors = []
        actor_tags = soup.select('.video-meta-panel .actor a')
        for actor_tag in actor_tags:
            actors.append(actor_tag.get_text(strip=True))
        
        tags = []
        tag_tags = soup.select('.video-meta-panel .tag a')
        for tag_tag in tag_tags:
            tags.append(tag_tag.get_text(strip=True))
        
        cover = ''
        cover_tag = soup.select_one('.video-cover img')
        if cover_tag:
            cover = cover_tag.get('src', '')
        
        thumbnail_images = []
        preview_tags = soup.select('.preview-images img')
        for preview_tag in preview_tags:
            src = preview_tag.get('src', '')
            if src:
                thumbnail_images.append(src)
        
        magnets = []
        magnet_tags = soup.select('.magnet-links a')
        for magnet_tag in magnet_tags:
            magnet = magnet_tag.get('href', '')
            size_text = magnet_tag.select_one('.size')
            size = size_text.get_text(strip=True) if size_text else ''
            if magnet:
                magnets.append({
                    'magnet': magnet,
                    'size_text': size
                })
        
        return {
            'id': video_id,
            'title': title,
            'code': code,
            'date': date,
            'series': series,
            'actors': actors,
            'tags': tags,
            'cover': cover,
            'thumbnail_images': thumbnail_images,
            'magnets': magnets
        }
    
    def search_actor(self, actor_name: str) -> List[Dict]:
        """搜索演员"""
        encoded_name = quote(actor_name)
        path = f"/search?q={encoded_name}&f=actor"
        
        response = self._request(path)
        if not response:
            return []
        
        soup = BeautifulSoup(response.text, 'lxml')
        actors = []
        items = soup.select('.actor-item')
        
        for item in items:
            try:
                a_tag = item.select_one('a')
                if not a_tag:
                    continue
                
                actor_id = a_tag.get('href', '').split('/')[-1]
                img_tag = a_tag.select_one('img')
                avatar = img_tag.get('src', '') if img_tag else ''
                
                name_tag = a_tag.select_one('.name')
                name = name_tag.get_text(strip=True) if name_tag else ''
                
                actors.append({
                    'id': actor_id,
                    'name': name,
                    'avatar': avatar
                })
            except Exception:
                continue
        
        return actors
    
    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict:
        """获取演员作品"""
        works = []
        
        for p in range(page, page + max_pages):
            path = f"/actor/{actor_id}?page={p}"
            
            response = self._request(path)
            if not response:
                continue
            
            soup = BeautifulSoup(response.text, 'lxml')
            items = soup.select('div.item a')
            
            for item in items:
                try:
                    work = self._parse_work_item(item)
                    if work:
                        works.append(work)
                except Exception:
                    continue
        
        return {
            'works': works,
            'page': page,
            'total': len(works)
        }


__all__ = ['SimpleJavdbClient']

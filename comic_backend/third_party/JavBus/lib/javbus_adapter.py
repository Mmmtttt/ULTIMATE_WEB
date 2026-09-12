"""
JavBus 平台适配器
负责将 JavBus 网站数据转换为系统标准格式
"""

import os
import re
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
from datetime import datetime

from curl_cffi import requests
from bs4 import BeautifulSoup

from .base_adapter import BaseAdapter
from .platform import Platform


class JavbusAdapter(BaseAdapter):
    """JavBus 平台适配器"""
    
    BASE_URL = "https://www.javbus.com"
    
    # 有码/无码类型
    TYPE_NORMAL = "normal"  # 有码
    TYPE_UNCENSORED = "uncensored"  # 无码
    
    def __init__(self, existing_tags: List[Dict] = None, proxy: str = None):
        super().__init__(existing_tags)
        self.platform = Platform.JAVBUS
        self.session = requests.Session()
        self.proxy = proxy
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
    
    def get_platform(self) -> Platform:
        """返回平台类型"""
        return self.platform
    
    def _get(self, url: str, **kwargs) -> requests.Response:
        """发送 GET 请求"""
        proxies = {'http': self.proxy, 'https': self.proxy} if self.proxy else None
        # 使用 impersonate 绕过 Cloudflare 和年龄验证
        return self.session.get(url, proxies=proxies, timeout=30, impersonate="chrome120", **kwargs)
    
    def _parse_movie_item(self, item: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """解析电影列表项"""
        try:
            # 获取封面图片
            img_tag = item.select_one('.photo-frame img')
            img = img_tag.get('src', '') if img_tag else ''
            title = img_tag.get('title', '') if img_tag else ''
            
            # 处理相对路径的缩略图 URL
            if img.startswith('//'):
                img = 'https:' + img
            elif img.startswith('/'):
                img = self.BASE_URL + img
            
            # 获取番号和日期
            info_tags = item.select('.photo-info date')
            code = info_tags[0].text.strip() if len(info_tags) > 0 else ''
            date = info_tags[1].text.strip() if len(info_tags) > 1 else None
            
            # 获取标签（高清、字幕等）
            tags = [tag.text.strip() for tag in item.select('.item-tag button')]
            
            # 获取详情页链接
            link_tag = item.select_one('a')
            href = link_tag.get('href', '') if link_tag else ''
            video_id = href.split('/')[-1] if href else ''
            
            if not code:
                return None
            
            return {
                "video_id": video_id,
                "code": code,
                "title": title,
                "date": date,
                "tags": tags,
                "actors": [],  # 列表页不显示演员
                "cover_url": img,
                "thumbnail_url": img,  # 搜索列表的缩略图
                "rating": "",  # JavBus 列表页不显示评分
            }
        except Exception as e:
            print(f"解析电影项失败: {e}")
            return None
    
    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1, movie_type: str = None) -> Dict[str, Any]:
        """
        搜索视频
        
        Args:
            keyword: 搜索关键词（番号、标题等）
            page: 起始页码
            max_pages: 最大搜索页数
            movie_type: 影片类型 'normal'(有码) 或 'uncensored'(无码)，None 表示全部
            
        Returns:
            包含分页信息和视频列表的字典
        """
        results = []
        current_page = page
        has_next = True
        
        # 构建基础 URL
        if movie_type == self.TYPE_UNCENSORED:
            base_url = f"{self.BASE_URL}/uncensored/search"
        else:
            base_url = f"{self.BASE_URL}/search"
        
        while current_page < page + max_pages and has_next:
            try:
                # 构建搜索 URL
                if current_page == 1:
                    url = f"{base_url}/{keyword}?type=1"
                else:
                    url = f"{base_url}/{keyword}/{current_page}?type=1"
                
                response = self._get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 解析电影列表
                items = soup.select('#waterfall .item')
                
                if not items:
                    has_next = False
                    break
                
                for item in items:
                    movie = self._parse_movie_item(item)
                    if movie:
                        results.append(movie)
                
                # 检查是否有下一页
                next_btn = soup.select_one('.pagination li #next')
                has_next = bool(next_btn)
                
                if has_next and current_page < page + max_pages - 1:
                    current_page += 1
                    time.sleep(0.5)
                else:
                    break
                
            except Exception as e:
                print(f"搜索失败 (page {current_page}): {e}")
                has_next = False
                break
        
        return {
            "page": page,
            "has_next": has_next,
            "total_pages": None,
            "videos": results
        }
    
    def get_video_detail(self, video_id: str, movie_type: str = None) -> Optional[Dict[str, Any]]:
        """
        获取视频详情
        
        Args:
            video_id: 视频 ID（如 ABP-123）
            movie_type: 影片类型 'normal' 或 'uncensored'
            
        Returns:
            视频详情字典
        """
        try:
            # 构建详情页 URL
            if movie_type == self.TYPE_UNCENSORED:
                url = f"{self.BASE_URL}/uncensored/{video_id}"
            else:
                url = f"{self.BASE_URL}/{video_id}"
            
            response = self._get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取标题
            title_tag = soup.select_one('.container h3')
            title = title_tag.text.strip() if title_tag else ''
            
            # 获取封面图片（高清）
            img_tag = soup.select_one('.container .movie .bigImage img')
            img = img_tag.get('src', '') if img_tag else ''
            
            # 尝试获取更高清的封面图
            # JavBus 的高清封面通常在 bigImage 的 href 中
            big_image_link = soup.select_one('.container .movie .bigImage')
            if big_image_link:
                href = big_image_link.get('href', '')
                if href:
                    # 处理相对路径
                    if href.startswith('//'):
                        img = 'https:' + href
                    elif href.startswith('/'):
                        img = self.BASE_URL + href
                    elif href.startswith('http'):
                        img = href
            
            # 确保封面 URL 是完整的
            if img and img.startswith('//'):
                img = 'https:' + img
            elif img and img.startswith('/'):
                img = self.BASE_URL + img
            
            # 解析基本信息
            info_nodes = soup.select('.container .movie .info p')
            
            info_dict = {}
            for node in info_nodes:
                header = node.select_one('.header')
                if header:
                    key = header.text.strip()
                    # 获取 header 后面的文本
                    value = node.text.replace(key, '').strip()
                    info_dict[key] = value
            
            # 提取日期
            date = info_dict.get('發行日期:', '').replace('發行日期:', '').strip() or None
            
            # 提取时长
            length_str = info_dict.get('長度:', '').replace('分鐘', '').strip()
            try:
                video_length = int(length_str) if length_str else None
            except:
                video_length = None
            
            # 提取导演
            director_node = soup.select_one('.container .movie .info p:contains("導演:") a')
            director = director_node.text.strip() if director_node else None
            
            # 提取制作商
            producer_node = soup.select_one('.container .movie .info p:contains("製作商:") a')
            producer = producer_node.text.strip() if producer_node else None
            
            # 提取发行商
            publisher_node = soup.select_one('.container .movie .info p:contains("發行商:") a')
            publisher = publisher_node.text.strip() if publisher_node else None
            
            # 提取系列
            series_node = soup.select_one('.container .movie .info p:contains("系列:") a')
            series = series_node.text.strip() if series_node else None
            
            # 提取类型（标签）- 更完整的标签抓取
            genres = []
            genre_links = soup.select('.container .movie .info .genre label a')
            for genre in genre_links:
                genre_text = genre.text.strip()
                if genre_text and genre_text not in genres:
                    genres.append(genre_text)
            
            # 提取演员 - 包含演员ID和头像
            actors = []
            actor_list = []
            for star_box in soup.select('.container .movie .info .genre[onmouseover]'):
                star_link = star_box.select_one('a')
                if star_link:
                    actor_name = star_link.text.strip()
                    actor_url = star_link.get('href', '')
                    # 提取演员ID
                    actor_id = None
                    if actor_url:
                        actor_id = actor_url.rstrip('/').split('/')[-1]
                    
                    actors.append(actor_name)
                    actor_list.append({
                        'name': actor_name,
                        'id': actor_id,
                        'url': actor_url if actor_url.startswith('http') else f"{self.BASE_URL}{actor_url}"
                    })
            
            # 提取样品图片（高清）
            samples = []
            sample_images = []
            for sample in soup.select('#sample-waterfall .sample-box'):
                img_tag = sample.select_one('img')
                if img_tag:
                    thumbnail = img_tag.get('src', '')
                    # 处理缩略图 URL
                    if thumbnail.startswith('//'):
                        thumbnail = 'https:' + thumbnail
                    elif thumbnail.startswith('/'):
                        thumbnail = self.BASE_URL + thumbnail
                    
                    # 尝试获取高清图链接
                    # 样品图的高清版本通常在父链接的 href 中
                    sample_link = sample.get('href', '')
                    full_image = None
                    if sample_link:
                        if sample_link.startswith('//'):
                            full_image = 'https:' + sample_link
                        elif sample_link.startswith('/'):
                            full_image = self.BASE_URL + sample_link
                        elif sample_link.startswith('http'):
                            full_image = sample_link
                    
                    sample_data = {
                        'thumbnail': thumbnail,
                        'alt': img_tag.get('title', ''),
                    }
                    if full_image:
                        sample_data['full_image'] = full_image
                    
                    samples.append(sample_data)
                    sample_images.append(thumbnail)
                    if full_image:
                        sample_images.append(full_image)
            
            # 提取 gid 和 uc（用于获取磁力链接）
            gid_match = re.search(r'var gid = (\d+);', response.text)
            uc_match = re.search(r'var uc = (\d+);', response.text)
            gid = gid_match.group(1) if gid_match else None
            uc = uc_match.group(1) if uc_match else None
            
            # 获取演员头像（从演员页面获取）
            actor_avatars = {}
            for actor in actor_list:
                if actor.get('id'):
                    avatar = self._get_actor_avatar(actor['id'], movie_type)
                    if avatar:
                        actor_avatars[actor['name']] = avatar
            
            return {
                "video_id": video_id,
                "code": video_id,  # JavBus 使用番号作为 ID
                "title": title,
                "date": date,
                "video_length": video_length,
                "director": director,
                "producer": producer,
                "publisher": publisher,
                "series": series,
                "tags": genres,
                "tags_count": len(genres),
                "actors": actors,
                "actors_detail": actor_list,
                "actor_avatars": actor_avatars,
                "cover_url": img,
                "cover_hd": img if img.startswith('http') else None,
                "thumbnail_images": sample_images,
                "samples": samples,
                "sample_count": len(samples),
                "preview_video": "",  # JavBus 没有预览视频
                "gid": gid,
                "uc": uc,
            }
            
        except Exception as e:
            print(f"获取详情失败: {e}")
            return None
    
    def get_movie_magnets(self, video_id: str, gid: str = None, uc: str = None, 
                          sort_by: str = 'size', sort_order: str = 'desc') -> List[Dict[str, Any]]:
        """
        获取影片磁力链接
        
        Args:
            video_id: 视频 ID
            gid: 页面中的 gid 参数
            uc: 页面中的 uc 参数
            sort_by: 排序方式 'size'(大小) 或 'date'(日期)
            sort_order: 排序顺序 'asc'(升序) 或 'desc'(降序)
            
        Returns:
            磁力链接列表
        """
        if not gid or not uc:
            # 先获取详情获取 gid 和 uc
            detail = self.get_video_detail(video_id)
            if not detail:
                return []
            gid = detail.get('gid')
            uc = detail.get('uc')
        
        if not gid or not uc:
            return []
        
        try:
            # 请求磁力链接 API
            url = f"{self.BASE_URL}/ajax/uncledatoolsbyajax.php"
            params = {
                'lang': 'zh',
                'gid': gid,
                'uc': uc,
            }
            headers = {
                'Referer': f"{self.BASE_URL}/{video_id}",
            }
            
            response = self._get(url, params=params, headers=headers)
            response.raise_for_status()
            
            # 解析 HTML 响应
            soup = BeautifulSoup(response.text, 'html.parser')
            magnets = []
            
            for row in soup.select('tr'):
                link_tag = row.select_one('td a')
                if not link_tag:
                    continue
                
                link = link_tag.get('href', '')
                if not link.startswith('magnet:'):
                    continue
                
                # 提取 BTIH
                btih_match = re.search(r'urn:btih:(\w+)', link)
                btih = btih_match.group(1) if btih_match else ''
                
                # 检查是否有高清标签
                is_hd = bool(link_tag.select_one('a:contains("高清")'))
                
                # 检查是否有字幕标签
                has_subtitle = bool(link_tag.select_one('a:contains("字幕")'))
                
                # 移除标签后获取标题
                title = link_tag.text.strip()
                
                # 获取大小
                size_tag = row.select_one('td:nth-child(2) a')
                size = size_tag.text.strip() if size_tag else None
                
                # 获取分享日期
                date_tag = row.select_one('td:nth-child(3) a')
                share_date = date_tag.text.strip() if date_tag else None
                
                magnets.append({
                    'id': btih,
                    'link': link,
                    'title': title,
                    'size': size,
                    'share_date': share_date,
                    'is_hd': is_hd,
                    'has_subtitle': has_subtitle,
                })
            
            # 排序
            if sort_by == 'size':
                magnets.sort(key=lambda x: self._parse_size(x.get('size', '')), 
                           reverse=(sort_order == 'desc'))
            elif sort_by == 'date':
                magnets.sort(key=lambda x: x.get('share_date', ''), 
                           reverse=(sort_order == 'desc'))
            
            return magnets
            
        except Exception as e:
            print(f"获取磁力链接失败: {e}")
            return []
    
    def _parse_size(self, size_str: str) -> int:
        """解析文件大小为字节数"""
        if not size_str:
            return 0
        
        units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
        match = re.match(r'([\d.]+)\s*(\w+)', size_str.upper())
        
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            return int(value * units.get(unit, 1))
        
        return 0
    
    def _get_actor_avatar(self, star_id: str, movie_type: str = None) -> Optional[str]:
        """
        获取演员头像
        
        Args:
            star_id: 演员ID
            movie_type: 影片类型
            
        Returns:
            头像URL
        """
        try:
            if movie_type == self.TYPE_UNCENSORED:
                url = f"{self.BASE_URL}/uncensored/star/{star_id}"
            else:
                url = f"{self.BASE_URL}/star/{star_id}"
            
            response = self._get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 获取头像
            avatar_box = soup.select_one('#waterfall .item .avatar-box')
            if avatar_box:
                img_tag = avatar_box.select_one('.photo-frame img')
                if img_tag:
                    avatar_url = img_tag.get('src', '')
                    return avatar_url if avatar_url.startswith('http') else None
            
            return None
            
        except Exception as e:
            return None
    
    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        """
        搜索演员（JavBus 没有专门的演员搜索接口，通过搜索页面解析）
        
        Args:
            actor_name: 演员名字
            
        Returns:
            演员列表
        """
        # JavBus 的演员搜索需要通过搜索结果页面解析
        # 暂时返回空列表，可以通过 get_star_info 获取演员详情
        return []
    
    def get_star_info(self, star_id: str, movie_type: str = None) -> Optional[Dict[str, Any]]:
        """
        获取演员信息
        
        Args:
            star_id: 演员 ID
            movie_type: 影片类型 'normal' 或 'uncensored'
            
        Returns:
            演员信息字典
        """
        try:
            if movie_type == self.TYPE_UNCENSORED:
                url = f"{self.BASE_URL}/uncensored/star/{star_id}"
            else:
                url = f"{self.BASE_URL}/star/{star_id}"
            
            response = self._get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 解析演员信息
            avatar_box = soup.select_one('#waterfall .item .avatar-box')
            if not avatar_box:
                return None
            
            # 获取头像
            img_tag = avatar_box.select_one('.photo-frame img')
            avatar = img_tag.get('src', '') if img_tag else ''
            
            # 获取名字
            name_tag = avatar_box.select_one('.photo-info .pb10')
            name = name_tag.text.strip() if name_tag else ''
            
            # 解析其他信息
            info_dict = {}
            for p in avatar_box.select('.photo-info p'):
                text = p.text.strip()
                if '生日:' in text:
                    info_dict['birthday'] = text.replace('生日:', '').strip()
                elif '年齡:' in text:
                    age_str = text.replace('年齡:', '').strip()
                    try:
                        info_dict['age'] = int(age_str)
                    except:
                        info_dict['age'] = None
                elif '身高:' in text:
                    info_dict['height'] = text.replace('身高:', '').strip()
                elif '胸圍:' in text:
                    info_dict['bust'] = text.replace('胸圍:', '').strip()
                elif '腰圍:' in text:
                    info_dict['waistline'] = text.replace('腰圍:', '').strip()
                elif '臀圍:' in text:
                    info_dict['hipline'] = text.replace('臀圍:', '').strip()
                elif '出生地:' in text:
                    info_dict['birthplace'] = text.replace('出生地:', '').strip()
                elif '愛好:' in text:
                    info_dict['hobby'] = text.replace('愛好:', '').strip()
            
            return {
                'actor_id': star_id,
                'actor_name': name,
                'avatar': avatar,
                **info_dict
            }
            
        except Exception as e:
            print(f"获取演员信息失败: {e}")
            return None
    
    def get_movies_by_page(self, page: int = 1, movie_type: str = None, 
                          magnet_type: str = 'exist') -> Dict[str, Any]:
        """
        按页获取影片列表
        
        Args:
            page: 页码
            movie_type: 影片类型 'normal' 或 'uncensored'
            magnet_type: 磁力类型 'all' 或 'exist'(有磁力)
            
        Returns:
            包含影片列表和分页信息的字典
        """
        try:
            # 构建 URL
            if movie_type == self.TYPE_UNCENSORED:
                base_url = f"{self.BASE_URL}/uncensored"
            else:
                base_url = self.BASE_URL
            
            if page == 1:
                url = base_url
            else:
                url = f"{base_url}/page/{page}"
            
            # 设置 Cookie
            cookies = {'existmag': 'mag' if magnet_type == 'exist' else 'all'}
            
            response = self._get(url, cookies=cookies)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 解析影片列表
            movies = []
            for item in soup.select('#waterfall #waterfall .item'):
                movie = self._parse_movie_item(item)
                if movie:
                    movies.append(movie)
            
            # 解析分页信息
            current_page = 1
            page_active = soup.select_one('.pagination .active a')
            if page_active:
                try:
                    current_page = int(page_active.text.strip())
                except:
                    pass
            
            # 获取所有页码
            pages = []
            for page_link in soup.select('.pagination li a'):
                text = page_link.text.strip()
                if text.isdigit():
                    pages.append(int(text))
            
            # 检查是否有下一页
            has_next = soup.select_one('.pagination li #next') is not None
            next_page = current_page + 1 if has_next else None
            
            return {
                'movies': movies,
                'pagination': {
                    'current_page': current_page,
                    'has_next_page': has_next,
                    'next_page': next_page,
                    'pages': sorted(set(pages)) if pages else [1],
                }
            }
            
        except Exception as e:
            print(f"获取影片列表失败: {e}")
            return {
                'movies': [],
                'pagination': {
                    'current_page': page,
                    'has_next_page': False,
                    'next_page': None,
                    'pages': [page],
                }
            }

    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取演员作品（实现基类抽象方法）
        
        Args:
            actor_id: 演员ID
            page: 起始页码
            max_pages: 最大页数
            
        Returns:
            作品列表和分页信息
        """
        results = []
        current_page = page
        has_next = True
        
        while current_page <= page + max_pages - 1 and has_next:
            try:
                url = f"{self.BASE_URL}/star/{actor_id}"
                if current_page > 1:
                    url = f"{url}/{current_page}"
                
                response = self._get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 解析影片列表
                for item in soup.select('#waterfall #waterfall .item'):
                    movie = self._parse_movie_item(item)
                    if movie:
                        results.append(movie)
                
                # 检查是否有下一页
                has_next = soup.select_one('.pagination li #next') is not None
                current_page += 1
                
                if has_next:
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"获取演员作品失败: {e}")
                break
        
        return {
            'page': page,
            'has_next': has_next,
            'actor_id': actor_id,
            'works': results
        }

    def get_tag_works(self, tag_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取标签作品（实现基类抽象方法）
        
        Args:
            tag_id: 标签ID
            page: 起始页码
            max_pages: 最大页数
            
        Returns:
            作品列表和分页信息
        """
        # JavBus 没有标签ID系统，返回空结果
        return {
            'page': page,
            'has_next': False,
            'tag_id': tag_id,
            'works': []
        }

    def download_video_images(self, video_id: str, download_dir: str) -> tuple:
        """
        下载视频缩略图（实现基类抽象方法）
        
        Args:
            video_id: 视频ID
            download_dir: 下载目录
            
        Returns:
            (成功下载数, 总数)
        """
        try:
            # 获取视频详情
            detail = self.get_video_detail(video_id)
            if not detail or not detail.get('cover_url'):
                return (0, 0)
            
            # 创建下载目录
            os.makedirs(download_dir, exist_ok=True)
            
            # 下载封面图
            cover_url = detail['cover_url']
            ext = cover_url.split('.')[-1].split('?')[0]
            if not ext:
                ext = 'jpg'
            
            filename = f"{video_id}_cover.{ext}"
            filepath = os.path.join(download_dir, filename)
            
            response = self._get(cover_url)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return (1, 1)
            
            return (0, 1)
            
        except Exception as e:
            print(f"下载图片失败: {e}")
            return (0, 0)

    def convert_to_standard_format(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        转换为标准格式（实现基类抽象方法）
        
        Args:
            videos: 视频列表
            
        Returns:
            标准格式的视频和标签数据
        """
        standard_videos = []
        all_tags = []
        
        for video in videos:
            # 转换视频格式
            std_video = {
                'id': video.get('video_id', ''),
                'code': video.get('code', ''),
                'title': video.get('title', ''),
                'cover_url': video.get('cover_url', ''),
                'url': video.get('url', ''),
                'date': video.get('date', ''),
                'rating': video.get('rating', ''),
                'tags': video.get('tags', []),
                'actors': video.get('actors', []),
                'platform': self.platform.value
            }
            standard_videos.append(std_video)
            
            # 收集标签
            for tag in video.get('tags', []):
                if isinstance(tag, dict) and 'id' in tag and 'name' in tag:
                    tag_key = f"{tag['id']}:{tag['name']}"
                    if tag_key not in [f"{t['id']}:{t['name']}" for t in all_tags]:
                        all_tags.append(tag)
        
        return {
            'videos': standard_videos,
            'tags': all_tags
        }

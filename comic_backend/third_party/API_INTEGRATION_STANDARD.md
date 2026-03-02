# 第三方漫画平台API接入标准

## 概述

本文档定义了如何将新的漫画平台API集成到本系统中的标准规范。遵循此标准可以确保新平台能够无缝接入，与现有功能（JM平台）保持一致的用户体验。

## 当前架构回顾

### 核心组件

```
comic_backend/
├── core/platform.py              # 平台枚举和ID处理
├── third_party/
│   ├── adapter_factory.py        # 适配器工厂
│   ├── base_adapter.py           # 适配器基类
│   ├── jmcomic_adapter.py        # JM平台适配器
│   └── external_api.py           # 外部API调用封装
└── api/v1/comic.py               # 导入API入口
```

### 数据流

```
用户请求导入 → API层 → 适配器工厂 → 平台适配器 → 第三方API
                                              ↓
数据库 ← 转换后的标准格式 ← 平台适配器 ← 响应数据
```

## 新增平台接入步骤

### 第一步：在 core/platform.py 中添加平台枚举

```python
from enum import Enum
from typing import Optional, Tuple

class Platform(Enum):
    JM = "JM"           # 已有平台
    PK = "PK"           # 示例新平台
    YOUR_PLATFORM = "YP"  # 你的新平台

# 平台前缀映射
PLATFORM_PREFIXES = {
    Platform.JM: "JM",
    Platform.PK: "PK",
    Platform.YOUR_PLATFORM: "YP",  # 添加你的平台前缀
}

# 平台名称映射（用于显示）
PLATFORM_NAMES = {
    Platform.JM: "JMComic",
    Platform.PK: "PK平台",
    Platform.YOUR_PLATFORM: "你的平台名称",
}
```

### 第二步：添加平台目录常量

在 `core/constants.py` 中添加：

```python
# 平台图片目录
YP_PICTURES_DIR = "data/pictures/YP"
YP_COVER_DIR = "static/cover/YP"
YP_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/YP"

def ensure_platform_dirs():
    """确保所有平台目录存在"""
    dirs = [
        JM_PICTURES_DIR, PK_PICTURES_DIR, YP_PICTURES_DIR,
        JM_COVER_DIR, PK_COVER_DIR, YP_COVER_DIR,
        JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR, YP_RECOMMENDATION_CACHE_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
```

### 第三步：创建平台适配器

创建文件 `third_party/your_platform_adapter.py`：

```python
"""
你的平台适配器
负责将你的平台API数据转换为系统标准格式
"""

from typing import Dict, List, Any, Optional, Tuple
from third_party.base_adapter import BaseAdapter
from core.platform import Platform
from infrastructure.logger import app_logger, error_logger


class YourPlatformAdapter(BaseAdapter):
    """你的平台适配器"""
    
    def __init__(self, existing_tags: List[Dict] = None):
        self.existing_tags = existing_tags or []
        self.platform = Platform.YOUR_PLATFORM
    
    def get_platform(self) -> Platform:
        """返回平台类型"""
        return self.platform
    
    def search_comics(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        搜索漫画
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大搜索页数
            
        Returns:
            漫画列表，每个漫画包含以下字段：
            - album_id: 原始平台ID（字符串）
            - title: 标题
            - author: 作者
            - tags: 标签名称列表
            - pages: 总页数
            - cover_url: 封面图片URL
        """
        # TODO: 实现搜索逻辑
        # 1. 调用你的平台API进行搜索
        # 2. 解析响应数据
        # 3. 转换为标准格式返回
        pass
    
    def get_comic_detail(self, album_id: str) -> Optional[Dict[str, Any]]:
        """
        获取漫画详情
        
        Args:
            album_id: 漫画原始ID
            
        Returns:
            漫画详情字典，包含：
            - album_id: 原始ID
            - title: 标题
            - author: 作者
            - desc: 描述/简介
            - tags: 标签名称列表
            - pages: 总页数
            - cover_url: 封面URL
        """
        # TODO: 实现详情获取逻辑
        pass
    
    def download_comic(
        self, 
        album_id: str, 
        download_dir: str,
        decode_images: bool = True
    ) -> Tuple[Dict, bool]:
        """
        下载漫画到本地
        
        Args:
            album_id: 漫画原始ID
            download_dir: 下载目录
            decode_images: 是否解密图片（如果你的平台图片加密）
            
        Returns:
            (detail, success)
            detail包含：
            - total_pages: 网络端图片总数
            - local_pages: 本地已下载图片数
            - downloaded: 是否下载成功
        """
        # TODO: 实现下载逻辑
        pass
    
    def get_image_url(self, album_id: str, page_num: int) -> str:
        """
        获取图片在线URL（用于推荐页在线加载）
        
        Args:
            album_id: 漫画原始ID
            page_num: 页码（从1开始）
            
        Returns:
            图片的完整URL
        """
        # TODO: 返回图片的在线URL
        pass
    
    def convert_to_standard_format(
        self, 
        albums: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict]]:
        """
        将平台数据转换为系统标准格式
        
        这是核心转换方法，必须正确实现！
        
        Args:
            albums: 平台原始数据列表
            
        Returns:
            {
                "comics": [...],  # 漫画列表
                "tags": [...]     # 标签列表
            }
        """
        # 标签去重和ID生成
        tag_name_to_id = {}
        tag_id_counter = 1
        
        # 处理已有标签
        for tag in self.existing_tags:
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
                        "create_time": self._get_current_time()
                    })
                    tag_id_counter += 1
                comic_tag_ids.append(tag_name_to_id[tag_name])
            
            # 构建标准漫画格式
            comic = {
                "id": album["album_id"],  # 这里会自动添加平台前缀
                "title": album.get("title", ""),
                "title_jp": album.get("title_jp", ""),
                "author": album.get("author", ""),
                "desc": album.get("desc", ""),
                "cover_path": album.get("cover_url", ""),
                "total_page": album.get("pages", 0),
                "current_page": 1,
                "score": None,
                "tag_ids": comic_tag_ids,
                "list_ids": [],
                "create_time": self._get_current_time(),
                "last_read_time": self._get_current_time(),
                "is_deleted": False
            }
            comics.append(comic)
        
        return {
            "comics": comics,
            "tags": new_tags
        }
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
```

### 第四步：注册适配器到工厂

修改 `third_party/adapter_factory.py`：

```python
from core.platform import Platform
from third_party.jmcomic_adapter import JMComicAdapter
from third_party.your_platform_adapter import YourPlatformAdapter  # 导入新适配器


class AdapterFactory:
    """适配器工厂"""
    
    _adapters = {
        Platform.JM: JMComicAdapter,
        Platform.YOUR_PLATFORM: YourPlatformAdapter,  # 注册新适配器
    }
    
    @classmethod
    def get_adapter(cls, platform: Platform, existing_tags: list = None):
        """获取指定平台的适配器"""
        adapter_class = cls._adapters.get(platform)
        if not adapter_class:
            raise ValueError(f"不支持的平台: {platform}")
        return adapter_class(existing_tags=existing_tags)
```

### 第五步：添加平台图片URL生成逻辑

修改 `core/platform.py`，添加平台图片URL生成：

```python
def get_platform_image_url(platform: Platform, album_id: str, page_num: int) -> Optional[str]:
    """
    获取指定平台的图片在线URL
    
    Args:
        platform: 平台类型
        album_id: 原始漫画ID
        page_num: 页码
        
    Returns:
        图片URL或None
    """
    if platform == Platform.JM:
        return f"https://cdn-msp.jmapinodeudzn.net/media/photos/{album_id}/{page_num:05d}.webp"
    elif platform == Platform.YOUR_PLATFORM:
        # TODO: 返回你的平台的图片URL格式
        return f"https://your-cdn.com/{album_id}/{page_num}.jpg"
    return None
```

## API实现标准

### 必需实现的方法

你的适配器必须实现 `BaseAdapter` 中定义的所有抽象方法：

| 方法 | 必需 | 说明 |
|------|------|------|
| `get_platform()` | ✓ | 返回平台枚举 |
| `search_comics()` | ✓ | 搜索漫画 |
| `get_comic_detail()` | ✓ | 获取详情 |
| `convert_to_standard_format()` | ✓ | 数据转换 |
| `download_comic()` | 可选 | 下载到本地（主页需要） |
| `get_image_url()` | 可选 | 在线图片URL（推荐页需要） |

### 数据格式标准

#### 搜索/详情返回格式

```python
{
    "album_id": "123456",           # 原始平台ID（字符串）
    "title": "漫画标题",            # 标题
    "author": "作者名",             # 作者
    "desc": "简介...",              # 描述（可选）
    "tags": ["标签1", "标签2"],     # 标签名称列表
    "pages": 24,                    # 总页数（整数）
    "cover_url": "https://..."      # 封面图片URL
}
```

#### 转换后的标准格式

```python
{
    "comics": [
        {
            "id": "YP123456",               # 会自动添加平台前缀
            "title": "漫画标题",
            "title_jp": "",                  # 日文标题（可选）
            "author": "作者名",
            "desc": "简介...",
            "cover_path": "https://...",     # 或本地路径
            "total_page": 24,
            "current_page": 1,
            "score": None,
            "tag_ids": ["tag_001", "tag_002"],
            "list_ids": [],
            "create_time": "2026-03-02T10:00:00",
            "last_read_time": "2026-03-02T10:00:00",
            "is_deleted": False
        }
    ],
    "tags": [
        {
            "id": "tag_001",
            "name": "标签名称",
            "create_time": "2026-03-02T10:00:00"
        }
    ]
}
```

## 目录结构标准

新平台的文件存储遵循以下结构：

```
data/
├── pictures/
│   ├── JM/           # JM平台
│   ├── PK/           # PK平台
│   └── YP/           # 你的平台（使用平台前缀小写）
│       └── {album_id}/
│           ├── 00001.jpg
│           ├── 00002.jpg
│           └── ...
├── recommendation_cache/
│   ├── JM/
│   ├── PK/
│   └── YP/           # 你的平台缓存目录
└── meta_data/
    ├── comics_database.json
    └── recommendations_database.json

static/
└── cover/
    ├── JM/
    ├── PK/
    └── YP/           # 你的平台封面目录
        └── {album_id}.jpg
```

## 错误处理标准

所有API调用必须包含适当的错误处理：

```python
def search_comics(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
    try:
        # API调用逻辑
        response = self._call_api(...)
        return self._parse_response(response)
    except requests.RequestException as e:
        error_logger.error(f"网络请求失败: {e}")
        return []
    except json.JSONDecodeError as e:
        error_logger.error(f"JSON解析失败: {e}")
        return []
    except Exception as e:
        error_logger.error(f"搜索漫画失败: {e}")
        return []
```

## 测试要求

在提交新平台适配器前，请确保：

1. **单元测试**：测试数据转换逻辑
2. **集成测试**：测试实际API调用
3. **边界测试**：处理空结果、网络错误等情况

## 示例：最小化实现

以下是一个最小化的适配器实现示例：

```python
import requests
from typing import Dict, List, Any, Optional, Tuple
from third_party.base_adapter import BaseAdapter
from core.platform import Platform


class MinimalAdapter(BaseAdapter):
    """最小化适配器示例"""
    
    API_BASE = "https://api.your-platform.com"
    
    def __init__(self, existing_tags: List[Dict] = None):
        self.existing_tags = existing_tags or []
        self.platform = Platform.YOUR_PLATFORM
        self.session = requests.Session()
    
    def get_platform(self) -> Platform:
        return self.platform
    
    def search_comics(self, keyword: str, max_pages: int = 1) -> List[Dict[str, Any]]:
        """搜索漫画"""
        results = []
        
        for page in range(1, max_pages + 1):
            try:
                response = self.session.get(
                    f"{self.API_BASE}/search",
                    params={"q": keyword, "page": page}
                )
                response.raise_for_status()
                data = response.json()
                
                for item in data.get("results", []):
                    results.append({
                        "album_id": str(item["id"]),
                        "title": item["title"],
                        "author": item.get("artist", ""),
                        "tags": item.get("tags", []),
                        "pages": item.get("page_count", 0),
                        "cover_url": item.get("cover", "")
                    })
            except Exception as e:
                error_logger.error(f"搜索失败: {e}")
                break
        
        return results
    
    def get_comic_detail(self, album_id: str) -> Optional[Dict[str, Any]]:
        """获取详情"""
        try:
            response = self.session.get(f"{self.API_BASE}/album/{album_id}")
            response.raise_for_status()
            data = response.json()
            
            return {
                "album_id": str(data["id"]),
                "title": data["title"],
                "author": data.get("artist", ""),
                "desc": data.get("description", ""),
                "tags": data.get("tags", []),
                "pages": data.get("page_count", 0),
                "cover_url": data.get("cover", "")
            }
        except Exception as e:
            error_logger.error(f"获取详情失败: {e}")
            return None
    
    def convert_to_standard_format(self, albums: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """转换为标准格式"""
        # 使用基类提供的通用转换方法
        return self._convert_albums_to_comics(albums)
```

## 提交清单

在提交新平台适配器前，请确认：

- [ ] 平台枚举已添加到 `core/platform.py`
- [ ] 目录常量已添加到 `core/constants.py`
- [ ] 适配器类已实现所有必需方法
- [ ] 适配器已注册到 `adapter_factory.py`
- [ ] 图片URL生成逻辑已添加（如需要在线加载）
- [ ] 错误处理已完善
- [ ] 代码通过类型检查（无类型错误）
- [ ] 基本功能测试通过

## 联系与支持

如有问题，请参考：
- JM平台适配器实现：`third_party/jmcomic_adapter.py`
- 基类定义：`third_party/base_adapter.py`
- 数据转换示例：`third_party/adapter.py` 中的 `_convert_album_to_comic` 方法

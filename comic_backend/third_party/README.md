# 第三方库文件夹
# 将第三方 API 库放在此目录，然后在此模块中调用

## 架构说明

本模块采用适配器工厂模式，支持多个第三方 API 的集成和切换。

### 核心组件

1. **base_adapter.py** - 适配器基类
   - 定义所有适配器必须实现的接口
   - 提供统一的配置管理

2. **adapter_factory.py** - 适配器工厂
   - 管理所有适配器的注册和实例化
   - 单例模式管理适配器实例
   - 配置文件管理

3. **external_api.py** - 统一接口
   - 提供简洁的 API 调用接口
   - 自动选择默认适配器
   - 支持动态切换适配器

4. **adapter.py** - 数据转换适配器
   - 将第三方 API 格式转换为应用格式
   - 实现去重检查逻辑

5. **jmcomic_adapter.py** - JMComic 适配器实现
   - 基于 JMComic-Crawler-Python 库
   - 实现所有必需的接口方法

### 配置文件

`third_party_config.json` - 全局配置文件

```json
{
  "default_adapter": "jmcomic",
  "adapters": {
    "jmcomic": {
      "enabled": true,
      "config_path": "third_party/JMComic-Crawler-Python/config.json",
      "username": "",
      "password": ""
    }
  }
}
```

### 添加新的第三方 API

1. 创建新的适配器类，继承 `BaseAdapter`
2. 实现所有必需的方法：
   - `get_album_by_id(album_id)`
   - `search_albums(keyword, max_pages)`
   - `get_favorites()`
3. 在 `adapter_factory.py` 中注册适配器
4. 在配置文件中添加配置

### 使用示例

```python
from third_party.external_api import get_album_by_id, search_albums, get_favorites

# 根据ID获取漫画
album = get_album_by_id("123456")

# 搜索漫画
result = search_albums("关键词", max_pages=2)

# 获取收藏夹
favorites = get_favorites()

# 使用指定适配器
from third_party.external_api import get_adapter
adapter = get_adapter("jmcomic")
```

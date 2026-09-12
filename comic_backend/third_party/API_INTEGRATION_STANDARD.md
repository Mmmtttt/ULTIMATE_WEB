# 第三方插件 API 集成标准

> 文档版本：2.0
> 适用范围：`ULTIMATE_WEB` 当前协议驱动第三方插件架构
> 规范文件：`comic_backend/third_party/**/ultimate-plugin.json`

本文档是新增或迁移第三方内容源时应遵循的正式 API 标准。文档以当前代码实现为准；早期的 `Platform` 枚举、`BaseAdapter`、`AdapterFactory` 和宿主侧平台注册方案不再是新插件的接入方式。

## 1. 设计原则

第三方库必须实现为自描述插件。宿主只负责扫描、校验、配置、能力路由和统一结果处理，不应根据具体平台名称编写业务分支。

插件负责调用第三方网站或 SDK、处理平台特有数据和认证、将平台能力映射为协议 capability，并声明配置、展示、资源、目录和各平台打包策略。

宿主负责扫描并校验清单、动态加载 Provider、按 `plugin_id + capability` 调用插件、管理运行时配置，以及按通用协议字段完成路由和展示。

```text
业务 API / Application Service
        |
        v
ProtocolHostService / ProtocolGateway
        |
        v
PluginRegistry -> PluginManifest
        |
        v
ProviderManager -> plugin.entrypoint
        |
        v
ProtocolProvider.execute(capability, params, context, config)
        |
        v
第三方库实现
```

## 2. 插件目录与入口

宿主递归扫描：

```text
comic_backend/third_party/**/ultimate-plugin.json
```

最小目录结构：

```text
your-plugin/
├── ultimate-plugin.json
├── ultimate_provider.py
└── ...第三方库及平台适配代码
```

`plugin.entrypoint` 使用“模块路径或相对 Python 文件路径:Provider 类名”格式：

```json
"entrypoint": "./ultimate_provider.py:YourProvider"
```

也支持：

```json
"entrypoint": "your_package.provider:YourProvider"
```

Provider 应继承 `protocol.base.ProtocolProvider`，并至少实现 `execute()`。基类提供以下扩展点：

```python
class ProtocolProvider:
    def __init__(self, manifest: dict, manifest_path: str): ...
    def normalize_config(self, payload: dict) -> dict: ...
    def serialize_public_config(self, config: dict) -> dict: ...
    def get_query_status(self, config: dict) -> dict: ...
    def build_client(self, config: dict, *args, **kwargs): ...
    def execute(self, capability: str, params: dict, context: dict, config: dict): ...
```

插件模块应使用自己的唯一前缀命名。不要在多个插件目录中放置同名顶层模块，例如都叫 `android_runtime.py`，否则多个插件加入 `sys.path` 后可能发生导入冲突。

## 3. `ultimate-plugin.json`

### 3.1 最小清单

```json
{
  "protocol_version": "1.0",
  "plugin": {
    "id": "comic.example",
    "name": "示例漫画源",
    "version": "1.0.0",
    "entrypoint": "./ultimate_provider.py:ExampleProvider",
    "config_key": "example"
  },
  "media_types": ["comic"],
  "capabilities": [
    { "key": "catalog.search" },
    { "key": "catalog.detail" }
  ]
}
```

### 3.2 顶层字段

| 字段 | 必需 | 说明 |
| --- | --- | --- |
| `protocol_version` | 是 | 当前支持 `1.0`、`1.1`、`2.0` |
| `plugin` | 是 | 插件身份、Provider 入口和配置键 |
| `media_types` | 是 | `comic`、`video`，可同时声明多个 |
| `capabilities` | 是 | 插件实际实现的能力列表 |
| `identity` | 否 | 平台查找名、ID 前缀和显示名 |
| `presentation` | 否 | 前端展示差异 |
| `configuration` | 否 | 动态配置表单和配置动作 |
| `helpers` | 否 | 插件自带的帮助页等静态资源 |
| `storage` | 否 | 数据目录绑定 |
| `collections` | 否 | 收藏夹、清单和虚拟清单描述 |
| `resource_policy` | 否 | 远程资源请求、下载、刷新策略 |
| `runtime` | 否 | Python 搜索路径和 vendor 目录 |
| `packaging` | 否 | 各平台打包策略，尤其是 Android |
| `actions` | 否 | 插件级动作；配置动作也可写在 `configuration.actions` |

### 3.3 `plugin`

```json
"plugin": {
  "id": "comic.example",
  "name": "示例漫画源",
  "version": "1.0.0",
  "entrypoint": "./ultimate_provider.py:ExampleProvider",
  "config_key": "example"
}
```

- `id` 是全局唯一主键，发布后不应随意修改。
- `name` 是默认展示名，`version` 是插件版本。
- `entrypoint` 指向 Provider；`config_key` 是运行时配置键，没有配置项时可以省略。
- `config_parent_key`、`effective_config_key` 可用于复用兼容的配置，但必须确保语义一致。

### 3.4 `identity`

```json
"identity": {
  "content_type": "comic",
  "host_id_prefix": "EXAMPLE",
  "platform_label": "示例源",
  "aliases": ["example", "示例"]
}
```

宿主会使用 `plugin.id`、`config_key`、`plugin.name`、`platform_label`、`host_id_prefix` 和 `aliases` 查找插件。`host_id_prefix` 用于带平台前缀的内容 ID，必须稳定且唯一。

## 4. Capability API

### 4.1 Provider 执行接口

所有平台能力最终通过同一个方法执行：

```python
def execute(
    self,
    capability: str,
    params: dict,
    context: dict,
    config: dict,
):
    ...
```

要求：

- `capability` 只能处理清单中声明的能力。
- 缺少必需参数时抛出清晰的 `ValueError` 或 `RuntimeError`。
- 网络错误、凭据错误和第三方响应格式错误应转换为可读错误。
- 返回值必须是可 JSON 序列化的字典、列表、布尔值或字符串。
- 不得直接返回第三方库对象、响应对象或文件句柄。
- `config` 由宿主注入，`context` 只用于请求级上下文。

### 4.2 能力命名

```text
catalog.*       内容检索和详情
collection.*    收藏夹和清单
person.*        演员或人物
taxonomy.*      标签和分类
asset.*         封面、预览和内容下载
storage.*       本地目录解析
playback.*      视频播放源和代理
transport.*     插件专用网络请求
health.*        配置和健康状态
```

能力应描述宿主需要的业务动作，不要暴露第三方库内部类名或固定 URL。

### 4.3 当前标准能力

| Capability | 主要参数 | 返回约定 |
| --- | --- | --- |
| `catalog.search` | `keyword`、`page`、`max_pages`、`fast_mode` | 漫画通常为 `{ "albums": [...] }`；视频通常为 `{ "videos": [...] }`，兼容 `works` |
| `catalog.detail` | 漫画用 `album_id`；视频用 `video_id` | 单条详情字典，或包含单条详情的字典 |
| `catalog.by_code` | `code` | 视频按番号等编码查询的详情 |
| `person.search` | `actor_name` | 人物/演员列表 |
| `person.works` | `actor_id`、`page`、`max_pages` | 作品分页结果 |
| `collection.favorites` | 插件特有参数 | 完整收藏数据 |
| `collection.favorites_basic` | 插件特有参数 | 轻量收藏条目 |
| `collection.list` | 插件特有参数 | `{ "lists": [...] }` |
| `collection.detail` | `list_id` | 漫画通常为 `albums`，视频通常为 `works` 或 `videos` |
| `taxonomy.tags` | 插件特有参数 | 标签体系或标签列表 |
| `taxonomy.tag_search` | 插件特有参数 | 按标签查询结果 |
| `asset.bundle.fetch` | `album_id`、`download_dir`、`show_progress`、`extra` | `{ "detail": {...}, "success": true/false }` |
| `asset.cover.fetch` | `album_id`、`save_path`、`show_progress` | `{ "detail": {...}, "success": true/false }` |
| `asset.preview.resolve` | `album_id`、`preview_pages` | 预览页 URL 或预览描述 |
| `storage.comic_dir.resolve` | `album_id`、`author`、`title`、`base_dir` | 本地漫画目录路径或路径描述 |
| `playback.sources.build` | `code` | 播放源列表或播放源描述 |
| `playback.proxy.stream` | `domain`、`path`、`query_string`、`incoming_referer` | 流式代理结果 |
| `playback.proxy.url` | `method`、`body_url`、请求头等 | 普通 URL 代理结果 |
| `transport.http.request` | `method`、`url`、`headers`、`stream`、`timeout` | 插件请求栈的响应描述 |
| `health.query.status` | 无 | `{ "configured": bool, "message": str, "missing_fields": [...] }` |

插件只需声明自己真正实现的能力。未声明的能力不能由宿主假设存在。

### 4.4 搜索和详情字段

漫画搜索或详情建议返回：

```json
{
  "album_id": "123456",
  "title": "漫画标题",
  "title_jp": "原始标题",
  "author": "作者",
  "desc": "简介",
  "tags": ["标签1", "标签2"],
  "pages": 24,
  "cover_url": "https://example.invalid/cover.jpg"
}
```

`album_id` 和 `title` 是最低限度的业务字段。`pages` 应为整数；未知时使用 `0`。视频结果使用项目现有视频字段约定，并保持 `video_id`、标题、封面、番号等宿主所需字段稳定。

### 4.5 下载结果

`asset.bundle.fetch` 和 `asset.cover.fetch` 应返回：

```json
{
  "detail": {
    "album_id": "123456",
    "total_pages": 24,
    "local_pages": 24
  },
  "success": true
}
```

失败时 `success` 必须为 `false`；`detail` 可以保留已完成数量或错误摘要。下载实现应支持重复执行和部分完成恢复。

## 5. 配置 API

### 5.1 Provider 配置方法

```python
def normalize_config(self, payload: dict) -> dict: ...
def serialize_public_config(self, config: dict) -> dict: ...
def get_query_status(self, config: dict) -> dict: ...
```

宿主统一读写 `third_party_config.json`，插件不能要求宿主为自己增加专用配置接口。敏感字段必须在清单中标记 `secret: true`，并在 `serialize_public_config()` 中脱敏。

### 5.2 动态配置清单

```json
"configuration": {
  "order": 30,
  "label": "示例源",
  "sections": [
    {
      "id": "basic",
      "label": "基础配置",
      "fields": [
        { "key": "enabled", "label": "启用", "type": "boolean" },
        { "key": "domain", "label": "域名", "type": "text" },
        { "key": "cookie", "label": "Cookie", "type": "textarea", "secret": true }
      ]
    }
  ]
}
```

当前常用字段类型：`boolean`、`text`、`password`、`textarea`、`number`。配置帮助页可通过 `helpers` 和 `configuration.actions` 声明，当前支持 `static_page` 与 `open_url`。

## 6. 展示、资源和存储

### 6.1 展示差异

```json
"presentation": {
  "media_card": {
    "cover": {
      "aspect_ratio": "2 / 3",
      "mobile_aspect_ratio": "2 / 3",
      "fit": "cover",
      "path_mode": "local_static"
    },
    "badge": {
      "show_platform_label": true,
      "label": "示例源"
    }
  }
}
```

平台视觉差异应通过 `presentation` 表达，宿主和前端不应通过平台名称判断卡片比例或封面策略。

### 6.2 远程资源策略

```json
"resource_policy": {
  "assets": {
    "preview_video": {
      "available": true,
      "download_enabled": true,
      "request_profiles": [
        {
          "match_hosts": ["cdn.example.invalid"],
          "referer": "https://example.invalid/",
          "cookie_config_key": "example",
          "cookie_field_path": "cookie",
          "headers": { "Origin": "https://example.invalid" },
          "frontend_proxy": true
        }
      ]
    }
  }
}
```

该字段可以描述可用性、是否允许下载、匹配域名、Referer、Origin、Cookie 来源、额外请求头、前端代理和过期刷新提示。认证和解密逻辑仍由 Provider 实现。

### 6.3 存储和清单

```json
"storage": {
  "data_dir_bindings": [
    { "config_field": "download_dir", "relative_dir": "comic/{host_prefix}" }
  ]
},
"collections": {
  "list_mode": "virtual_only",
  "virtual_lists": [
    { "id": "favorites", "name": "我的收藏", "capability": "collection.favorites_basic" }
  ]
}
```

目录绑定用于补默认目录和迁移；真实内容目录应通过 `storage.comic_dir.resolve` 返回。没有独立远程清单 API 时，可以用虚拟清单包装已有 capability。

## 7. 宿主调用方式

新业务代码优先使用协议层：

```python
from protocol.host_service import get_protocol_host_service

host = get_protocol_host_service()
result = host.execute_comic_adapter(
    "catalog.search",
    {"keyword": keyword, "page": 1, "max_pages": 1},
    adapter_name="example",
)
```

也可以直接使用统一 Gateway：

```python
from protocol import get_protocol_gateway

gateway = get_protocol_gateway()
result = gateway.execute_plugin(
    "comic.example",
    "catalog.detail",
    params={"album_id": "123456"},
)
```

需要客户端风格接口时使用 `gateway.get_client(plugin_id)`。`third_party/external_api.py`、`third_party/platform_service.py` 和旧应用层包装仍是兼容壳，新代码不应围绕它们增加平台逻辑。

## 8. Android 打包标准

### 8.1 声明 Android 支持

```json
"packaging": {
  "android": {
    "enabled": true,
    "pip_options": ["--no-deps"],
    "pip_requirements": ["example-package==1.0.0"],
    "pip_install_args": []
  }
}
```

当前主项目 Android 构建使用 `android_backend_third_party_mode: "supported"`：只打包 `packaging.android.enabled` 为 `true` 的插件，并同步过滤协议快照，保证快照中的可运行插件与实际 Provider 集合一致。

未声明 Android 支持的插件不会被当前 Android supported 模式打包；桌面端仍按桌面运行时加载。Android 支持声明代表插件已提供适配和依赖声明，不代表桌面二进制可以直接放入 APK。

如果一个被打包的插件目录内还包含其他 `ultimate-plugin.json`，Android supported 模式仍以每个插件自己的 `packaging.android.enabled` 为准。未声明支持 Android 的嵌套 manifest 会在 APK 运行时副本中被移除，避免宿主扫描时注册桌面专用插件；源码文件可以随目录存在，但不会作为 Android 插件启用。

### 8.2 依赖和运行时适配

- `pip_requirements` 只声明插件自己需要的依赖。
- 与宿主重复的基础依赖必须保持兼容。
- 使用 `--no-deps` 前必须确认传递依赖已由插件清单或宿主提供。
- 必须优先使用 Chaquopy/Android 可用的 wheel 或纯 Python 包。
- Windows/Linux 专用二进制必须替换为 Android 实现，或由插件声明该能力不可用。
- 不要把需要外置浏览器二进制、系统服务或桌面进程模型的依赖直接声明进 Android，例如 Playwright。确需支持时，应在插件内部提供 Android 等价实现或降级能力。
- Android 适配代码放在插件目录内，主项目不能出现平台专用分支。

推荐结构：

```text
your-plugin/
├── ultimate-plugin.json
├── ultimate_provider.py
└── your_plugin_android_runtime.py
```

插件可以在 Provider 内按运行环境处理线程数、解码器、临时目录、网络库或 Android API 差异。适配模块必须使用插件专属前缀，避免导入冲突。

### 8.3 Android 回退模式

Android 构建支持：

- `disabled`：不打包第三方运行时。
- `external`：不把第三方库源码打进 APK，只把声明支持 Android 的插件依赖预置进 APK，并在运行时从应用私有 `plugins/` 目录加载用户安装的扩展包。
- `selected`：只打包指定插件。
- `supported`：打包所有声明 Android 支持的插件，当前推荐模式。
- `all`：打包扫描到的所有插件，仅适合实验性验证。

新增插件或 Android 适配失败时，可以暂时切回 `disabled` 或 `selected`，不会改变 Windows、Linux、Docker 的插件加载方式。

### 8.4 扩展包模式

桌面端 `plugin_package_mode: "external"` 和 Android 端 `android_backend_third_party_mode: "external"` 都遵循同一个原则：

- 主程序包不预置第三方插件源码，也不会在启动后显示未安装的第三方平台。
- 打包阶段根据各插件 `packaging.external.pip_requirements` 或 `packaging.android.pip_requirements` 构建通用依赖池。
- 用户通过第三方配置页安装本地 `.zip` 扩展包；安装后需要重启后端或应用。
- 安装时宿主只校验协议清单、平台支持声明、路径安全和依赖池是否覆盖扩展声明的依赖；宿主不识别具体平台名称。

扩展包内容应是一个普通 zip，内部必须且只能包含一个 `ultimate-plugin.json`，且 Provider 代码和插件资源位于该 manifest 所在目录下。例如：

```text
comic-example.zip
└── comic-example/
    ├── ultimate-plugin.json
    ├── ultimate_provider.py
    └── example_runtime.py
```

如果扩展包声明了当前安装包没有预置的依赖，安装会被拒绝。需要新增依赖时，应先更新插件 manifest，再重新打包主程序依赖池。

也可以在第三方配置页输入公开 GitHub 仓库链接安装扩展。仓库内容要求与 zip 扩展包完全一致：仓库内必须且只能包含一个 `ultimate-plugin.json`。支持普通仓库链接和指定分支链接，例如：

```text
https://github.com/owner/repo
https://github.com/owner/repo/tree/main
```

当前实现不处理私有仓库授权，也不会在安装扩展时动态安装新 pip 依赖；依赖仍必须由主程序包的通用依赖池预置。

## 9. 新增插件流程

1. 创建独立插件目录和 `ultimate-plugin.json`。
2. 分配唯一 `plugin.id`，声明 `media_types`、`identity` 和真实 capability。
3. 编写 Provider，只在插件内部调用第三方库。
4. 定义各 capability 的参数校验、返回格式和错误行为。
5. 有配置时补充 `configuration` 和三个配置方法。
6. 有封面、预览、播放或目录差异时补充对应协议字段。
7. 支持 Android 时补充 `packaging.android`、依赖和插件内部适配。
8. 编写 Provider 单元测试和协议集成测试。
9. 执行后端测试、前端构建和对应平台打包验证。

禁止在宿主中新增：

```python
if platform == "XX":
    ...
elif platform == "XX":
    ...
```

跨插件的共同需求应优先扩展协议字段，或抽取不带平台语义的通用能力。

## 10. 测试和验收

每个插件至少覆盖：

- 清单发现、协议版本、入口和唯一 ID 校验。
- Provider 加载，以及未声明 capability 的拒绝行为。
- 搜索、详情、空结果和第三方错误。
- 凭据缺失、配置规范化和敏感字段脱敏。
- 下载或预览的成功、部分失败和重复执行。
- 前缀 ID、封面路径、媒体类型和展示描述。
- Android 依赖安装、Provider 导入和关键 capability 调用（如声明 Android 支持）。

推荐验证：

```text
python -m pytest tests/features/third_party_integration -q
python -m pytest comic_backend/tests -q
npm run build --prefix comic_frontend
```

Android 构建后必须检查：

```text
android/app/src/main/python/third_party/
android/app/src/main/python/protocol/mobile_protocol_snapshot.json
android/app/src/main/python/protocol/plugin_dependency_pool_manifest.json
```

集成模式下，`third_party/` 和 `mobile_protocol_snapshot.json` 必须包含同一组可运行插件。只有协议快照而没有 Provider 的插件属于打包错误。

扩展模式下，`third_party/` 和 `mobile_protocol_snapshot.json` 可以为空，但 `plugin_dependency_pool_manifest.json` 必须记录将来允许安装的扩展依赖。

## 11. 当前实现位置

| 组件 | 当前实现 |
| --- | --- |
| 清单扫描与查找 | `comic_backend/protocol/registry.py` |
| 清单对象 | `comic_backend/protocol/base.py` 的 `PluginManifest` |
| Provider 基类与通用客户端 | `comic_backend/protocol/base.py` |
| Provider 动态加载与配置注入 | `comic_backend/protocol/provider_manager.py` |
| 扩展包安装与依赖池校验 | `comic_backend/protocol/extension_service.py` |
| 统一网关 | `comic_backend/protocol/gateway.py` |
| 业务路由 | `comic_backend/protocol/host_service.py` |
| 兼容旧漫画调用 | `comic_backend/protocol/adapter_api.py`、`platform_service.py` |
| Android 选择性打包 | `scripts/package_unified.py`、`build/packagers.json` |
| Android 打包说明 | `docs/android-third-party-packaging.md` |
| 插件实现 | 各插件目录内的 `ultimate_provider.py` |

## 12. 迁移和版本兼容

旧文档中的以下做法已废弃，不应作为新增插件模板：

- 在 `core/platform.py` 增加平台枚举。
- 在 `core/constants.py` 增加平台目录常量。
- 创建 `BaseAdapter` 子类并注册 `AdapterFactory`。
- 在宿主中硬编码平台图片 URL。
- 修改宿主导入流程来适配第三方 API。
- 把 `download_comic()`、`get_image_url()` 等旧适配器方法作为新协议入口。

兼容壳可以继续服务旧调用者，但新插件必须使用 manifest、Provider 和 capability。

已有 `plugin.id`、`host_id_prefix` 或 `config_key` 可能被历史数据和用户配置引用，除非提供迁移，不得随意修改。新增 capability 应保持向后兼容；无法兼容时提升 `protocol_version`，同步更新宿主校验、测试和本标准。

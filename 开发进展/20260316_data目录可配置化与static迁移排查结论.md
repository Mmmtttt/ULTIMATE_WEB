# 2026-03-16 数据目录可配置化与 static 迁移排查结论（仅排查）

## 1. 背景与目标
本次仅进行排查，不改代码。目标是确认以下需求的可行性与落地方案：

1. 将 `static` 目录放到 `data` 目录下（即 `data/static`）。
2. `data` 目录可配置：每次启动从 `server_config.json` 读取路径，并用于后端读写、前端访问（通过后端路由）、第三方下载落盘。
3. 保证迁移后前后端读写与第三方下载行为正常。

---

## 2. 当前现状结论

## 2.1 路径强依赖启动工作目录（cwd）
当前后端启动脚本会先 `cd comic_backend` 再执行 `python app.py`。大量路径使用相对路径（如 `data/...`、`static/...`），因此它们实际上都绑定在 `comic_backend` 目录下。

已确认现有目录结构：
- `comic_backend/data/...`
- `comic_backend/static/cover/...`

这意味着一旦换启动方式（例如从项目根目录直接运行），路径基准会变化，存在跨平台/跨部署不稳定风险。

关键文件：
- `scripts/start_backend.sh`
- `scripts/start_backend.ps1`

## 2.2 `static` 与 `data` 当前分离，且静态服务路径硬编码
后端静态路由直接写死了 `static/cover`：
- `app.static_folder = 'static'`
- `send_from_directory('static/cover', ...)`
- `send_from_directory(f'static/cover/{platform}/author_cache', ...)`

关键文件：
- `comic_backend/app.py`

## 2.3 `data` 路径来源分散：常量 + 硬编码并存
`core/constants.py` 里有大量 `data/...` 与 `static/...` 常量，但业务中仍存在绕过常量的硬编码路径。

典型硬编码位置（非完整列表）：
- `comic_backend/infrastructure/task_manager.py`
  - `data/meta_data/import_tasks.json`
  - `data/meta_data/comics_database.json`
  - `data/meta_data/recommendations_database.json`
- `comic_backend/infrastructure/persistence/cache.py`
  - `CACHE_DIR = 'data/cache'`
- `comic_backend/infrastructure/persistence/repositories/author_repository_impl.py`
  - `data/meta_data/authors_database.json`
- `comic_backend/application/author_app_service.py`
  - `os.path.exists("static/cover/...`)`
- `comic_backend/application/actor_app_service.py`
  - `os.path.exists("static/cover/...`)`
- `comic_backend/api/v1/comic.py`
  - 第三方目录默认值 `../../data/pictures/...`

## 2.4 存在“导入即实例化”的路径时序风险
部分组件在模块导入阶段就初始化，且默认路径写死，若配置加载时机晚于导入，会继续使用旧路径。

关键风险点：
- `recommendation_cache_manager = RecommendationCacheManager()`（模块底部单例）
- `TaskManager()` 单例（虽为延迟导入场景较多，但仍有路径默认值）

关键文件：
- `comic_backend/infrastructure/recommendation_cache_manager.py`
- `comic_backend/infrastructure/task_manager.py`
- `comic_backend/api/__init__.py`
- `comic_backend/api/v1/__init__.py`
- `comic_backend/api/v1/recommendation.py`

## 2.5 第三方下载路径配置链路是多来源
第三方下载目录来源并不单一：

1. 主配置：`comic_backend/third_party_config.json`
2. 适配器工厂默认值：`adapter_factory.py` 中 `../../data/pictures/...`
3. 适配器内部 fallback 默认值：`jmcomic_adapter.py`、`picacomic_adapter.py`

如果不统一归一化，迁移后会出现“部分下载写入新目录、部分仍写回旧目录”的分叉问题。

## 2.6 前端对磁盘路径无直接耦合，但依赖 URL 契约
前端本质依赖 `/static/...` URL，而不是后端磁盘路径：
- Vite 开发代理将 `/static` 转发到后端
- 前端封面工具函数接收 `/static/...` 并直接使用

结论：只要后端继续对外提供兼容的 `/static/...` URL，前端无需感知 `data/static` 的落盘变化。

关键文件：
- `comic_frontend/vite.config.js`
- `comic_frontend/src/utils/helpers.js`
- `comic_frontend/src/api/image.js`

---

## 3. 可行性判断
可行，但属于“中等复杂度、时序敏感”的改造。核心难点不是“改路径字符串”，而是：

1. 启动时配置加载顺序必须先于路径相关单例初始化。
2. 必须建立统一路径解析层，禁止继续散落硬编码。
3. 需要一轮历史数据迁移与兼容策略，避免已有数据不可见。

---

## 4. 建议落地方案（实施蓝图）

## 4.1 配置模型（server_config.json）
建议新增 `storage` 节点：

```json
{
  "backend": { "host": "0.0.0.0", "port": 5005 },
  "frontend": { "host": "0.0.0.0", "port": 5176 },
  "storage": {
    "data_dir": "./comic_backend/data",
    "auto_migrate_legacy": true
  }
}
```

规则建议：
- `data_dir` 支持绝对路径与相对路径。
- 相对路径统一按“项目根目录”解析（不是 cwd）。
- 启动时输出最终解析后的绝对路径到日志。

## 4.2 统一路径注册中心（单一真相源）
新增统一路径解析模块（例如 `core/path_registry.py`），集中产出：

- `DATA_ROOT`
- `STATIC_ROOT = DATA_ROOT/static`
- `COVER_ROOT = DATA_ROOT/static/cover`
- `META_ROOT = DATA_ROOT/meta_data`
- `PICTURES_ROOT = DATA_ROOT/pictures`
- `CACHE_ROOT = DATA_ROOT/cache`
- `RECOMMENDATION_CACHE_ROOT = DATA_ROOT/recommendation_cache`

并由该模块派生出所有现有常量路径，彻底避免 `data/...` 字符串散落。

## 4.3 启动时序改造（必须优先）
建议启动流程：

1. 最早阶段读取 `server_config.json`。
2. 初始化路径注册中心（解析出绝对路径）。
3. 再导入蓝图/服务模块（避免单例提前使用旧默认值）。
4. 初始化目录并注册静态路由。

否则 `recommendation_cache_manager` 这类导入即初始化组件会锁定旧路径。

## 4.4 static 迁移策略
目标是“磁盘迁移，URL 不变”：

- 磁盘：`static/cover/...` -> `<DATA_ROOT>/static/cover/...`
- 对外 URL 保持：`/static/cover/...`
- `send_from_directory` 改为使用路径注册中心提供的绝对目录

这样前端无需改动资源访问逻辑。

## 4.5 第三方下载路径统一策略
改造目标：第三方下载一律落到 `<DATA_ROOT>/pictures/...`。

建议策略：

1. 启动时读取 `third_party_config.json`。
2. 对 `download_dir/base_dir` 执行归一化：
   - 用户配置绝对路径：保留。
   - 用户配置旧相对路径（`data/...` 或 `../../data/...`）：转换到新 `DATA_ROOT` 语义。
   - 为空：填充为基于 `DATA_ROOT` 的默认值。
3. 适配器内部 fallback 默认值也改为引用统一路径注册中心。

## 4.6 分阶段改造清单

### P0（必须同批完成）
- `comic_backend/app.py`（静态目录、路由目录改为注册中心路径）
- `comic_backend/core/constants.py`（所有路径由注册中心派生）
- `comic_backend/infrastructure/recommendation_cache_manager.py`（默认路径与单例初始化）
- `comic_backend/infrastructure/task_manager.py`（硬编码 JSON 路径移除）
- `comic_backend/infrastructure/persistence/cache.py`
- `comic_backend/infrastructure/persistence/repositories/author_repository_impl.py`
- `comic_backend/application/author_app_service.py`
- `comic_backend/application/actor_app_service.py`
- `comic_backend/api/v1/comic.py`（第三方默认路径）
- `comic_backend/third_party/adapter_factory.py`
- `comic_backend/third_party/jmcomic_adapter.py`
- `comic_backend/third_party/picacomic_adapter.py`

### P1（建议同阶段完成）
- 启动脚本输出当前 `data_dir` 实际路径，便于运维定位。
- 文档更新：部署说明、路径说明、迁移说明。

### P2（可选优化）
- 日志目录是否也并入可配置存储根（当前不在本次强需求范围）。

## 4.7 迁移与回滚建议

### 迁移建议
- 启动时检测旧目录：`comic_backend/data` 与 `comic_backend/static`。
- 若新 `data_dir` 为空且检测到旧数据，可自动迁移（受 `auto_migrate_legacy` 控制）。
- 自动迁移建议先 copy 后校验，再按开关清理旧目录，降低风险。

### 回滚建议
- 保留迁移前目录快照。
- 回滚仅需：恢复旧目录 + 将 `storage.data_dir` 指回旧路径。

---

## 5. 验证清单（实施后必测）

1. 启动路径验证
- 相对 `data_dir`、绝对 `data_dir`、不存在目录自动创建。

2. 前端资源访问验证
- 首页/推荐页/视频页封面均可通过 `/static/cover/...` 正常访问。
- 作者缓存封面、演员缓存封面路由可访问。

3. 后端读写验证
- `meta_data` 各 JSON（漫画、推荐、视频、标签、清单、作者/演员）可读写。
- 缓存、推荐缓存、任务文件写入新目录。

4. 第三方下载验证
- JM、PK 下载写入新 `data_dir`。
- JAV 相关图片/封面写入新 `data_dir`。

5. 迁移兼容验证
- 旧数据迁移后可被新服务读取。
- 未迁移场景有明确告警，不出现静默丢失。

---

## 6. 总结
本需求可以实现，且推荐采用“`data_dir` 单一真相源 + static 磁盘迁移但 URL 保持不变”的方案。当前主要阻碍不在前端，而在后端路径分散与初始化时序。按上面的 P0 清单统一收敛后，可稳定支持跨平台部署与后续迁移。

（本文件为排查与方案文档，未修改业务代码。）

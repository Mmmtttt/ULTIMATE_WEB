# ULTIMATE_WEB 全栈功能设计说明书

更新时间：2026-03-15  
适用版本：当前工作区代码（`comic_frontend` + `comic_backend`）

---

## 1. 文档目的与范围

本文档用于说明 ULTIMATE_WEB 当前前后端已实现的用户功能，覆盖以下内容：

- 漫画、视频双模块
- 本地库、预览库
- 详情页、阅读页、在线播放
- 导入（ID/搜索/清单/订阅链路）
- 搜索、标签、清单、订阅、筛选、排序、回收站
- 备份机制、服务端缓存机制、前端缓存机制
- 关键接口与实现位置（精确到文件+函数）

---

## 2. 系统总体设计

### 2.1 分层结构

- 前端：Vue 3 + Pinia + Vue Router + Vant  
  目录：`comic_frontend/src`
- 后端：Flask 蓝图 + 应用服务层 + JSON 持久化  
  目录：`comic_backend`
- 数据：JSON 库 + 图片目录 + 缓存目录 + 备份目录  
  目录：`ULTIMATE_WEB/data`、`ULTIMATE_WEB/static`

### 2.2 请求入口

- 前端请求封装：`comic_frontend/src/api/request.js`
- API 基础路径：`/api/v1/*`
- 后端蓝图注册：`comic_backend/api/__init__.py` -> `register_blueprints`
- 后端启动：`comic_backend/app.py` -> `init_temp_file_cleanup`、`init_default_data`、`init_backup`

### 2.3 主要状态中心（前端）

- 模式与视图：`stores/mode.js`  
  关键函数：`setMode`、`toggleMode`、`setMediaViewMode`
- 漫画本地：`stores/comic.js`  
  关键函数：`fetchComics`、`fetchComicDetail`、`filterMulti`、`sortComics`
- 漫画预览：`stores/recommendation.js`  
  关键函数：`fetchRecommendations`、`fetchRecommendationDetail`、`filterMulti`
- 视频本地：`stores/video.js`  
  关键函数：`fetchList`、`fetchDetail`、`filterMulti`、`sortVideos`
- 视频预览：`stores/videoRecommendation.js`  
  关键函数：`fetchRecommendations`、`fetchDetail`、`filterMulti`
- 清单：`stores/list.js`  
  关键函数：`fetchLists`、`fetchListDetail`、`bindComics`、`bindVideos`
- 标签：`stores/tag.js`
- 订阅：`stores/author.js`、`stores/actor.js`
- 导入任务：`stores/importTask.js`
- 前端缓存：`stores/cache.js`

---

## 3. 前端用户功能设计（含后端落点）

## 3.1 全局框架、模式切换、视图模式

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 漫画/视频模式切换 | 顶部 `ModeSwitch` 点击切换 | 切换后列表、订阅、标签、详情路由逻辑联动 | `components/common/ModeSwitch.vue` `toggle`；`stores/mode.js` `toggleMode` | 无专属接口（使用各模块 API） |
| 视图大小切换（大/中/小/列表） | 本地库/预览库点击 `apps-o` | 写入 `localStorage`，全局生效 | `stores/mode.js` `setMediaViewMode`；`components/common/MediaGrid.vue` `resolvedViewMode` | 无 |
| 响应式布局 | 桌面侧栏，移动端顶栏+Tabbar | 路由一致，布局不同 | `layouts/MainLayout.vue` | 无 |

## 3.2 本地库（漫画/视频）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 列表展示 | 进入 `/library` | 按当前模式切换数据源 | `views/library/Library.vue` `loadData`；`MediaGrid.vue` | `GET /v1/comic/list` `comic_list`; `GET /v1/video/list` `video_list` |
| 统一筛选（标签/作者/清单/最低评分） | 点击筛选按钮 | 漫画额外支持 `未读` | `Library.vue` `applyFilters`; `AdvancedFilter.vue` `emitChange` | `comic.py` `filter_comics` -> `ComicAppService.filter_multi`; `video.py` `filter_videos` -> `VideoAppService.filter_multi` |
| 排序 | 点击排序按钮 | 与模式联动 | `Library.vue` `onSortConfirm` | 漫画：`ComicAppService.get_comic_list`; 视频：`VideoAppService.get_video_list` |
| 批量管理（全选/取消全选/移入回收站） | 菜单进入批量管理 | 全选通过公共工具函数 | `Library.vue` `toggleSelectAllItems` `batchDelete`; `utils/helpers.js` `toggleSelectAll` | 漫画：`/v1/comic/trash/batch-move` `batch_move_to_trash`; 视频：`/v1/video/trash/batch-move` |
| 收藏切换 | 卡片星标 | 实际绑定默认收藏清单 | `Library.vue` `toggleFavorite`; `stores/list.js` `toggleFavorite/toggleFavoriteVideo` | `list.py` `toggle_favorite` / `toggle_favorite_video` |

## 3.3 预览库（漫画/视频）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 推荐库浏览 | 进入 `/preview` | 模式切换决定漫画/视频推荐库 | `views/preview/Preview.vue` `loadData` | 漫画：`/v1/recommendation/list`; 视频：`/v1/video/recommendation/list` |
| 统一筛选与排序 | 同本地库 | 支持标签/作者/清单/最低评分（漫画含未读） | `Preview.vue` `applyFilterAndClose` `onSortConfirm`; `AdvancedFilter.vue` | `recommendation.py` `filter_recommendations`; `video.py` `filter_video_recommendations` |
| 批量操作（全选/回收站） | 批量管理条 | `batchSave` 当前为占位实现 | `Preview.vue` `toggleSelectAllItems` `batchTrash` `batchSave` | `recommendation.py`/`video.py` 对应 trash 批量接口 |

## 3.4 搜索（本地/预览/全网）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 本地搜索 | `/search` -> 本地库 Tab | 直接调用 store 搜索 | `GlobalSearch.vue` `searchLocal` | 漫画：`/v1/comic/search`; 视频：`/v1/video/search` |
| 预览库搜索 | `/search` -> 预览库 Tab | 走推荐库 API | `GlobalSearch.vue` `searchPreview` | 漫画：`/v1/recommendation/search`; 视频：`/v1/video/recommendation/search` |
| 全网搜索 | `/search` -> 全网搜索 Tab | 支持多选、全选、批量导入 | `GlobalSearch.vue` `searchRemote` `toggleSelectAllRemote` `confirmImport` | 漫画：`/v1/comic/search-third-party`；视频：`/v1/video/third-party/search` |
| 全网结果跳转 | 点击全网卡片 | 当前为“先导入再查看”策略（提示导入） | `GlobalSearch.vue` `onItemClick` | 无 |

## 3.5 详情页（漫画/视频/预览）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 漫画详情 | 点击漫画卡片 | 本地与预览使用不同详情页 | `ComicDetail.vue` `fetchComicDetail`; `RecommendationDetail.vue` `fetchDetail` | `/v1/comic/detail` `comic_detail`; `/v1/recommendation/detail` `get_recommendation_detail` |
| 评分/进度/标签 | 详情页内操作 | 评分和进度立即写库 | `handleScoreChange` `markAsRead` `saveTags` | `update_score` `progress` `bind_tags` |
| 收藏与清单绑定 | 详情页按钮 | 复用统一清单变更工具 | `addToLists`; `utils/helpers.js` `applyListMembershipChanges` | `list.py` `bind/remove/toggle/check` |
| 视频详情 | 点击视频卡片 | 本地与预览详情均支持清单/收藏/标签 | `VideoDetail.vue` `loadVideo`; `VideoRecommendationDetail.vue` `loadVideo` | `/v1/video/detail`; `/v1/video/recommendation/detail` |
| 磁力复制 | 点击磁力项 | 本地详情含兼容回退逻辑 | `VideoDetail.vue` `copyMagnet`; `VideoRecommendationDetail.vue` `copyMagnet` | 无专属接口 |
| 作者/演员联动筛选 | 点击作者/演员/标签 | 根据来源跳转本地库或预览库 | `filterByAuthor/filterByTag/goToActor` | 跳转后使用列表筛选接口 |

## 3.6 阅读页（漫画与预览漫画）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 本地阅读 | 漫画详情 -> 开始阅读 | 支持左右/上下、缩放、全屏、进度保存 | `ComicReader.vue` `loadImages` `saveProgress` | `/v1/comic/images` `comic_images`；`/v1/comic/progress` |
| 预览阅读（缓存优先） | 预览详情 -> 开始阅读 | 先查缓存状态，不足则触发缓存下载 | `RecommendationReader.vue` `loadImages` | `/v1/recommendation/cache/status` `get_cache_status`; `/cache/download` `download_to_cache`; `/cache/image` `get_cached_image` |

## 3.7 在线播放（视频）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 拉取播放源 | 点击封面“点击播放” | 返回多源、多清晰度 | `VideoDetail.vue` `loadPlayUrls`; `VideoRecommendationDetail.vue` `loadPlayUrls` | `/v1/video/<id>/play-urls`; `/v1/video/recommendation/<id>/play-urls` |
| HLS 播放/切换清晰度 | 播放器中切源切清晰度 | `hls.js`，通过代理规避跨域 | `switchSource` `changeQuality` `playStream` | `video.py` `proxy_video_request` `/proxy2` |

## 3.8 清单系统（管理/详情/导入/同步）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 清单 CRUD | `/lists` 页面管理 | 默认收藏清单不可删除 | `ListManage.vue` `createList` `updateList` `confirmDelete` | `list.py` `create_list/update_list/delete_list` -> `ListAppService` 对应函数 |
| 清单详情浏览 | 进入 `/list/:id` | 支持筛选、排序、批量下载漫画 | `ListDetail.vue` `loadDetail` `setSortType` `applyFilterAndClose` `handleBatchDownload` | `list.py` `get_list_detail`; 漫画下载 `comic.py` `batch_download_comics` |
| 清单条目跳详情 | 点击清单内内容 | 根据 `source` 跳本地/预览详情页 | `ListDetail.vue` `goToComic` `goToVideo` | 无 |
| 平台清单导入 | 清单管理 -> 导入 | 可导入到本地或预览 | `ListManage.vue` `doImport` | `/v1/list/import` `import_platform_list` -> `ListAppService.import_platform_list` |
| 远程跟踪清单命名 | 导入后自动建追踪清单 | 漫画平台名并入名称避免冲突 | 后端逻辑 | `ListAppService._build_tracking_list_name` `_get_or_create_tracking_list` |
| 平台清单同步 | 清单管理 -> 同步按钮 | 只增量导入新内容 | `ListManage.vue` `syncList` | `/v1/list/sync` `sync_platform_list` -> `ListAppService.sync_platform_list` |
| 清单导入并发 | 同步/导入大清单 | 线程数由环境变量控制 | 后端逻辑 | `_resolve_import_workers` `_run_detail_tasks` |

## 3.9 标签系统

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 标签管理（增删改） | `/tags` 或 `/video-tags` | 漫画/视频复用基类组件 | `BaseTagManage.vue` `addTag/editTag/deleteTag` | `tag.py` `add_tag/edit_tag/delete_tag` -> `TagAppService` |
| 标签详情 | `/tag/:id` 或 `/video-tag/:id` | 本地与预览内容都可进入详情 | `BaseTagDetail.vue` `fetchTagDetail` `goToItem` | `tag.py` `get_tag_comics/get_tag_videos` |
| 批量打标/去标 | 标签管理页多选操作 | 漫画、视频独立批量接口 | `BaseTagManage.vue` `batchAddTags/batchRemoveTags` | `tag.py` `batch_add_*` `batch_remove_*` |

## 3.10 订阅系统（作者/演员）

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 订阅列表 | `/subscribe` | 漫画模式展示作者，视频模式展示演员 | `SubscriptionList.vue` `loadData` | `author.py` `/list`; `actor.py` `/list` |
| 检查更新 | 订阅页点击“检查更新” | 支持全量检查 | `SubscriptionList.vue` `checkAllUpdates` | `author.py`/`actor.py` `check_updates` |
| 创作者作品页 | 点击订阅项进入 `/creator/:name` | 支持分页与批量导入 | `CreatorDetail.vue` `loadData` `confirmImport` | `author.py`/`actor.py` `get_*_works` `search_*_works` |
| 订阅状态维护 | 详情页可订阅作者/演员 | 创作者页 `toggleSubscribe` 当前为占位 | `ComicDetail.vue` `subscribeAuthor`; `VideoDetail.vue` `subscribeActor`; `CreatorDetail.vue` `toggleSubscribe` | `author.py`/`actor.py` `subscribe/unsubscribe` |

## 3.11 回收站

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 查看回收站 | `/trash` | 漫画/视频使用统一基类 | `Trash.vue` + `BaseTrash.vue` `fetchTrashList` | 漫画：`/v1/comic/trash/list`、`/v1/recommendation/trash/list`；视频：`/v1/video/trash/list`、`/v1/video/recommendation/trash/list` |
| 恢复/永久删除/批量 | 回收站操作按钮 | 预览库与本地库分开处理 | `BaseTrash.vue` `restoreItem/deleteItem/batchRestore/batchDelete` | 各模块 `trash/restore` `trash/delete` `trash/batch-*` |

## 3.12 导入与导入任务

| 功能 | 使用方法 | 注意事项 | 前端实现 | 后端实现 |
|---|---|---|---|---|
| 漫画异步导入 | Mine/搜索/订阅发起导入 | 任务可轮询、取消、清理 | `importTaskStore.createImportTask/startPolling`; `ImportTasks.vue` | `comic.py` `/import/async` `/import/tasks` `/import/task/*` -> `TaskManager` |
| 视频第三方导入 | 搜索/Mine/订阅导入 | 按 `code` 去重，支持本地/预览目标 | `videoApi.thirdPartyImport` | `video.py` `third_party_import` + `VideoAppService.import_video` |
| 清单导入/同步 | 清单管理页发起 | 可指定导入到本地或预览 | `ListManage.vue` `doImport` `syncList` | `ListAppService.import_platform_list/sync_platform_list` |
| 最近导入标签（视频） | 视频导入后自动更新 | 新一轮导入会清除旧“最近导入”标记 | 后端逻辑 | `VideoAppService.apply_recent_import_tags` |

---

## 4. 后端关键机制设计

## 4.1 服务层（AppService）职责

- 漫画：`application/comic_app_service.py`  
  `get_comic_list/get_comic_detail/update_score/update_progress/filter_multi/move_to_trash/...`
- 预览漫画：`application/recommendation_app_service.py`  
  `get_recommendation_list/get_recommendation_detail/update_total_page/filter_multi/...`
- 视频：`application/video_app_service.py`  
  `get_video_list/get_video_detail/import_video/filter_multi/apply_recent_import_tags/...`
- 清单：`application/list_app_service.py`  
  `get_list_detail/import_platform_list/sync_platform_list/_import_comics/_import_javdb_videos`
- 标签：`application/tag_app_service.py`
- 订阅：`application/author_app_service.py`、`application/actor_app_service.py`

## 4.2 去重与冲突处理（当前实现）

- 漫画清单导入：按内容 ID（含平台前缀）查重；已存在则补清单绑定  
  位置：`ListAppService._import_comics`
- 视频清单导入：按 `code` 查重；已存在则补清单绑定  
  位置：`ListAppService._import_javdb_videos`（`find_existing_video_by_code`）
- 视频第三方导入：本地与预览均按 `code` 判重  
  位置：`api/v1/video.py` `third_party_import`
- 漫画在线导入：`DuplicateChecker` 过滤重复 ID  
  位置：`api/v1/comic.py` `import_online`

## 4.3 服务端缓存机制（推荐漫画缓存）

- 管理器：`infrastructure/recommendation_cache_manager.py`
- 核心能力：
  - LRU 淘汰：`_evict_lru`
  - 缓存状态：`is_cached/get_cache_status/get_cache_info`
  - 缓存索引修复：`is_cached` 中自愈索引逻辑
  - PK 目录模糊匹配：`_get_pk_comic_dir`、`_fuzzy_match_dir`
  - 统计与清理：`get_cache_stats/clear_cache/cleanup_orphaned_files`
- 对外接口：
  - `recommendation.py` `download_to_cache/get_cache_status/get_cached_image/get_cache_stats/clear_cache/remove_from_cache`
  - `config.py` `get_cache_stats/clear_cache/clean_orphan_cache`

## 4.4 前端缓存机制

- Store：`comic_frontend/src/stores/cache.js`
- 缓存类型：列表、详情、图片、标签、作者、作者作品、预览列表、预览详情
- TTL 来源：`utils/constants.js` `CACHE_EXPIRY`（默认 30 分钟，可本地配置）
- 核心函数：`getListCache/setListCache/getDetailCache/setDetailCache/clearCache/clearExpiredCache`

## 4.5 备份机制（定时三级备份）

- 管理器：`infrastructure/backup_manager.py` `TieredBackupManager`
- 备份层级：
  - Tier1：10 分钟
  - Tier2：1 小时
  - Tier3：1 天
- 覆盖数据源（已对齐漫画/视频）：
  - `comics_database.json`
  - `recommendations_database.json`
  - `videos_database.json`
  - `video_recommendations_database.json`
  - `tags_database.json`
  - `lists_database.json`
- 启动入口：`app.py` `init_backup` -> `init_backup_system`
- API：`backup.py` `get_backup_info/trigger_backup/restore_backup`

## 4.6 `.tmp` 文件清理机制

- 存储层：`infrastructure/persistence/json_storage.py`
  - `_cleanup_stale_temp_files`
  - `cleanup_stale_meta_temp_files`
- 启动时清理：`app.py` `init_temp_file_cleanup`

---

## 5. 功能耦合关系（高频链路）

- 详情页点击作者/标签 -> 跳转库页并附带 query -> 库页自动应用筛选  
  前端：`filterByAuthor/filterByTag` + `Library/Preview` 中 `watch(route.query.*)`
- 收藏本质是默认清单绑定  
  前端：`listStore.toggleFavorite/toggleFavoriteVideo`  
  后端：`list.py` `toggle_favorite*`
- 导入后在多个页面可见（库页、清单、标签、订阅）  
  依赖统一 JSON 数据库与 list/tag 绑定

---

## 6. 当前实现注意事项（使用与维护）

- 远程搜索结果点击不直接进详情，当前策略是“先导入再查看”  
  位置：`GlobalSearch.vue` `onItemClick`
- 预览库 `batchSave` 目前为占位提示（未完成业务实现）  
  位置：`Preview.vue` `batchSave`
- 创作者页 `toggleSubscribe` 当前为占位（提示“稍后完善”）  
  位置：`CreatorDetail.vue` `toggleSubscribe`
- 部分历史文件存在中文注释/文案编码遗留（不影响功能调用路径）

---

## 7. 附录：核心 API 分组速查

### 7.1 漫画

- `comicApi`：`getList/getDetail/getImages/saveProgress/updateScore/filter/search/searchThirdParty/import(online/async)/trash/*/batchDownload`
- 后端：`api/v1/comic.py` + `ComicAppService` + `TaskManager`

### 7.2 推荐漫画

- `recommendationApi`：`getList/getDetail/filter/search/bindTags/trash/*/cache/*`
- 后端：`api/v1/recommendation.py` + `RecommendationAppService` + `RecommendationCacheManager`

### 7.3 视频与视频推荐

- `videoApi`：`getList/getDetail/filter/search/thirdParty*/play-urls/recommendation/*/trash/*`
- 后端：`api/v1/video.py` + `VideoAppService`

### 7.4 清单/标签/订阅/配置/备份

- 清单：`api/list.js` <-> `api/v1/list.py` <-> `ListAppService`
- 标签：`api/tag.js` <-> `api/v1/tag.py` <-> `TagAppService`
- 订阅：
  - 漫画作者：`api/author.js` <-> `api/v1/author.py` <-> `AuthorAppService`
  - 视频演员：`api/video.js` 中 `actorApi` <-> `api/v1/actor.py` <-> `ActorAppService`
- 配置：`api/config.js` <-> `api/v1/config.py` <-> `ConfigAppService`
- 备份：`api/v1/backup.py` <-> `backup_manager.py`

---

## 8. 建议的后续维护规则

- 新增功能优先沿用现有“页面 -> Store -> API -> 蓝图 -> AppService”链路，避免把业务写进组件。
- 统一筛选项保持四要素：标签、作者/演员、清单、最低评分（漫画可加未读）。
- 导入相关逻辑优先复用 `ListAppService` 并发与去重策略，避免分散重复实现。
- 涉及缓存与备份改动时，同时更新 `config.py`、`recommendation_cache_manager.py`、`backup_manager.py` 的联动行为。


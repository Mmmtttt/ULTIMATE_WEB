# 测试门禁架构说明（E2E 为主，测试数据隔离）

## 1. 目标
- 对当前项目的“漫画 + 视频”全量功能建立回归门禁。
- 每次 `push`、每次 `pull_request` 自动执行。
- 本地可执行同一套门禁，保证与 CI 行为一致。
- 不影响现有发布工作流（构建三平台可执行文件的 workflow 保持不变）。

## 2. 总体测试架构
- 主体策略：`E2E : Integration = 80 : 20`。
- E2E（Playwright）负责：
  - 输入：真实用户操作（点击、切换、输入、提交）。
  - 输出：前端显示、前后端请求链路、关键参数。
- Integration（Pytest）负责：
  - 输入：后端 HTTP 接口调用。
  - 输出：接口响应、文件系统落盘、与第三方交互契约（通过 mock/stub）。

## 3. 测试数据与真实数据隔离
- 禁止使用真实业务数据。
- 每次测试使用 `tests/tools/prepare_test_env.py` 自动构建隔离沙箱：
  - 目录：`tests/.runtime/<profile>`（如 `e2e`、`integration`）。
  - 后端通过环境变量切换配置：
    - `SERVER_CONFIG_PATH`
    - `THIRD_PARTY_CONFIG_PATH`
    - `BACKEND_ENABLE_THIRD_PARTY=0`
- 所有读写仅发生在沙箱内，不会触碰真实 `comic_backend/data`。
- 第三方能力默认不连外网，只验证调用契约；必要时使用 mock/stub。

## 4. 目录规范（可追溯）
```text
tests/
  features/
    <feature_name>/
      e2e/
      integration/
  shared/
  tools/
  README.md
  AI_PROMPTS.md
```

规则：
1. 同一功能下，E2E 与 Integration 必须放在同一功能目录。
2. 用例命名必须体现业务行为，失败后可快速定位功能。
3. 所有测试相关文件都放在 `tests/` 下。

## 5. 运行方式
- 一键门禁：
  - Windows: `./tests/run_test_gate.ps1`
  - Linux/macOS: `bash ./tests/run_test_gate.sh`
- 分开执行：
  - Integration: `python -m pytest tests/features -m integration`
  - E2E: `python tests/tools/run_e2e.py`

说明：E2E 必须优先通过 `run_e2e.py` 执行。该脚本会显式启动前后端并在结束后强制回收进程与端口，避免服务常驻。
另外：若本地 Python 环境缺少 `flask_cors`，`run_e2e.py` 会在测试启动阶段注入 no-op fallback（仅测试进程生效），不影响生产代码。

## 6. 已落地用例（当前）
- library_browse
  - e2e: `library_open_detail.spec.js`
  - e2e: `library_open_video_detail.spec.js`
  - e2e: `library_sort_by_score.spec.js`（已升级为强看护）
  - e2e: `library_filter_include_exclude_tags.spec.js`（新增）
  - e2e: `comic_detail_operations.spec.js`（新增，覆盖漫画详情页评分更新、标签绑定、清单加入）
  - e2e: `video_detail_operations.spec.js`（新增，覆盖视频详情页评分更新、进度更新、标签绑定）
  - e2e: `video_library_sort_by_score.spec.js`（新增，覆盖视频库按评分排序）
  - integration: `test_progress_persistence.py`
  - integration: `test_sort_filter_contract.py`（新增）
  - integration: `test_comic_import_contract.py`（新增，覆盖漫画导入、编辑、搜索、详情、评分更新）
  - integration: `test_video_import_contract.py`（新增，覆盖视频导入、评分更新、进度更新）
  - integration: `test_recommendation_contract.py`（新增，覆盖推荐列表、排序、添加）
  - integration: `test_video_progress_contract.py`（新增，覆盖视频进度更新、详情、编辑）
- list_management
  - e2e: `list_manage_create_custom_list.spec.js`
  - e2e: `comic_detail_add_to_custom_list.spec.js`
  - integration: `test_list_create_bind_remove_delete_persistence.py`
  - integration: `test_list_operations.py`（新增，覆盖清单创建、更新、删除、批量操作）
- tag_management
  - e2e: `tag_operations.spec.js`（新增，覆盖标签创建、编辑、删除、绑定）
  - integration: `test_tag_add_edit_bind_delete_persistence.py`
  - integration: `test_tag_content_type_schema_backfill.py`（新增，覆盖缺失 content_type 自动回填）
  - integration: `test_tag_batch_operations.py`（新增，覆盖标签批量添加/移除到漫画/视频）
- trash_management
  - e2e: `comic_move_to_trash_and_restore.spec.js`
  - e2e: `trash_operations.spec.js`（新增，覆盖回收站移入、恢复、永久删除）
  - integration: `test_video_trash_lifecycle_persistence.py`
  - integration: `test_comic_trash_lifecycle.py`（新增，覆盖漫画/视频回收站生命周期）
- global_search
  - e2e: `global_search_local_comic_open_detail.spec.js`
  - integration: `test_search_contract.py`（新增，覆盖漫画/视频本地搜索）
- system_config
  - e2e: `system_config_updates_reader_preferences.spec.js`
  - integration: `test_config_contract.py`（新增，覆盖配置读取、更新、备份）
  - integration: `test_backup_contract.py`（新增，覆盖备份创建、恢复）
  - integration: `test_cache_contract.py`（新增，覆盖缓存统计、清理、配置验证）
- subscribe
  - integration: `test_author_actor_subscription.py`（新增，覆盖作者/演员订阅、更新检查）
- sync_center
  - integration: `test_sync_center_guard.py`（新增，覆盖 session 分层打包/清理 + 双端 directional pull tag/list 映射与资产幂等 + meta-only 分层守卫 + API 鉴权参数守卫 + directional push/task 主链路）

## 7. 排序/筛选强看护（本次重点）
### 7.1 强看护定义
排序/筛选用例必须同时覆盖：
1. 用户操作输入（前端真实交互）。
2. 后端请求参数（`sort_type`、`include_tag_ids`、`exclude_tag_ids`、`authors`、`list_ids`、`min_score/max_score`）。
3. 结果语义（UI 顺序或结果集合），不能只断言“请求发出”。
4. Integration 要把接口结果与沙箱文件数据计算结果对比。

### 7.2 本次新增/升级
- E2E
  - `library_sort_by_score.spec.js`
    - 升级为：参数断言 + UI 标题顺序断言。
  - `library_filter_include_exclude_tags.spec.js`
    - 新增：包含标签 + 排除标签组合筛选；参数断言 + UI 结果集合断言。
- Integration
  - `test_sort_filter_contract.py`
    - comic: `sort_type=score`、`min_score/max_score`、组合筛选。
    - video: `sort_type=score`、`min_score/max_score`、组合筛选。

## 8. 固定多样化种子数据矩阵
说明：采用“固定 + 多样化”而非随机数据，保证失败可复现、可定位。

漫画（5 条）：
- `JM100001`: score 8.5, tags `tag_action`, author `Tester A`, list `list_favorites_comic`
- `JM100002`: score 7.0, tags `tag_story`, author `Tester B`
- `JM100003`: score 9.8, tags `tag_action,tag_drama`, author `Tester C`, list `list_curated_comic`
- `JM100004`: score 6.2, tags `tag_drama`, author `Tester D`, list `list_curated_comic`
- `JM100005`: score 4.1, tags `tag_action,tag_story`, author `Tester B`

视频（3 条）：
- `JAVDB900001`: score 8.0, tags `tag_video`
- `JAVDB900002`: score 9.3, tags `tag_video,tag_video_action`, creator `Video Creator B`, list `list_curated_video`
- `JAVDB900003`: score 5.6, tags `tag_video_story`

## 9. 用例编写硬规范（后续 AI 必须遵守）
每个测试用例前都必须写“用例描述”，包含：
1. 用例目的
2. 测试步骤
3. 预期结果
4. 历史变更（`YYYY-MM-DD + 变更说明`）

位置要求：
- E2E：写在 `test(...)` 前的块注释。
- Integration：写在测试函数 docstring。

## 10. 后续覆盖计划（功能维度）
优先级 P0（先补全）
1. 漫画：导入（by_id/by_search/by_list/task）主链路 + 异常恢复。
2. 视频：导入、详情播放、播放失败降级。
3. 排序/筛选：补齐作者、清单、评分阈值、已读/未读多维组合。
4. 回收站：批量移入/恢复/永久删除（漫画 + 视频）。
5. 标签：批量绑定/移除、跨页面一致性。

优先级 P1（稳定性）
1. 全局搜索三分支（本地/预览/远程 mock）。
2. 系统配置与缓存管理联动。
3. 同步中心（pairing/push/pull/冲突/幂等）。
4. 第三方契约专项（统一 mock/stub）。

优先级 P2（韧性）
1. 并发与幂等。
2. 长任务生命周期（导入任务、重试、取消、恢复）。
3. 边界与异常输入组合。

## 11. 可追溯与失败定位要求
每条用例应明确：
- 输入条件（用户操作或请求参数）
- 预期输出（UI/响应/文件）
- 实际输出
- 定位维度：前端参数组装 / 后端逻辑 / 文件落盘 / 第三方契约

推荐在断言文案中直接带上关键 ID、参数和值，方便 CI 失败时快速定位。
## 12. CI 闸门行为（2026-03-23 更新）
- GitHub `test-gate` 工作流中，Integration 与 E2E 两段都必须执行完，不因前一段失败而中断。
- 最终结果以汇总 gate 为准：只要任一测试段失败，workflow 必须失败并显示红叉。
- 失败排查信息必须回传：
  - `tests/ci-artifacts/integration.log`
  - `tests/ci-artifacts/e2e.log`
  - `tests/ci-artifacts/integration-junit.xml`
  - `tests/playwright-report` 与 `tests/test-results`

## 13. 第三方接口高优先级覆盖（2026-03-25 更新）
新增功能目录：`tests/features/third_party_integration/`

- Integration 看护点：
  - 漫画：`/comic/third-party/config`、`/comic/search-third-party`、`/comic/import/online`
  - 视频：`/video/third-party/search`、`/video/third-party/<platform>/health-status`、`/video/third-party/<platform>/search-by-tags`、`/video/third-party/detail`、`/video/third-party/actor/search`、`/video/third-party/actor/works`、`/video/third-party/import`、`/video/preview-video/refresh`、`/video/actor/search-works`、`/video/actor/works/<actor_id>`、`/video/actor/works-cache/clear`
  - 清单：`/list/platform/lists`、`/list/platform/list/detail`、`/list/import`、`/list/sync`、`/list/import/favorites`、`/list/sync/favorites`
  - 作者/演员：`/author/search-works`、`/author/check-updates`、`/author/new-works`、`/author/works`、`/actor/search-works`、`/actor/check-updates`、`/actor/new-works`、`/actor/works`、`/actor/videos`
  - 推荐与系统配置：`/recommendation/cache/download`、`/config/system`（third-party 路径更新回调）
  - 预览库迁移到本地库异步任务：`/recommendation/migrate-to-local`、`/video/recommendation/migrate-to-local`（仅创建任务，不阻塞导入）
  - 预览下载头：`VideoAppService._build_preview_video_headers`（JAVDB Referer/Cookie）
- E2E 看护点：
  - 用户在 `VideoTagSearch` 页面完成“选标签 -> 搜索 -> 选择结果 -> 导入”，并断言请求参数和导入 body。
  - 用户在 `VideoDetail` 与 `VideoRecommendationDetail` 页面完成“点击播放”，并断言 `play-urls` 请求与 `proxy2` 播放地址映射契约。
  - 视频搜索结果混排（JAVDB 横版 + JAVBUS 竖版）卡片高度与比例守卫。

## 14. Third-party Coverage Matrix (2026-03-25 Latest)
- Current status: `tests/features/third_party_integration/` has `72` integration cases + `5` E2E cases.
- Covered import flows:
  - Comic: `import/online` (`by_id`, `by_search`, `by_favorite`, `home`, `recommendation`), `import/async by_list`.
  - Video: `third-party/import` (`home`, `recommendation`), fallback `get_video_by_code`, duplicate-code guards (`home` and `recommendation`).
  - List: `platform/import`, `platform/sync`, `platform/list/detail`, `import/sync favorites` for `JAVDB/JM/PK`.
  - Preview -> local migrate routes (`comic` and `video`) create async import tasks.
  - Video preview->local migrate cache copy: when preview cache exists, copy cached assets and rewrite local asset paths.
- Covered search flows:
  - Comic third-party keyword search (`platform=all`, invalid platform guard).
  - Video third-party keyword search (`platform=all`, page parameter contract).
  - Video JAVDB tag search (tag parsing, invalid tag IDs, cookie-required branch).
  - Actor third-party search/update chain (`actor` and `video actor` route entries + service adapter calls).
  - E2E "search next page" via `/video-tag-search` load-more path.
- Covered playback/download flows:
  - `play-urls` for local/recommendation data source.
  - E2E click-to-play chain guards:
    - Local detail `/video/:id` click -> `GET /api/v1/video/{id}/play-urls` -> player visible -> `video.src` mapped to `/api/v1/video/proxy2?...`.
    - Recommendation detail `/video-recommendation/:id` click -> `GET /api/v1/video/recommendation/{id}/play-urls` -> player visible -> `video.src` mapped to `/api/v1/video/proxy2?...`.
  - `/video/proxy/*` and `/video/proxy2` forwarding contract (query/body/header/referer).
  - `/video/preview-video/refresh` end-to-end backend chain (frontend request -> third-party detail -> cache scheduling).
  - `/recommendation/cache/download` unavailable branch + third-party download argument contract.
  - `VideoAppService._build_preview_video_headers` cookie/referer isolation behavior.
- Covered list sync/import with third-party:
  - Tracking list creation/update persistence (`platform`, `platform_list_id`, `import_source`).
  - De-dup for sync (existing bound video codes and existing bound comic IDs).
  - JM favorites branch via `/list/import` and non-favorites detail route forwarding.
- Covered author/creator third-party:
  - Author works search contract (`jmcomic/picacomic` mapping).
  - Author new works enrichment (`get_album_by_id`), check-updates persistence, works runtime-guard/cache-only branches.
  - Actor check-updates persistence, new-works delta slicing, works/videos/search route contracts.
  - Actor JAVDB `get_actor_works` (`works` payload) compatibility + cover proxy2 decode download contract.
  - Video actor works cache clear contract (`/api/v1/video/actor/works-cache/clear`).
- Residual risk notes (next priority):
  - Add timeout/retry branch guards for long-running third-party adapter failures.

## 15. Reader Regression Coverage (2026-03-24 Latest)
- New E2E suite directory: `tests/features/reader/e2e/`
- New integration suite directory: `tests/features/reader/integration/`
- Added E2E cases:
  - `local_reader_core_regression.spec.js`
    - route `?page=` restore for local reader
    - page-mode toggle keeps anchor page
    - progress persistence request contract (`/api/v1/comic/progress`)
    - configured default page mode takes effect on first render
  - `preview_reader_cache_and_download_gate.spec.js`
    - cached recommendation-reader path uses `/recommendation/cache/image`
    - cached path must not trigger `/recommendation/cache/download`
    - uncached + runtime third-party disabled fallback enters reader error state
    - recommendation detail "continue reading" opens reader at saved progress
  - `reader_interaction_deep_regression.spec.js`
    - preload order around focus page (regression guard for `calculateLoadSequence`)
    - horizontal/vertical seamless page stitching (gap tolerance guard)
    - desktop interactions: paging, Ctrl+wheel zoom, pan transform, fullscreen toggle
    - local comic detail "continue reading" route + progress restore
    - mobile touch path: pinch zoom and touch pan transform changes
- Added integration cases:
  - `test_recommendation_reader_contract.py`
    - recommendation cache status/image/detail contract consistency
    - recommendation progress persistence and invalid-page validation
- Data strategy for reader cases:
  - Reuses isolated runtime seed assets from `prepare_test_env.py`
  - For recommendation reader cache path, tests write real PNG files into runtime cache directories and verify frontend fetches those files through backend cache-image APIs.

## 16. Reader Single-Page + Progressive Download Gates (2026-03-24)
- Added E2E: `tests/features/reader/e2e/local_reader_core_regression.spec.js`
  - `local reader single-page mode renders one page and keeps paging flow`
  - Guards that `singlePageBrowsing=true` renders exactly one page in local reader and page turn still works.
- Added E2E: `tests/features/reader/e2e/preview_reader_cache_and_download_gate.spec.js`
  - `preview reader single-page mode renders one page and keeps paging flow`
  - Guards that preview reader also honors `singlePageBrowsing=true` with single-page rendering + correct page turn.
  - `preview reader progressively renders cached pages before download call finishes`
  - Guards progressive reading behavior: reader can render cached pages before `/api/v1/recommendation/cache/download` response completes.
- Updated E2E: `tests/features/system_config/e2e/system_config_updates_reader_preferences.spec.js`
  - Now also asserts config PUT body includes `"single_page_browsing":true`.

## 17. Local Visual E2E Mode (Developer Workflow)
- Purpose:
  - Provide a local, visual execution mode so developers can watch real browser interactions and build confidence in E2E guard coverage.
- Command:
  - `python tests/tools/run_e2e.py --visual`
- What `--visual` enables (all-in-one, no extra flags needed):
  - Headed browser (non-headless)
  - Slow motion execution (`slowmo=200ms`)
  - `PWDEBUG` debug mode
  - Playwright UI mode (`--ui`)
- CI behavior remains unchanged:
  - GitHub workflow does not use `--visual`.
  - Gate keeps current fast headless behavior and performance.

## 18. 新增测试用例详细说明（2026-03-26）

### 18.1 library_browse 模块

#### integration: test_comic_import_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_comic_init_rejects_missing_comic_dir | 验证漫画初始化校验目录存在性 | 调用 `/api/v1/comic/init` 传入不存在的漫画目录，期望返回 404 |
| test_comic_init_rejects_duplicate_comic_id | 验证漫画初始化校验ID唯一性 | 调用 `/api/v1/comic/init` 传入已存在的漫画ID，期望返回 400 |
| test_comic_init_rejects_missing_comic_id | 验证漫画初始化校验必要参数 | 调用 `/api/v1/comic/init` 不传 comic_id，期望返回 400 |
| test_comic_edit_updates_metadata_and_persists | 验证漫画编辑接口正确持久化 | 调用 `/api/v1/comic/edit` 更新元数据，验证文件持久化 |
| test_comic_edit_rejects_nonexistent_comic | 验证漫画编辑校验漫画存在性 | 调用 `/api/v1/comic/edit` 传入不存在的ID，期望返回 400 |
| test_comic_search_returns_matching_results | 验证漫画搜索返回正确结果 | 调用 `/api/v1/comic/search` 搜索关键词，验证返回匹配结果 |
| test_comic_search_returns_empty_for_no_match | 验证漫画搜索无匹配时返回空 | 调用 `/api/v1/comic/search` 搜索不存在的关键词，期望返回空列表 |
| test_comic_search_rejects_missing_keyword | 验证漫画搜索校验必要参数 | 调用 `/api/v1/comic/search` 不传关键词，期望返回 400 |
| test_comic_detail_returns_full_info | 验证漫画详情返回完整信息 | 调用 `/api/v1/comic/detail` 获取漫画详情，验证返回完整数据 |
| test_comic_detail_rejects_nonexistent_comic | 验证漫画详情校验漫画存在性 | 调用 `/api/v1/comic/detail` 传入不存在的ID，期望返回 404 |
| test_comic_score_update_persists | 验证漫画评分更新正确持久化 | 调用 `/api/v1/comic/score` 更新评分，验证文件持久化 |
| test_comic_score_rejects_missing_params | 验证漫画评分校验必要参数 | 调用 `/api/v1/comic/score` 不传必要参数，期望返回 400 |

#### integration: test_video_import_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_video_score_update_persists | 验证视频评分更新正确持久化 | 调用 `/api/v1/video/score` 更新评分，验证文件持久化（评分精度需为0.5） |
| test_video_score_rejects_invalid_precision | 验证视频评分校验精度 | 调用 `/api/v1/video/score` 传入无效精度评分，期望返回 400 |
| test_video_progress_update_persists | 验证视频进度更新正确持久化 | 调用 `/api/v1/video/progress` 更新进度，验证文件持久化 |

#### integration: test_recommendation_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_recommendation_list_returns_items | 验证推荐列表返回正确数据 | 调用 `/api/v1/recommendation/list` 获取推荐列表，验证返回数据结构 |
| test_recommendation_list_sort_by_score | 验证推荐列表按评分排序 | 调用 `/api/v1/recommendation/list?sort_type=score`，验证排序正确性 |
| test_recommendation_add_creates_item | 验证添加推荐正确创建记录 | 调用 `/api/v1/recommendation/add` 添加推荐，验证文件持久化 |
| test_recommendation_add_rejects_missing_title | 验证添加推荐校验必要参数 | 调用 `/api/v1/recommendation/add` 不传标题，期望返回 400 |

#### integration: test_video_progress_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_video_progress_update_persists | 验证视频进度更新正确持久化 | 调用 `/api/v1/video/progress` 更新进度（参数为 unit），验证文件持久化 |
| test_video_progress_rejects_invalid_unit | 验证视频进度校验进度值 | 调用 `/api/v1/video/progress` 传入超出范围的进度值，期望返回 400 |
| test_video_progress_rejects_missing_video_id | 验证视频进度校验必要参数 | 调用 `/api/v1/video/progress` 不传 video_id，期望返回 400 |
| test_video_progress_rejects_nonexistent_video | 验证视频进度校验视频存在性 | 调用 `/api/v1/video/progress` 传入不存在的ID，期望返回 400 |
| test_video_detail_returns_full_info | 验证视频详情返回完整信息 | 调用 `/api/v1/video/detail` 获取视频详情，验证返回完整数据 |
| test_video_detail_rejects_nonexistent_video | 验证视频详情校验视频存在性 | 调用 `/api/v1/video/detail` 传入不存在的ID，期望返回 404 |
| test_video_edit_updates_metadata | 验证视频编辑正确持久化 | 调用 `/api/v1/video/edit` 更新元数据，验证文件持久化 |
| test_video_edit_rejects_nonexistent_video | 验证视频编辑校验视频存在性 | 调用 `/api/v1/video/edit` 传入不存在的ID，期望返回 400 |

#### e2e: comic_detail_operations.spec.js
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| comic detail page updates score via API | 验证用户可更新漫画评分 | 用户打开漫画详情页，修改评分，验证请求参数和UI更新 |
| comic detail page toggles favorite via API | 验证用户可切换收藏状态 | 用户打开漫画详情页，点击收藏按钮，验证请求参数 |
| comic detail page moves to trash via API | 验证用户可将漫画移入回收站 | 用户打开漫画详情页，点击移入回收站，验证请求参数，测试结束后恢复数据 |
| comic detail page starts reading and navigates to reader | 验证用户可开始阅读漫画 | 用户打开漫画详情页，点击阅读按钮，验证路由跳转 |

**注意**: 移入回收站测试使用 JM100005 (E2E Comic Epsilon)，测试结束后自动恢复数据，避免影响其他测试。

#### e2e: video_detail_operations.spec.js
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| video detail page updates score via API | 验证用户可更新视频评分 | 用户打开视频详情页，修改评分，验证请求参数和UI更新 |
| video detail page toggles favorite via API | 验证用户可切换收藏状态 | 用户打开视频详情页，点击收藏按钮，验证请求参数 |
| video detail page moves to trash via API | 验证用户可将视频移入回收站 | 用户打开视频详情页，点击移入回收站，验证请求参数 |
| video detail page tag click navigates to library with filter | 验证用户可点击标签跳转筛选 | 用户打开视频详情页，点击标签，验证路由跳转 |

#### e2e: video_library_sort_by_score.spec.js
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| 视频库按评分排序 | 验证视频库评分排序功能 | 用户打开视频库，选择按评分排序，验证请求参数和UI顺序 |

### 18.2 list_management 模块

#### integration: test_list_operations.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_list_create_persists | 验证清单创建正确持久化 | 调用 `/api/v1/list/create` 创建清单，验证文件持久化 |
| test_list_update_persists | 验证清单更新正确持久化 | 调用 `/api/v1/list/update` 更新清单，验证文件持久化 |
| test_list_delete_removes_record | 验证清单删除正确移除记录 | 调用 `/api/v1/list/delete` 删除清单，验证文件移除 |
| test_list_batch_add_comics | 验证批量添加漫画到清单 | 调用 `/api/v1/list/batch-add` 批量添加，验证文件持久化 |
| test_list_batch_remove_comics | 验证批量从清单移除漫画 | 调用 `/api/v1/list/batch-remove` 批量移除，验证文件持久化 |

### 18.3 tag_management 模块

#### integration: test_tag_batch_operations.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_tag_batch_add_to_comics_persists | 验证批量添加标签到漫画 | 调用 `/api/v1/tag/batch-add-tags` 批量添加标签到漫画，验证文件持久化 |
| test_tag_batch_remove_from_comics_persists | 验证批量从漫画移除标签 | 调用 `/api/v1/tag/batch-remove-tags` 批量移除标签，验证文件持久化 |
| test_tag_batch_add_to_videos_persists | 验证批量添加标签到视频 | 调用 `/api/v1/tag/batch-add-tags-to-videos` 批量添加标签到视频，验证文件持久化 |
| test_tag_batch_remove_from_videos_persists | 验证批量从视频移除标签 | 调用 `/api/v1/tag/batch-remove-tags-from-videos` 批量移除标签，验证文件持久化 |
| test_tag_batch_add_rejects_missing_params | 验证批量添加校验必要参数 | 调用 `/api/v1/tag/batch-add-tags` 不传必要参数，期望返回 400 |
| test_tag_get_all_comics_returns_data | 验证获取所有漫画返回正确数据 | 调用 `/api/v1/tag/all-comics` 获取所有漫画，验证返回数据结构 |
| test_tag_get_all_videos_returns_data | 验证获取所有视频返回正确数据 | 调用 `/api/v1/tag/all-videos` 获取所有视频，验证返回数据结构 |
| test_tag_get_comics_by_tag_returns_matching | 验证按标签获取漫画返回正确结果 | 调用 `/api/v1/tag/comics?tag_id=xxx` 获取漫画，验证返回匹配结果 |
| test_tag_get_videos_by_tag_returns_matching | 验证按标签获取视频返回正确结果 | 调用 `/api/v1/tag/videos?tag_id=xxx` 获取视频，验证返回匹配结果 |

#### e2e: tag_operations.spec.js
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| 标签创建 | 验证用户可创建标签 | 用户打开标签管理页面，创建新标签，验证请求参数和UI更新 |
| 标签编辑 | 验证用户可编辑标签 | 用户打开标签管理页面，编辑标签名称，验证请求参数和UI更新 |
| 标签删除 | 验证用户可删除标签 | 用户打开标签管理页面，删除标签，验证请求参数和UI更新 |
| 标签绑定 | 验证用户可绑定标签到内容 | 用户打开内容详情页，绑定标签，验证请求参数和UI更新 |

### 18.4 trash_management 模块

#### integration: test_comic_trash_lifecycle.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_comic_trash_move_and_restore_lifecycle | 验证漫画回收站移入恢复生命周期 | 调用 `/api/v1/comic/trash/move` 移入回收站，调用 `/api/v1/comic/trash/restore` 恢复，验证文件状态变化 |
| test_comic_trash_permanent_delete_removes_record | 验证漫画永久删除正确移除记录 | 调用 `/api/v1/comic/trash/delete` 永久删除，验证文件记录移除 |
| test_video_batch_trash_move_moves_all | 验证视频批量移入回收站 | 调用 `/api/v1/video/trash/batch-move` 批量移入，验证文件状态变化 |
| test_video_batch_trash_restore_restores_all | 验证视频批量恢复 | 调用 `/api/v1/video/trash/batch-restore` 批量恢复，验证文件状态变化 |
| test_video_batch_permanent_delete_removes_all | 验证视频批量永久删除 | 调用 `/api/v1/video/trash/batch-delete` 批量删除，验证文件记录移除 |
| test_video_trash_list_returns_only_deleted | 验证回收站列表只返回已删除项 | 调用 `/api/v1/video/trash/list` 获取回收站列表，验证只包含已删除项 |
| test_video_trash_move_rejects_nonexistent_video | 验证移入回收站校验视频存在性 | 调用 `/api/v1/video/trash/move` 传入不存在的ID，期望返回 400 |
| test_video_trash_restore_rejects_nonexistent_video | 验证恢复校验视频存在性 | 调用 `/api/v1/video/trash/restore` 传入不存在的ID，期望返回 400 |
| test_video_batch_trash_move_rejects_empty_list | 验证批量移入校验非空列表 | 调用 `/api/v1/video/trash/batch-move` 传入空列表，期望返回 400 |

#### e2e: trash_operations.spec.js
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| trash page complete lifecycle: move to trash, list, and restore | 验证回收站完整生命周期 | 用户移入漫画到回收站，验证列表请求，然后恢复 |
| trash page shows delete button for trashed item | 验证回收站删除按钮存在 | 用户移入漫画到回收站，验证删除按钮可见，然后恢复数据 |
| trash page shows empty button when items exist | 验证回收站清空按钮存在 | 用户移入漫画到回收站，验证清空按钮可见，然后恢复数据 |

**注意**: 回收站测试使用 JM100005 (E2E Comic Epsilon)，测试结束后自动恢复数据，避免影响 library_sort_by_score 等依赖所有漫画在库的测试。

### 18.5 global_search 模块

#### integration: test_search_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_comic_search_returns_matching_results | 验证漫画搜索返回匹配结果 | 调用 `/api/v1/comic/search` 搜索关键词，验证返回匹配结果 |
| test_comic_search_returns_empty_for_no_match | 验证漫画搜索无匹配返回空 | 调用 `/api/v1/comic/search` 搜索不存在的关键词，期望返回空列表 |
| test_video_search_returns_matching_results | 验证视频搜索返回匹配结果 | 调用 `/api/v1/video/search` 搜索关键词，验证返回匹配结果 |
| test_video_search_returns_empty_for_no_match | 验证视频搜索无匹配返回空 | 调用 `/api/v1/video/search` 搜索不存在的关键词，期望返回空列表 |

### 18.6 system_config 模块

#### integration: test_config_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_config_get_returns_user_config | 验证获取配置返回正确数据 | 调用 `/api/v1/config` 获取配置，验证返回数据结构 |
| test_config_update_persists | 验证配置更新正确持久化 | 调用 `/api/v1/config` 更新配置，验证文件持久化 |
| test_config_update_validates_background_value | 验证配置更新校验背景值 | 调用 `/api/v1/config` 传入无效背景值，期望返回 400 |
| test_config_update_validates_page_mode_value | 验证配置更新校验翻页模式 | 调用 `/api/v1/config` 传入无效翻页模式，期望返回 400 |

#### integration: test_backup_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_backup_create_returns_valid_structure | 验证备份创建返回正确结构 | 调用 `/api/v1/backup/create` 创建备份，验证返回数据结构 |
| test_backup_restore_returns_valid_structure | 验证备份恢复返回正确结构 | 调用 `/api/v1/backup/restore` 恢复备份，验证返回数据结构 |

#### integration: test_cache_contract.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_cache_stats_returns_valid_structure | 验证缓存统计返回正确结构 | 调用 `/api/v1/config/cache/stats` 获取缓存统计，验证返回数据结构 |
| test_cache_clear_returns_valid_structure | 验证缓存清理返回正确结构 | 调用 `/api/v1/config/cache/clear` 清理缓存，验证返回数据结构 |
| test_cache_clean_orphan_returns_valid_structure | 验证孤立缓存清理返回正确结构 | 调用 `/api/v1/config/cache/orphan` 清理孤立缓存，验证返回数据结构 |
| test_config_data_path_returns_valid_structure | 验证缓存信息返回正确结构 | 调用 `/api/v1/config/cache/info` 获取缓存信息，验证返回数据结构 |
| test_config_storage_info_returns_valid_structure | 验证系统信息返回正确结构 | 调用 `/api/v1/config/system` 获取系统信息，验证返回数据结构 |

### 18.7 subscribe 模块

#### integration: test_author_actor_subscription.py
| 用例名称 | 用例目的 | 测试内容 |
|---------|---------|---------|
| test_author_subscribe_persists | 验证作者订阅正确持久化 | 调用 `/api/v1/author/subscribe` 订阅作者，验证文件持久化 |
| test_author_unsubscribe_removes_record | 验证作者取消订阅正确移除 | 调用 `/api/v1/author/unsubscribe` 取消订阅，验证文件移除 |
| test_actor_subscribe_persists | 验证演员订阅正确持久化 | 调用 `/api/v1/actor/subscribe` 订阅演员，验证文件持久化 |
| test_actor_unsubscribe_removes_record | 验证演员取消订阅正确移除 | 调用 `/api/v1/actor/unsubscribe` 取消订阅，验证文件移除 |
| test_author_check_updates_returns_data | 验证作者更新检查返回数据 | 调用 `/api/v1/author/check-updates` 检查更新，验证返回数据结构 |
| test_actor_check_updates_returns_data | 验证演员更新检查返回数据 | 调用 `/api/v1/actor/check-updates` 检查更新，验证返回数据结构 |

### 18.8 测试用例统计

| 模块 | Integration 用例数 | E2E 用例数 |
|-----|------------------|-----------|
| library_browse | 28 | 4 |
| list_management | 5 | 2 |
| tag_management | 9 | 1 |
| trash_management | 9 | 1 |
| global_search | 4 | 1 |
| system_config | 11 | 1 |
| subscribe | 6 | 0 |
| **总计** | **72** | **10** |

### 18.9 关键修复记录

| 问题类型 | 修复内容 | 影响用例 |
|---------|---------|---------|
| API端点不匹配 | `/api/v1/comic/import` → `/api/v1/comic/init` | test_comic_trash_lifecycle.py |
| 参数名称不匹配 | `current_unit` → `unit`（视频进度） | test_video_progress_contract.py |
| 响应格式不匹配 | 标签批量操作返回dict而非list | test_tag_batch_operations.py |
| 测试数据不匹配 | 使用种子数据中的ID进行测试 | 多个用例 |
| 评分精度验证 | 视频评分需为0.5精度（9.5而非9.8） | test_video_import_contract.py |
| 请求格式错误 | DELETE请求使用json而非params | test_comic_trash_lifecycle.py |

## 19. E2E Parallel Policy (2026-03-26)

- We keep only one parallel group: `PARALLEL_SAFE_SPECS` in `tests/tools/run_e2e.py`.
- All other E2E specs run serially by default.
- New E2E specs are serial by default, unless explicitly added into `PARALLEL_SAFE_SPECS`.
- Before adding a spec to `PARALLEL_SAFE_SPECS`, confirm it has no shared-state/race impact on other specs.
- `python tests/tools/run_e2e.py` will run:
  1. parallel-safe whitelist (multi-worker)
  2. remaining specs (worker=1 serial)

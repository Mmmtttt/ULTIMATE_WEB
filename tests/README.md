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
  - integration: `test_progress_persistence.py`
  - integration: `test_sort_filter_contract.py`（新增）
- list_management
  - e2e: `list_manage_create_custom_list.spec.js`
  - e2e: `comic_detail_add_to_custom_list.spec.js`
  - integration: `test_list_create_bind_remove_delete_persistence.py`
- tag_management
  - integration: `test_tag_add_edit_bind_delete_persistence.py`
  - integration: `test_tag_content_type_schema_backfill.py`（新增，覆盖缺失 content_type 自动回填）
- trash_management
  - e2e: `comic_move_to_trash_and_restore.spec.js`
  - integration: `test_video_trash_lifecycle_persistence.py`
- global_search
  - e2e: `global_search_local_comic_open_detail.spec.js`
- system_config
  - e2e: `system_config_updates_reader_preferences.spec.js`
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

## 13. 第三方接口高优先级覆盖（2026-03-24 更新）
新增功能目录：`tests/features/third_party_integration/`

- Integration 看护点：
  - 漫画：`/comic/third-party/config`、`/comic/search-third-party`、`/comic/import/online`
  - 视频：`/video/third-party/search`、`/video/third-party/javdb/cookie-status`、`/video/third-party/javdb/search-by-tags`、`/video/third-party/detail`、`/video/third-party/actor/search`、`/video/third-party/actor/works`、`/video/third-party/import`、`/video/preview-video/refresh`、`/video/actor/search-works`、`/video/actor/works/<actor_id>`、`/video/actor/works-cache/clear`
  - 清单：`/list/platform/lists`、`/list/platform/list/detail`、`/list/import`、`/list/sync`、`/list/import/favorites`、`/list/sync/favorites`
  - 作者/演员：`/author/search-works`、`/author/check-updates`、`/author/new-works`、`/author/works`、`/actor/search-works`、`/actor/check-updates`、`/actor/new-works`、`/actor/works`、`/actor/videos`
  - 推荐与系统配置：`/recommendation/cache/download`、`/config/system`（third-party 路径更新回调）
  - 预览下载头：`VideoAppService._build_preview_video_headers`（JAVDB Referer/Cookie）
- E2E 看护点：
  - 用户在 `VideoTagSearch` 页面完成“选标签 -> 搜索 -> 选择结果 -> 导入”，并断言请求参数和导入 body。
  - 用户在 `VideoDetail` 与 `VideoRecommendationDetail` 页面完成“点击播放”，并断言 `play-urls` 请求与 `proxy2` 播放地址映射契约。

## 14. Third-party Coverage Matrix (2026-03-24 Latest)
- Current status: `tests/features/third_party_integration/` has `61` integration cases + `4` E2E cases.
- Covered import flows:
  - Comic: `import/online` (`by_id`, `by_search`, `by_favorite`, `home`, `recommendation`), `import/async by_list`.
  - Video: `third-party/import` (`home`, `recommendation`), fallback `get_video_by_code`, duplicate-code guards (`home` and `recommendation`).
  - List: `platform/import`, `platform/sync`, `platform/list/detail`, `import/sync favorites` for `JAVDB/JM/PK`.
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

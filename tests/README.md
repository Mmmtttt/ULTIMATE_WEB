# 测试门禁架构说明（E2E 为主，隔离数据）

## 1. 目标与约束
- 目标：对当前“漫画 + 视频”全量功能建立回归门禁，防止每次提交/PR 引入回归。
- 原则：系统测试（E2E）为主，复杂逻辑用少量集成测试兜底。
- 数据：测试数据必须测试时自建，与真实数据彻底隔离，可 mock 第三方交互。
- 流水线：每次 `push`、每次 `pull_request` 自动执行；本地可执行同一套门禁。
- 不影响现有发布工作流：`release-three-platforms.yml` 保持不变。

---

## 2. 当前已落地内容
### 2.1 门禁流水线
- 新增工作流：[`test-gate.yml`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\.github\workflows\test-gate.yml)
- 触发：`push` + `pull_request`
- 执行顺序：
1. 后端集成测试（Pytest）
2. 前端 E2E（Playwright）

### 2.2 本地一键门禁
- 执行器：[`run_test_gate.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\run_test_gate.py)
- Windows 包装：[`run_test_gate.ps1`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\run_test_gate.ps1)
- Linux/macOS 包装：[`run_test_gate.sh`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\run_test_gate.sh)

### 2.3 已落地主用例（含高优先级扩展）
- library_browse / E2E：
  - [`library_open_detail.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\e2e\library_open_detail.spec.js)
  - [`library_open_video_detail.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\e2e\library_open_video_detail.spec.js)
  - [`library_sort_by_score.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\e2e\library_sort_by_score.spec.js)
- library_browse / Integration：
  - [`test_progress_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\integration\test_progress_persistence.py)
- global_search / E2E：
  - [`global_search_local_comic_open_detail.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\global_search\e2e\global_search_local_comic_open_detail.spec.js)
- list_management：
  - E2E：
    - [`list_manage_create_custom_list.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\list_management\e2e\list_manage_create_custom_list.spec.js)
    - [`comic_detail_add_to_custom_list.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\list_management\e2e\comic_detail_add_to_custom_list.spec.js)
  - Integration：
    - [`test_list_create_bind_remove_delete_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\list_management\integration\test_list_create_bind_remove_delete_persistence.py)
- tag_management / Integration：
  - [`test_tag_add_edit_bind_delete_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\tag_management\integration\test_tag_add_edit_bind_delete_persistence.py)
- trash_management：
  - E2E：
    - [`comic_move_to_trash_and_restore.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\trash_management\e2e\comic_move_to_trash_and_restore.spec.js)
  - Integration：
    - [`test_video_trash_lifecycle_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\trash_management\integration\test_video_trash_lifecycle_persistence.py)
- system_config / E2E：
  - [`system_config_updates_reader_preferences.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\system_config\e2e\system_config_updates_reader_preferences.spec.js)

---

## 3. 首个用例到底测了什么
### 3.1 E2E 用例（前端真实用户流）
文件：[`library_open_detail.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\e2e\library_open_detail.spec.js)

覆盖点：
1. 打开 `/library` 页面（真实前端路由）。
2. 以用户视角点击“漫画卡片”（按标题 `E2E Comic Alpha` 定位）。
3. 断言页面跳转到 `/comic/JM100001`。
4. 断言详情页标题正确显示。
5. 断言交互链路中包含后端请求：
   - `/api/v1/comic/list`
   - `/api/v1/comic/detail?comic_id=JM100001`

这条用例看护的是：  
`用户点击 -> 前端路由与渲染 -> 与后端关键接口交互 -> 详情落地展示`。

### 3.2 Integration 用例（后端接口 + 文件系统持久化）
文件：[`test_progress_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\integration\test_progress_persistence.py)

覆盖点：
1. 先读取测试沙箱 `comics_database.json`，确认 `current_page=1`。
2. 调用 `PUT /api/v1/comic/progress`，提交 `current_page=2`。
3. 断言 HTTP 响应：
   - `status_code=200`
   - `payload.code=200`
   - `payload.data.current_page=2`
4. 再读回 `comics_database.json`，断言已持久化为 `2`。

这条用例看护的是：  
`前端可发出的交互输入 -> 后端响应正确 -> 后端写文件正确`。

---

## 4. 你问的“简易图片”是否生成
是有生成的，而且现在已补得更明显：
- 漫画页图片：`tests/.runtime/<profile>/data/comic/JM/<id>/001.png ...`
- 封面图片：`tests/.runtime/<profile>/data/static/cover/JM/*.png + *.jpg`
- 默认封面：`tests/.runtime/<profile>/data/static/default/default_cover.jpg`

相关代码：
- 生成占位 PNG/JPG：[`prepare_test_env.py:32`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\prepare_test_env.py:32)
- 媒体文件写入：[`prepare_test_env.py:201`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\prepare_test_env.py:201)
- 生成清单清点：`seed_manifest.json`（每个 profile 会输出）

你可直接执行：
1. `python tests/tools/prepare_test_env.py --profile check --json`
2. 查看：`tests/.runtime/check/seed_manifest.json`

---

## 5. 配置与数据隔离原理（为什么不会污染真实数据）
### 5.1 隔离核心
每次测试会创建独立目录：`tests/.runtime/<profile>`，例如：
- `tests/.runtime/integration`
- `tests/.runtime/e2e`

所有读写都指向该沙箱目录，不指向真实 `comic_backend/data`。

### 5.2 如何切换到沙箱配置
通过环境变量注入：
- `SERVER_CONFIG_PATH=<tests/.runtime/.../server_config.json>`
- `THIRD_PARTY_CONFIG_PATH=<tests/.runtime/.../third_party_config.json>`
- `BACKEND_ENABLE_THIRD_PARTY=0`

这样后端启动后，`core/constants.py` 会按这两个路径加载配置，从而把 `DATA_DIR` 指到沙箱路径。

代码入口：
- 生成配置：[`prepare_test_env.py:227`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\prepare_test_env.py:227)
- 集成测试注入变量：[`conftest.py:30`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\conftest.py:30)
- E2E 注入变量：[`run_e2e.py:102`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\run_e2e.py:102)

### 5.3 为什么进程不会常驻（本地与 CI 一致）
E2E 统一通过 [`run_e2e.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\tools\run_e2e.py) 启停：
1. 显式启动 backend
2. 显式启动 frontend
3. 跑 Playwright
4. `finally` 强制终止进程树 + 清理端口

关键点：
- 进程启动：`_spawn_process`
- 关闭：`_kill_process_tree`
- Windows 端口兜底清理：`_kill_ports_on_windows`

---

## 6. 目录规范（按功能可追溯）
```text
tests/
  features/
    <feature_name>/
      e2e/
      integration/
  tools/
  shared/
  legacy/
```

规则：
1. 同一功能的前后端测试必须同目录聚合。
2. 功能目录名称采用业务语义，不用技术语义。
3. 失败后能直接映射到功能，不能出现“无业务含义”的用例名。
4. 历史旧测试归档在 `tests/legacy/`，不参与新门禁。

---

## 7. 标准化写用例规范（后续 AI 必须遵守）
### 7.1 命名规范
- 功能目录：`snake_case`，例如 `library_browse`、`trash_management`。
- E2E 文件：`<behavior>.spec.js`
- 集成文件：`test_<behavior>.py`

### 7.2 断言规范
- E2E 至少包含 3 类断言：
1. 用户可见结果（文本/状态/跳转）
2. 后端交互请求（URL/方法/关键参数）
3. 非功能性兜底（例如错误 toast 不出现，或 loading 收敛）

- Integration 至少包含 3 类断言：
1. 状态码与业务码
2. 业务字段（输入输出关系）
3. 文件系统持久化（JSON 实际落盘内容）

### 7.3 第三方交互规范
- 不测第三方库内部实现。
- 只测后端调用第三方的契约：
1. 调用时机
2. 入参结构
3. 出参映射
4. 失败重试/降级行为

### 7.4 用例描述规范（新增强制）
- 每个用例前必须写“用例描述”，不允许省略。
- 必填字段：
1. 用例目的
2. 测试步骤
3. 预期结果
4. 历史变更（`YYYY-MM-DD + 变更说明`）
- 位置要求：
1. E2E：写在 `test(...)` 前的块注释中。
2. Integration：写在测试函数 docstring 中。
- 推荐模板：
```text
用例描述:
- 用例目的: ...
- 测试步骤:
  1. ...
  2. ...
- 预期结果:
  1. ...
  2. ...
- 历史变更:
  - 2026-03-23: 初始创建，覆盖 ...
```

---

## 8. AI 提示词规范（强约束版本）
统一提示词文档：[`AI_PROMPTS.md`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\AI_PROMPTS.md)

使用方法：
1. 在任务开头复制“通用约束提示词”。
2. 选择对应场景模板（新增功能 / 修复失败 / 第三方契约 / 数据同步）。
3. 强制要求 AI 产出“可运行用例 + 运行命令 + 失败定位说明”。

---

## 9. 全面覆盖计划（功能维度，深入版）
### 9.1 覆盖总策略
- E2E : Integration 目标比例 = **80 : 20**
- 当前已落地比例（累计）约 **67 : 33**，后续批次继续向 80 : 20 收敛。
- 每个功能最少 1 条主路径 E2E + 1 条关键异常 E2E。
- 仅对复杂后端逻辑补集成测试（文件写入、多表联动、并发、幂等等）。

### 9.2 功能拆解与测试目标
#### A. 漫画模式（Comic）
1. 导入
- by_id / by_search / by_list / async task
- 主路径、重复导入、失败恢复、任务取消
2. 浏览
- 本地库列表、详情、预览图、阅读器翻页
3. 下载与更新
- 下载 zip、更新检查、更新下载、页数同步
4. 标签
- 新建/编辑/删除/绑定/批量绑定/按标签筛选
5. 清单
- 新建清单、加入移除、收藏开关、按清单筛选
6. 排序筛选搜索
- 排序字段、评分筛选、已读未读、组合筛选
7. 回收站删除
- 移入回收站、恢复、永久删除、批量操作

#### B. 视频模式（Video）
1. 导入与列表
- 本地视频导入、推荐导入、列表展示
2. 详情与播放
- 播放地址解析、代理播放流、失败回退
3. 标签与演员
- 视频标签管理、演员检索/过滤
4. 清单收藏
- 视频收藏清单、跨页面保持
5. 回收站删除
- 与漫画同口径验证（单条 + 批量）

#### C. 跨模式通用能力
1. 搜索中心（global search）
2. 配置中心（system/config）
3. 缓存管理（统计、清理）
4. 同步中心（pairing / directional sync）
5. 导入任务中心（task lifecycle）

### 9.3 阶段推进（建议）
#### Phase 1（必须先完成，阻断高风险回归）
- 漫画浏览、详情、阅读进度、标签绑定、收藏清单、回收站
- 视频浏览、详情播放、收藏清单、回收站

#### Phase 2（管理能力补齐）
- 排序/筛选/搜索全组合
- 配置中心 + 缓存清理
- 导入任务中心

#### Phase 3（复杂链路与稳定性）
- 同步中心（双向/冲突/恢复）
- 第三方契约测试（mock/stub）
- 并发与幂等测试

### 9.4 每个功能目录建议模板
```text
tests/features/<feature_name>/
  README.md                  # 功能范围 + 风险点 + 用例索引
  e2e/
    <main_flow>.spec.js
    <error_flow>.spec.js
  integration/
    test_<persistence>.py
    test_<edge_case>.py
```

### 9.5 可追溯性标准
- 每个用例在注释首行标注：`CASE_ID`、`Feature`、`Risk`
- 失败信息必须包含：
1. 输入条件
2. 期望输出
3. 实际输出
4. 关键信息定位（接口/文件/页面节点）

### 9.6 本批次新增的 10 条高优先级用例
1. `library_browse/e2e/library_open_video_detail.spec.js`
   - 风险看护：模式切换后视频主路径不可用、详情请求参数错。
2. `library_browse/e2e/library_sort_by_score.spec.js`
   - 风险看护：排序 UI 失效、后端排序参数丢失。
3. `global_search/e2e/global_search_local_comic_open_detail.spec.js`
   - 风险看护：本地搜索链路回归、搜索结果跳转错误。
4. `list_management/e2e/list_manage_create_custom_list.spec.js`
   - 风险看护：清单创建入口失效、创建后列表不刷新。
5. `list_management/e2e/comic_detail_add_to_custom_list.spec.js`
   - 风险看护：详情页加清单失败、绑定后列表展示不一致。
6. `trash_management/e2e/comic_move_to_trash_and_restore.spec.js`
   - 风险看护：移入回收站/恢复链路断裂，用户内容丢失风险。
7. `system_config/e2e/system_config_updates_reader_preferences.spec.js`
   - 风险看护：阅读偏好修改不落库、配置 API 契约漂移。
8. `list_management/integration/test_list_create_bind_remove_delete_persistence.py`
   - 风险看护：清单全生命周期与 JSON 落盘不一致。
9. `tag_management/integration/test_tag_add_edit_bind_delete_persistence.py`
   - 风险看护：标签 CRUD/绑定链路回归，标签删除后脏引用。
10. `trash_management/integration/test_video_trash_lifecycle_persistence.py`
   - 风险看护：视频回收站生命周期与落盘状态错乱。

### 9.7 后续全覆盖开发计划（给后续 AI 的执行路线）
1. 漫画导入链路（by_id/by_search/by_list/async task）补齐：
   - E2E 主路径 + Integration 导入任务状态落盘。
2. 漫画详情扩展能力补齐：
   - 下载、检查更新、更新下载、作者订阅。
3. 标签能力补齐到“批量页面操作”：
   - E2E 覆盖批量加/批量移除 + Integration 校验跨源（home/recommendation）一致性。
4. 清单能力补齐到“视频 + 收藏 + 详情筛选”：
   - E2E 覆盖视频清单、收藏清单详情、清单内筛选排序。
5. 回收站能力补齐到“批量操作 + 永久删除”：
   - E2E 覆盖批量恢复/删除，Integration 校验文件资产清理。
6. 视频播放链路补齐：
   - E2E 覆盖详情加载、播放地址获取、预览资源刷新入口。
7. 搜索链路补齐：
   - 本地/预览/远程三分支分别覆盖，远程分支使用 mock/stub。
8. 系统设置与缓存管理补齐：
   - E2E 覆盖缓存面板操作入口，Integration 校验 cache/info 与清理结果。
9. 同步中心补齐：
   - Integration 优先覆盖 pairing、directional/push/pull、冲突策略、幂等。
10. 第三方契约专项：
   - 统一使用 mock/stub，不接真实外网，固定断言入参/出参/错误分支。

---

## 10. 执行命令
### 本地一键
- Windows: `./tests/run_test_gate.ps1`
- Linux/macOS: `bash ./tests/run_test_gate.sh`

### 分开执行
- 集成：`python -m pytest tests/features -m integration`
- E2E：`python tests/tools/run_e2e.py`

---

## 11. 当前状态
- 已完成门禁基础设施、隔离数据工厂、CI 接入，并落地高优先级 10 条新增真实用例（累计 12 条）。
- 现阶段已验证：
1. 集成测试可通过
2. E2E 可通过
3. 测试后服务进程自动回收，不会常驻端口

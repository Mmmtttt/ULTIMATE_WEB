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

### 2.3 首个真实功能用例（library_browse）
- E2E：[`library_open_detail.spec.js`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\e2e\library_open_detail.spec.js)
- Integration：[`test_progress_persistence.py`](D:\code\临时并行开发目录\第二\ULTIMATE_WEB\tests\features\library_browse\integration\test_progress_persistence.py)

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
- 已完成门禁基础设施、隔离数据工厂、首个功能用例、CI 接入。
- 现阶段已验证：
1. 集成测试可通过
2. E2E 可通过
3. 测试后服务进程自动回收，不会常驻端口

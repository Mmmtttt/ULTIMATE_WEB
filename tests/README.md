# 测试门禁说明（Isolation + E2E First）

## 1. 目标
- 本测试体系用于看护当前系统已支持的全量功能，防止代码变更引入回归。
- 门禁在每次 `push`、每次 `pull_request` 自动执行。
- 本地可一键执行同一套门禁。
- 测试以系统测试（E2E）为主，复杂逻辑补充集成测试。
- 测试数据全部由测试框架自动生成，和真实数据隔离，默认不依赖真实第三方服务。

## 2. 总体架构
- `前端系统看护`：用 Playwright 模拟真实用户操作（点击、跳转、输入），断言前端显示 + 与后端交互请求。
- `后端系统看护`：用 Pytest 走真实 HTTP 接口，断言接口响应 + 文件系统持久化行为 +（必要时）第三方交互契约。
- `第三方库`：不直接测第三方实现，只看护后端对第三方调用的入参与出参契约（通过 mock/stub 断言）。

## 3. 数据隔离策略
- 每次测试都在 `tests/.runtime/<profile>` 自动生成独立沙箱数据。
- 不读写 `comic_backend/data` 与生产/开发真实数据。
- 通过环境变量注入：
  - `SERVER_CONFIG_PATH` 指向测试专用 `server_config.json`
  - `THIRD_PARTY_CONFIG_PATH` 指向测试专用 `third_party_config.json`
  - `BACKEND_ENABLE_THIRD_PARTY=0`（默认关闭第三方）
- 测试数据由 `tests/tools/prepare_test_env.py` 自动创建：
  - `meta_data/*.json`
  - 漫画图片/封面等必要媒体文件
  - 默认清单、标签、基础漫画/视频样本

## 4. 目录设计（按功能组织）
```text
tests/
  README.md
  requirements.txt
  pytest.ini
  playwright.config.js
  conftest.py
  run_test_gate.ps1
  run_test_gate.sh
  shared/
    test_constants.py
  tools/
    prepare_test_env.py
    start_backend_for_tests.py
    run_test_gate.py
  features/
    library_browse/
      e2e/
        library_open_detail.spec.js
      integration/
        test_progress_persistence.py
  legacy/
    old_suite/
    docs/
```

规则：
- 同一功能放在同一目录（`tests/features/<feature_name>`）。
- 功能目录下同时包含 `e2e/` 与 `integration/`（按需要增减）。
- 用例文件名使用“行为导向”命名，便于失败后快速定位。

## 5. 本地执行
前置安装：
- Python 依赖：`pip install -r comic_backend/requirements.txt -r tests/requirements.txt`
- 前端依赖：`npm ci --prefix comic_frontend`
- Playwright 浏览器：`npx --prefix comic_frontend playwright install chromium`

一键执行：
- Windows: `./tests/run_test_gate.ps1`
- Linux/macOS: `bash ./tests/run_test_gate.sh`

等价命令：
- 仅集成测试：`python -m pytest tests/features -m integration`
- 仅 E2E：`python tests/tools/run_e2e.py`

## 6. GitHub 门禁
- 工作流文件：`.github/workflows/test-gate.yml`
- 触发条件：
  - `push`（所有分支）
  - `pull_request`
- 注意：该门禁是新增工作流，不会修改或影响现有发布工作流 `release-three-platforms.yml`。

## 7. 用例编写规范
- 优先编写 E2E：从用户行为出发，覆盖真实页面和真实路由流转。
- 集成测试聚焦复杂模块：接口输入/输出、文件写入、异常分支、幂等行为。
- 每个用例至少包含：
  - 输入（用户动作或接口请求）
  - 输出（UI 状态 / API 响应 / 文件系统变化）
  - 失败定位信息（断言信息应直接指向功能行为）
- 禁止直接依赖真实数据目录。
- 允许对第三方调用做 mock/stub 并断言调用参数与返回契约。

## 8. 后续 AI 编写提示词模板
将以下模板直接给后续 AI 使用：

```text
你需要在当前测试架构下继续补充用例，请严格遵守：
1) 所有测试文件只能放在 tests/ 下。
2) 按功能目录组织：tests/features/<feature>/<e2e|integration>/...
3) 禁止使用真实数据；必须使用 tests/tools/prepare_test_env.py 生成的隔离测试数据。
4) E2E 用 Playwright，输入必须是用户操作（点击/输入/切换/跳转）。
5) 集成测试用 Pytest，输入为接口调用，输出必须断言：
   - 响应 JSON
   - 文件系统变化（相关 meta_data JSON）
   - 必要时第三方调用契约（mock/stub）
6) 复用 tests/shared/test_constants.py，避免硬编码分散。
7) 新增用例后，确保以下命令可通过：
   - python -m pytest tests/features -m integration
   - python tests/tools/run_e2e.py
8) 用例命名要体现功能行为，失败后可快速定位。
```

## 9. 后续覆盖计划（功能维度）
Phase 1（优先回归）：
- 导入（漫画/视频）
- 本地库浏览（漫画/视频）
- 详情与在线播放/阅读
- 下载与进度保存
- 清单与收藏
- 标签与搜索

Phase 2（核心管理）：
- 排序与筛选
- 回收站（移入/恢复/永久删除/批量）
- 后端数据同步
- 配置管理与缓存清理

Phase 3（边界与稳定性）：
- 错误恢复与空状态
- 并发与幂等
- 与第三方库交互契约回归

## 10. 当前已落地首个真实用例
- 功能：`library_browse`
- E2E：用户在本地库点击漫画卡片进入详情，断言后端请求链路与详情展示。
- Integration：调用进度保存接口，断言响应与 `comics_database.json` 持久化更新。

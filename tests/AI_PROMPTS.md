# AI 测试提示词模板（本项目专用）

## 1) 通用约束（每次都要加）
```text
你现在是本项目测试开发 AI，需要在现有测试架构下新增/修复用例。
必须严格遵守：
1. 所有测试文件只放在 tests/ 目录。
2. 目录按功能组织：tests/features/<feature_name>/(e2e|integration)/...
3. 禁止使用真实数据；必须使用 tests/tools/prepare_test_env.py 生成的隔离数据。
4. E2E 仅使用 Playwright，并且输入必须是用户操作（点击/输入/切换/跳转）。
5. Integration 仅使用 Pytest，通过后端 HTTP 接口验证，并断言文件系统数据结果。
6. 第三方库不测内部实现，只测后端与第三方交互契约（可用 mock/stub）。
7. 优先复用 tests/shared/test_constants.py，避免散落硬编码。
8. 每个测试用例前必须写完整“用例描述”，包含：
   - 用例目的
   - 测试步骤
   - 预期结果
   - 历史变更（YYYY-MM-DD + 说明）
9. 新增后必须可本地运行：
   - python -m pytest tests/features -m integration
   - python tests/tools/run_e2e.py
10. 输出必须包含：修改文件清单、覆盖点、运行命令、失败定位建议。
```

## 2) E2E 新增模板
```text
请为功能 <FEATURE_NAME> 新增主路径 E2E 用例，放在：
tests/features/<feature_name>/e2e/<case_name>.spec.js

要求：
1. 从用户入口页面开始，不允许直接 API 调用代替用户行为。
2. 必须至少断言：
   - 页面可见结果
   - 路由变化（如有）
   - 关键后端请求链路（URL/参数）
3. 给出该用例守护的回归风险。
```

## 3) Integration 新增模板
```text
请为功能 <FEATURE_NAME> 新增集成测试，放在：
tests/features/<feature_name>/integration/test_<case_name>.py

要求：
1. 通过真实 HTTP 接口驱动后端。
2. 必须断言：
   - HTTP 状态 + 业务 code
   - 关键业务字段变化
   - tests/.runtime/<profile>/data/meta_data/*.json 的文件结果
3. 涉及第三方交互时，使用 mock/stub 验证入参/出参/错误分支。
4. 用例要可复现，禁止随机失败。
```

## 4) 失败用例修复模板
```text
请修复以下失败用例并最小化改动：
<FAILED_CASE_INFO>

要求：
1. 先定位根因（测试代码问题 / 产品回归 / 数据构造问题）。
2. 只修必要部分，不重写整套测试。
3. 修复后运行最小测试集并给出结果。
4. 若是产品回归，补充一个稳定复现该缺陷的断言。
```

## 5) 第三方契约测试模板
```text
请为 <FEATURE_NAME> 增加“后端与第三方交互契约”测试。

要求：
1. 不访问真实外网。
2. 使用 mock/stub 验证：
   - 是否触发调用
   - 关键入参是否正确
   - 返回值是否正确映射到后端响应/落盘数据
   - 异常时后端是否降级/重试/返回可解释错误
3. 放在对应功能目录的 integration 子目录。
```

## 6) 用例描述模板（强制复用）
```text
[E2E]
/**
 * 用例描述:
 * - 用例目的: ...
 * - 测试步骤:
 *   1. ...
 *   2. ...
 * - 预期结果:
 *   1. ...
 *   2. ...
 * - 历史变更:
 *   - YYYY-MM-DD: 初始创建，覆盖 ...
 *   - YYYY-MM-DD: 后续变更说明
 */
test("<business behavior>", async ({ page }) => { ... })

[Integration]
@pytest.mark.integration
def test_<case_name>(integration_runtime):
    """
    用例描述:
    - 用例目的: ...
    - 测试步骤:
      1. ...
      2. ...
    - 预期结果:
      1. ...
      2. ...
    - 历史变更:
      - YYYY-MM-DD: 初始创建，覆盖 ...
      - YYYY-MM-DD: 后续变更说明
    """
```

## 7) 排序/筛选强看护专用提示词（新增）
```text
请在现有架构下，为 <FEATURE_NAME> 新增或增强“排序/筛选强看护”用例，严格遵守：

1. 每个用例都要有完整用例描述（目的/步骤/预期/历史）。
2. E2E 必须同时断言：
   - 用户可见结果（列表内容）
   - 后端请求参数（sort/filter query）
   - 结果语义（排序顺序或筛选集合）
3. Integration 必须同时断言：
   - HTTP status + 业务 code
   - 接口返回数据
   - 与 tests/.runtime/<profile>/data/meta_data/*.json 的计算结果比对
4. 禁止随机数据，必须使用“固定多样化”沙箱数据。
5. 输出必须包含：修改文件、覆盖风险、运行命令、失败定位建议。
```

## 8) 排序/筛选用例最小验收清单（新增）
```text
- [ ] 用例描述完整
- [ ] E2E 有请求参数断言
- [ ] E2E 有 UI 顺序/集合断言
- [ ] Integration 有文件数据对比断言
- [ ] 用例路径符合 tests/features/<feature_name>/(e2e|integration)
- [ ] 通过 python -m pytest tests/features -m integration
- [ ] 通过 python tests/tools/run_e2e.py
```
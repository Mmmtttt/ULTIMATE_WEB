# AI 标准提示词模板（测试体系专用）

## 1) 通用约束提示词（每次都要加）
```text
你现在是本项目的测试开发 AI，需要在现有测试架构下新增/修复用例。
必须严格遵守：
1. 所有测试文件只能放在 tests/ 目录。
2. 必须按功能组织目录：tests/features/<feature_name>/(e2e|integration)/...
3. 禁止使用真实数据；必须使用 tests/tools/prepare_test_env.py 生成的测试沙箱数据。
4. E2E 只允许使用 Playwright，并以用户操作作为输入（点击/输入/切换/跳转）。
5. Integration 只允许使用 Pytest，通过后端 HTTP 接口验证，并断言文件系统持久化结果。
6. 第三方库不直接测试实现，只测试后端与第三方的交互契约（可用 mock/stub）。
7. 代码风格：优先复用 tests/shared/test_constants.py，避免散落硬编码。
8. 新增后必须本地可跑：
   - python -m pytest tests/features -m integration
   - python tests/tools/run_e2e.py
9. 产出必须包含：修改文件清单、用例覆盖点、如何运行、失败如何定位。
```

## 2) 新增“功能主路径”E2E 提示词
```text
请为功能 <FEATURE_NAME> 新增主路径 E2E 用例，放在：
tests/features/<feature_name>/e2e/<case_name>.spec.js

要求：
1. 从用户入口页面开始，不允许直接 API 调用代替用户行为。
2. 必须至少断言：
   - 页面可见结果
   - 路由变化（如有）
   - 与后端关键请求链路（URL/参数）
3. 用例命名体现业务行为，不要泛化命名（如 test1.spec.js）。
4. 给出用例风险描述：它防的回归是什么。
```

## 3) 新增“复杂后端逻辑”Integration 提示词
```text
请为功能 <FEATURE_NAME> 新增集成测试，放在：
tests/features/<feature_name>/integration/test_<case_name>.py

要求：
1. 通过真实 HTTP 接口驱动后端。
2. 必须断言：
   - HTTP 状态 + 业务 code
   - 关键业务字段变化
   - tests/.runtime/<profile>/data/meta_data/*.json 的持久化变化
3. 如果功能涉及第三方交互，使用 mock/stub 断言调用契约（入参/出参/错误分支）。
4. 测试要可复现、无随机失败。
```

## 4) 修复失败用例提示词（回归修复）
```text
请修复以下失败用例并最小化改动：
<FAILED_CASE_INFO>

要求：
1. 先定位失败根因（测试代码问题 / 产品回归 / 数据构造问题）。
2. 只修必要部分，不重写整套用例。
3. 修复后运行对应最小测试集并给出验证结果。
4. 如果是产品回归，补充一个能稳定复现该缺陷的用例断言。
```

## 5) 第三方契约测试提示词
```text
请为 <FEATURE_NAME> 增加“后端与第三方交互契约”测试。

要求：
1. 不直接访问真实第三方网络。
2. 使用 mock/stub 验证：
   - 调用函数/方法是否被触发
   - 关键入参是否正确
   - 关键返回值是否正确映射到后端响应或落盘数据
   - 异常时后端是否降级/重试/返回可解释错误
3. 用例放在功能目录 integration 子目录下。
```

## 6) 同步功能专项提示词
```text
请为数据同步功能新增用例，覆盖：
1. 配对成功/失败
2. 方向同步（push/pull）主路径
3. 冲突策略（同字段不同值）
4. 幂等（重复同步结果不重复写入）
5. 网络异常恢复

要求：
1. E2E 与 Integration 组合覆盖；
2. Integration 必须断言 meta_data 文件变化；
3. 明确每条用例对应的风险场景。
```

## 7) AI 输出格式要求（强制）
```text
请按以下结构输出：
1. 本次覆盖范围（功能点）
2. 修改文件清单（按绝对路径）
3. 每条用例的输入/输出断言
4. 运行命令
5. 已验证结果（通过/失败）
6. 风险与后续建议
```

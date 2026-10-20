# Aria2 for ULTIMATE_WEB

ULTIMATE WEB 的 Aria2 下载引擎插件。协议驱动，宿主侧不含任何平台特判。

| 项 | 值 |
| --- | --- |
| 插件 ID | `download.aria2` |
| 入口 | `./ultimate_provider.py:Aria2Provider` |
| 协议版本 | 1.0 |
| 配置键 | `aria2` |
| 宿主 ID 前缀 | `ARIA2` |
| 运行依赖 | `requests`（宿主已内置，扩展无需额外安装 pip 依赖） |

## 能力（capability）

| capability | 说明 |
| --- | --- |
| `health.query.status` | 返回配置是否就绪（启用即可用，RPC 地址为空时回退本地默认端点） |
| `download.magnet.add` | 调用 `aria2.addUri` 投递磁力/种子直链 |
| `download.task.status` | 调用 `aria2.tellStatus` 并映射为宿主统一结构 |
| `download.task.list` | 合并 `aria2.tellActive` + `tellWaiting` + `tellStopped` |
| `download.task.pause` / `download.task.resume` | `aria2.pause` / `aria2.unpause`（幂等） |
| `download.task.remove` | 活动任务用 `aria2.forceRemove`，已完成任务用 `aria2.removeDownloadResult` |
| `download.task.migrate` | 换保存目录重建任务：删除原任务后用 info hash 磁力重新投递 |

状态映射（Aria2 原生 status → 宿主统一状态）：

- `active` / `waiting` / `paused` 原样映射
- `complete` / `removed` → `complete`
- `error` → `error`

RPC 调用约定：`rpc-secret` 非空时，`token:<secret>` 始终作为 `params` 的第一个元素；响应体带 `error` 字段时抛出 `RuntimeError`（携带 Aria2 的错误信息）。

## 配置

在宿主「第三方配置页 → Aria2」填写：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `enabled` | boolean | 是否启用，默认 `true` |
| `rpc_url` | text | JSON-RPC 地址，如 `http://127.0.0.1:6800/jsonrpc` |
| `secret` | password | `rpc-secret`，按 secret 字段脱敏存储与回显 |
| `dir` | text | 默认下载目录（投递时作为 `options.dir`） |
| `timeout_seconds` | number | 请求超时秒数，默认 30 |
| `auto_import_enabled` / `auto_import_mode` | boolean / text | 下载完成后自动导入本地库（默认 `softlink_ref`） |
| `auto_organize_enabled` | boolean | 下载完成后自动归集番号文件夹 |

## 安装

三种方式效果等价：

1. 在第三方配置页输入本仓库链接（仓库根目录有且只有一个 `ultimate-plugin.json`）：
   `https://github.com/niaonhu001/aria2_for_ultimate`
   指定分支可用 `https://github.com/niaonhu001/aria2_for_ultimate/tree/main`。
2. 打包成 zip 扩展包后在配置页本地安装。
3. 直接把仓库内容放进宿主 `comic_backend/third_party/Aria2/`。

安装后需要重启后端或应用。宿主安装时只校验协议清单、平台声明、路径安全和依赖池覆盖，不识别具体平台名称。

## 开发与测试

把仓库检出到宿主的 `comic_backend/third_party/Aria2`，在项目根目录执行：

```bash
python -m pytest comic_backend/third_party/Aria2/tests -q
```

契约测试全部离线：用桩替身模拟 JSON-RPC 端点，不连接真实 Aria2、不联网。单独克隆本仓库时宿主 `protocol` 包不可用，测试模块会自动跳过。

## 目录结构

```text
aria2_for_ultimate/
├── ultimate-plugin.json          # 协议清单（安装与能力声明的唯一入口）
├── ultimate_provider.py          # Aria2Provider 实现
├── tests/test_aria2_contract.py
├── README.md
└── .gitignore
```

扩展规范见宿主仓库 `comic_backend/third_party/API_INTEGRATION_STANDARD.md`。

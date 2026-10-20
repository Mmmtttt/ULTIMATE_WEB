# LibreTorrent 下载引擎插件（Android 专用）

把磁力/种子链接通过 Android Intent **链式启动**交给已安装的
[LibreTorrent](https://github.com/proninyaroslav/libtorrent) 应用去下载。

本插件只声明 **一个能力**：`download.magnet.add`。任务列表、暂停/继续/删除、目录迁移、
自动归集统统不实现——那些由 LibreTorrent 自己管理。

## 为什么只做一个能力

宿主的「功能 ↔ 能力」映射（`comic_backend/protocol/download_features.py`）会根据插件
真实声明的能力算出一张功能矩阵，界面据此裁剪。本插件只声明投递能力，于是：

| 宿主界面 | 表现 |
| --- | --- |
| 下载任务页 · 投递入口 | 可用（引擎被正常发现） |
| 下载任务页 · 任务列表 | 不轮询本引擎（未声明 `download.task.list`） |
| 任务卡片 · 暂停/继续/删除 | 不出现（未声明对应能力） |
| 自动归集 / 自动导入 | 跳过本引擎（未声明 `download.task.*`） |

也就是说：**插件只声明真实能力，界面自适应，宿主零特判**。插件把某天补上了
`download.task.list` 等能力，界面会自动把对应功能亮起来。

## 安装

按 `comic_backend/third_party/README.md` 的外部插件约定，检出到宿主扫描目录即可：

```bash
cd comic_backend/third_party
git clone <本插件仓库地址> LibreTorrent
```

也可以在第三方插件配置页直接粘贴本仓库链接安装（仓库根目录有且只有一个
`ultimate-plugin.json`）。

装好后**需要在第三方插件配置页显式启用**：按主项目的协议策略，非 `storage.*` 插件
默认 `enabled=false`，这是预期行为。

## Android 打包

manifest 已声明 `packaging.android.enabled: true`，因此 Android `supported` 打包模式会
把本插件打进 APK。

### `<queries>` 与软件包可见性（重要）

Android 11（API 30）起有软件包可见性限制。本插件在 manifest 里用声明式字段描述它需要
交互的对象：

```json
"packaging": {
  "android": {
    "manifest_queries": {
      "intents": [
        { "action": "android.intent.action.VIEW", "schemes": ["magnet"],
          "mime_types": ["application/x-bittorrent"] }
      ],
      "packages": ["org.proninyaroslav.libretorrent"]
    }
  }
}
```

打包脚本（`scripts/package_unified.py` 的 `ensure_android_manifest_network`）会把这些声明
汇总并注入到生成的 `AndroidManifest.xml`：

```xml
<queries>
    <intent>
        <action android:name="android.intent.action.VIEW" />
        <data android:scheme="magnet" />
        <data android:mimeType="application/x-bittorrent" />
    </intent>
    <package android:name="org.proninyaroslav.libretorrent" />
</queries>
```

宿主只搬运声明式数据，不识别具体插件。多轮重复打包结果一致（幂等），插件被移除后旧声明
会被清理。

## 使用

1. 在第三方插件配置页启用 **LibreTorrent** 引擎；
2. 在视频详情页或下载任务页点投递——宿主会调用本插件；
3. 插件拉起 LibreTorrent 的「添加种子」界面；**由你在 LibreTorrent 里确认后**才开始下载。

## 已知限制（都是设计取舍，不是缺陷）

- **单向投递**：拿不到 gid，也查不到进度、不能暂停。所以下载任务页不会显示来自本引擎的
  任务——这是「只声明投递能力」的直接结果。
- **落盘位置由 LibreTorrent 决定**：宿主投递接口里的 `dir`（子文件夹）与 `out`（重命名）
  对本引擎无效。插件会如实回报 `ignored_params` 与 `warning`，不假装已生效。
- **需要用户确认**：LibreTorrent 的投递入口会弹出添加界面，不是无感后台下载。
- **App 必须在前台**：Android 10+ 限制后台应用直接启动 Activity。你从界面点投递时
  App 正处于前台，因此可用；不要在后台任务里调用本插件。
- **非 Android 平台不可用**：桌面端/ Docker 下引擎会显示为「未就绪」，投递时返回可读错误。

## 测试

```bash
python -m pytest tests -q      # 16 个契约用例
```

覆盖 manifest 边界（只声明一个能力、必须有 Android 声明与 queries）、配置归一化、
能力白名单、enabled 自检、非 Android 环境的可读失败、磁力解析优先级、`dir`/`out`
的如实回报，以及**宿主集成**：宿主是否把本引擎识别为「只支持投递」。

## 结构

```text
LibreTorrent/
├── ultimate-plugin.json              # 协议清单（含 Android 打包与 queries 声明）
├── ultimate_provider.py              # Provider：只做投递，平台无关的编排与报错
├── libretorrent_android_runtime.py   # Android 适配层：Intent 启动、上下文获取、安装探测
└── tests/
    └── test_libretorrent_protocol.py
```

Android 适配代码全部留在插件目录内（`API_INTEGRATION_STANDARD.md` §8.2），宿主不出现任何
平台分支。适配模块带插件专属前缀，避免多插件共用 `sys.path` 时发生导入冲突。

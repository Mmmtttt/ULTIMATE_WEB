# 第三方插件目录

当前目录已经从旧的 `adapter_factory / base_adapter` 方案迁移到“协议驱动插件”架构。

如果你要了解当前实现、协议格式、配置方式、调用原理、以及如何新增扩展，请优先阅读：

- [开发者手册](../../开发者文档/开发者手册.md)：当前架构、模块边界、打包和测试规范。
- [API 集成标准](./API_INTEGRATION_STANDARD.md)：新增插件必须遵循的 manifest、Provider、capability、配置和 Android 打包规范。

当前目录中的约定如下：

- 宿主会递归扫描 `comic_backend/third_party/**/ultimate-plugin.json`。
- 每个插件通过 `ultimate-plugin.json` 声明协议元数据。
- 每个插件通过 `plugin.entrypoint` 指向自己的 provider 类。
- 平台差异应优先写进插件自己的 `manifest + provider`，而不是回流到宿主代码里。
- `external_api.py`、`platform_service.py` 仍然保留为兼容壳，但新代码不应再基于它们设计新能力。

一句话概括：

宿主现在面向的是“插件 + capability + manifest 字段”，不包含具体内容源特判。

## 外部插件仓库

下载引擎等迭代独立、体积较大的插件不再随主仓库分发，各自维护独立仓库，按需检出到本目录即可被宿主递归扫描到（宿主只认 `ultimate-plugin.json`，不关心目录名）。

| 插件 | 仓库 | 检出目录 |
| --- | --- | --- |
| Aria2（下载引擎） | https://github.com/niaonhu001/aria2_for_ultimate | `comic_backend/third_party/Aria2/` |
| qBittorrent（下载引擎） | https://github.com/niaonhu001/qbtorrent_for_ultimate | `comic_backend/third_party/qBittorrent/` |
| LibreTorrent（下载引擎，Android 专用） | https://github.com/niaonhu001/libretorrent_for_ultimate | `comic_backend/third_party/LibreTorrent/` |
| JavBus | https://github.com/niaonhu001/javbus_for_ultimate | `comic_backend/third_party/javbus/` |
| NHentai | https://github.com/niaonhu001/nhentai_for_ultimate | `comic_backend/third_party/NHentai/` |
| Hanime1 | https://github.com/niaonhu001/Hanime1_for_ultimate-Public- | `comic_backend/third_party/hanime1/` |

约定：

- 主仓库不跟踪这些目录；本机检出后由 `.git/info/exclude` 忽略，干净克隆不会出现未跟踪噪音。
- 每个插件仓库根目录有且只有一个 `ultimate-plugin.json`，因此也可以在第三方配置页直接粘贴仓库链接安装。
- 插件的协议契约测试随插件仓库维护（`tests/`）；依赖插件源码的宿主测试在目录缺失时自动 skip，干净克隆不会因此变红。


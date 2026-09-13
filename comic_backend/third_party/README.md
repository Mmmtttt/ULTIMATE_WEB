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

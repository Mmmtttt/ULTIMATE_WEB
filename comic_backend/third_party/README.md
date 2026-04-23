# 第三方插件目录

当前目录已经从旧的 `adapter_factory / base_adapter` 方案迁移到“协议驱动插件”架构。

如果你要了解当前实现、协议格式、配置方式、调用原理、以及如何新增平台，请优先阅读：

- [开发者文档/第三方插件框架与协议开发指南.md](../../开发者文档/第三方插件框架与协议开发指南.md)

补充参考：

- [设计文档/第三方库协议说明书.md](../../设计文档/第三方库协议说明书.md)
- [设计文档/第三方平台完全插件化最终计划书.md](../../设计文档/第三方平台完全插件化最终计划书.md)

当前目录中的约定如下：

- 宿主会递归扫描 `comic_backend/third_party/**/ultimate-plugin.json`。
- 每个插件通过 `ultimate-plugin.json` 声明协议元数据。
- 每个插件通过 `plugin.entrypoint` 指向自己的 provider 类。
- 平台差异应优先写进插件自己的 `manifest + provider`，而不是回流到宿主代码里。
- `external_api.py`、`platform_service.py` 仍然保留为兼容壳，但新代码不应再基于它们设计新能力。

一句话概括：

宿主现在面向的是“插件 + capability + manifest 字段”，而不是 “JM / PK / JAVDB / JAVBUS / MISSAV” 这些平台特判。

"""下载引擎的「功能 ↔ 能力」映射。

本模块是下载功能裁剪的**单一事实源**：把产品语义（投递磁力、任务控制、自动
归集……）映射到引擎插件必须声明的协议能力与配置字段。第三方引擎插件只负责
声明能力，具体能提供哪些功能由宿主判定——因此：

- 新增引擎无需改动宿主代码；
- 能力不全的引擎不会在界面上留下「点不通」的按钮；
- 同一个界面里可以正确表达「引擎 A 支持暂停、引擎 B 不支持」。

注意区分两件事，不要混用：

- ``features``：引擎**能做什么**——静态，完全由 manifest 的 capabilities 与
  configuration 字段决定，与当前是否启用、是否配置完整无关。
- ``status``：引擎**现在能不能用**——运行时就绪状态（enabled / 必填凭据）。

界面据此分工：按钮可用性看 features（静态裁剪），可用性提示看 status。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

# 判定「这个插件是不是下载引擎」的能力：宿主就是按它发现下载引擎的。
DOWNLOAD_ENGINE_CAPABILITY = "download.magnet.add"

DOWNLOAD_TASK_LIST_CAPABILITY = "download.task.list"
DOWNLOAD_TASK_MIGRATE_CAPABILITY = "download.task.migrate"

# 功能 -> 必需能力 / 必需配置字段。
# 配置字段是必须的：自动归集/自动导入的开关本身就来自插件配置，
# 引擎没声明该字段时用户根本无从开启，功能也就不存在。
DOWNLOAD_FEATURE_REQUIREMENTS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "submit_magnet": {"capabilities": (DOWNLOAD_ENGINE_CAPABILITY,), "fields": ()},
    # 能否指定落盘目录（下载根目录 + 子文件夹）。判据是引擎是否暴露了 dir 配置项：
    # aria2 / qBittorrent 这类接受目标目录参数的引擎为 True；链式交接给外部客户端
    # （落盘位置由对方决定）的引擎为 False——调用方据此跳过子文件夹，而不是报错。
    "target_dir": {"capabilities": (), "fields": ("dir",)},
    "task_list": {"capabilities": (DOWNLOAD_TASK_LIST_CAPABILITY,), "fields": ()},
    "task_status": {"capabilities": ("download.task.status",), "fields": ()},
    "pause": {"capabilities": ("download.task.pause",), "fields": ()},
    "resume": {"capabilities": ("download.task.resume",), "fields": ()},
    "remove": {"capabilities": ("download.task.remove",), "fields": ()},
    "migrate": {"capabilities": (DOWNLOAD_TASK_MIGRATE_CAPABILITY,), "fields": ()},
    "health": {"capabilities": ("health.query.status",), "fields": ()},
    "auto_import": {
        "capabilities": (DOWNLOAD_TASK_LIST_CAPABILITY,),
        "fields": ("auto_import_enabled",),
    },
    "auto_organize": {
        "capabilities": (DOWNLOAD_TASK_LIST_CAPABILITY, DOWNLOAD_TASK_MIGRATE_CAPABILITY),
        "fields": ("auto_organize_enabled",),
    },
}

# 稳定的输出顺序，便于测试与前端渲染。
DOWNLOAD_FEATURE_ORDER: Tuple[str, ...] = (
    "submit_magnet",
    "target_dir",
    "task_list",
    "task_status",
    "pause",
    "resume",
    "remove",
    "migrate",
    "health",
    "auto_import",
    "auto_organize",
)


def normalize_capability_set(capabilities: Optional[Iterable[Any]]) -> frozenset:
    """把 capabilities 归一成去空白的小写集合，便于大小写无关比较。"""
    normalized = set()
    for item in capabilities or ():
        text = str(item or "").strip().lower()
        if text:
            normalized.add(text)
    return frozenset(normalized)


def normalize_field_set(config_fields: Optional[Iterable[Any]]) -> frozenset:
    """把 manifest 的配置字段名归一成小写集合。"""
    return normalize_capability_set(config_fields)


def manifest_config_field_keys(manifest: Any) -> list:
    """取 manifest 声明的配置字段名。

    用鸭子类型访问 ``list_configuration_fields()``，避免本模块反向依赖
    protocol.base，保持纯逻辑、可独立测试。
    """
    try:
        fields = manifest.list_configuration_fields()
    except Exception:
        return []
    keys = []
    for field in fields or ():
        key = str((field or {}).get("key") or "").strip()
        if key:
            keys.append(key)
    return keys


def _requirement_met(
    requirement: Mapping[str, Tuple[str, ...]],
    capabilities: frozenset,
    config_fields: frozenset,
) -> bool:
    for capability in requirement.get("capabilities", ()):
        if str(capability or "").strip().lower() not in capabilities:
            return False
    for field in requirement.get("fields", ()):
        if str(field or "").strip().lower() not in config_fields:
            return False
    return True


def resolve_download_features(
    capabilities: Optional[Iterable[Any]],
    config_fields: Optional[Iterable[Any]] = None,
) -> Dict[str, bool]:
    """按引擎声明的能力与配置字段，算出它能提供的功能。

    返回的字典包含全部已知功能（缺失能力即为 False），顺序与
    :data:`DOWNLOAD_FEATURE_ORDER` 一致，便于前端与测试稳定消费。
    """
    capability_set = normalize_capability_set(capabilities)
    field_set = normalize_field_set(config_fields)
    return {
        feature: _requirement_met(
            DOWNLOAD_FEATURE_REQUIREMENTS[feature], capability_set, field_set
        )
        for feature in DOWNLOAD_FEATURE_ORDER
    }


def aggregate_download_features(
    per_engine_features: Optional[Iterable[Optional[Mapping[str, Any]]]],
) -> Dict[str, bool]:
    """汇总多个引擎的功能矩阵：只要**任意**引擎支持，该功能整体就算可用。

    用于回答「当前环境下整体能做什么」，例如决定是否展示自动归集入口。
    单个引擎的裁剪仍应以该引擎自己的 features 为准。
    """
    aggregate = {feature: False for feature in DOWNLOAD_FEATURE_ORDER}
    for features in per_engine_features or ():
        if not isinstance(features, Mapping):
            continue
        for feature in DOWNLOAD_FEATURE_ORDER:
            if features.get(feature) is True:
                aggregate[feature] = True
    return aggregate


def is_download_engine(capabilities: Optional[Iterable[Any]]) -> bool:
    """该插件能否作为下载引擎被宿主发现。"""
    return DOWNLOAD_ENGINE_CAPABILITY.lower() in normalize_capability_set(capabilities)


def unsupported_download_features(features: Optional[Mapping[str, Any]]) -> list:
    """列出该引擎**不支持**的功能名（按稳定顺序）。"""
    if not isinstance(features, Mapping):
        return []
    return [
        feature
        for feature in DOWNLOAD_FEATURE_ORDER
        if features.get(feature) is not True
    ]

"""LibreTorrent 链式启动的 Android 适配层。

职责：把一个磁力/种子链接通过 Android Intent 交给已安装的 LibreTorrent 处理。

平台边界
--------
本模块**只要被导入**就必须是安全的：`java` 模块的导入被推迟到函数内部，
因此桌面端（Windows / Linux / Docker）import 本模块不会失败，只有真正调用
投递时才会返回明确原因。Android 适配代码全部留在插件目录内，宿主不出现任何
平台分支（API_INTEGRATION_STANDARD.md §8.2）。

与 LibreTorrent 的契约
----------------------
依据 LibreTorrent 的 ``AddTorrentActivity`` 实现，它接受两种入口：

1. ``Intent.ACTION_VIEW`` 且 ``intent.getData()`` 为 magnet / http / 种子文件 URI
   （隐式 Intent，由 IntentFilter 解析）；
2. 显式组件 + ``intent.getParcelableExtra("uri")``。

两种形式都由 LibreTorrent 自己弹出「添加种子」界面，**由用户确认后才开始下载**。
因此这里是**单向投递**：拿不到 gid，也查不到进度——这也正是本插件只声明
``download.magnet.add`` 一个能力的原因。

权限与可见性
------------
Android 11（API 30）起有软件包可见性限制。本插件优先使用
``Intent.setPackage()`` 的显式形式；若被系统拦截，会抛出可读错误并提示在打包时
声明 ``<queries>``（插件 manifest 的 ``packaging.android.manifest_queries`` 会被
打包脚本注入到 AndroidManifest.xml）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_PACKAGE_NAME = "org.proninyaroslav.libretorrent"

# LibreTorrent 的 "uri" extra 键名（见其 AddTorrentActivity.TAG_URI）
URI_EXTRA_KEY = "uri"


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _java_classes() -> Optional[Dict[str, Any]]:
    """惰性取 Java 类；非 Android 环境返回 None。

    单独抽出便于测试时 monkeypatch，避免测试进程真的去碰 `java` 模块。
    """
    try:
        from java import jclass  # type: ignore
    except Exception:
        return None
    try:
        return {
            "Python": jclass("com.chaquo.python.Python"),
            "Intent": jclass("android.content.Intent"),
            "Uri": jclass("android.net.Uri"),
            "ActivityNotFound": jclass("android.content.ActivityNotFoundException"),
        }
    except Exception:
        return None


def context_probe() -> tuple:
    """探测 Android 上下文，返回 ``(context, 诊断信息)``。

    ``context`` 为 None 时，诊断信息说明**具体卡在哪一步**。这很重要：在真机上
    没有 adb 时，这条信息会随投递失败的错误提示显示出来，直接指出是「不是 Android
    端」「Python 未启动」「getPlatform() 为 null」还是「平台不是 AndroidPlatform」，
    不必再靠猜。
    """
    try:
        from java import jclass  # type: ignore
    except Exception as exc:
        return None, f"当前进程没有 java 模块（{type(exc).__name__}），不是 Chaquopy 运行环境"
    try:
        python_cls = jclass("com.chaquo.python.Python")
    except Exception as exc:
        return None, f"无法加载 com.chaquo.python.Python：{exc}"
    try:
        if not python_cls.isStarted():
            return None, "Chaquopy Python 尚未启动（Python.isStarted() 为 false）"
    except Exception as exc:
        return None, f"调用 Python.isStarted() 失败：{exc}"
    try:
        platform = python_cls.getPlatform()
    except Exception as exc:
        return None, f"调用 Python.getPlatform() 失败：{exc}"
    if platform is None:
        return None, "Python.getPlatform() 返回 null（Python 未通过 start() 启动）"
    try:
        application = platform.getApplication()
    except Exception as exc:
        platform_name = ""
        try:
            platform_name = str(platform.getClass().getName())
        except Exception:
            platform_name = "<未知平台>"
        return None, (
            f"平台 {platform_name} 没有 getApplication()"
            "（通常意味着 Python 是被 GenericPlatform 启动的，而不是 AndroidPlatform）："
            f"{exc}"
        )
    if application is None:
        return None, "AndroidPlatform.getApplication() 返回 null"
    return application, ""


def has_java_bridge() -> bool:
    """当前进程是否有 Chaquopy 的 Java 桥。

    这是「是不是 Android 端」的可靠判据：桌面端没有 `java` 模块，Android 端有。
    与 :func:`android_context` 的区别很重要——后者会因为运行时探测失败而返回 None，
    那并不代表平台不支持，因此不能用来判定「不可用」。
    """
    return _java_classes() is not None


def android_context() -> Any:
    """返回 Android Application 上下文；非 Android 环境或探测失败返回 None。

    依据 Chaquopy Java API：``Python.getPlatform()`` 返回启动 Python 时使用的
    Platform，``AndroidPlatform.getApplication()`` 返回 Application 上下文。
    需要知道**为什么**拿不到时用 :func:`context_probe`。
    """
    return context_probe()[0]


def unavailable_reason() -> str:
    """当前环境无法链式启动时的可读原因（含具体卡在哪一步）。"""
    context, detail = context_probe()
    if context is not None:
        return ""
    if not has_java_bridge():
        return "当前运行环境没有 Chaquopy Java 桥（LibreTorrent 引擎只能在 Android 端使用）"
    return f"无法获取 Android Application 上下文：{detail}"


def is_package_installed(package_name: str) -> Optional[bool]:
    """尽力探测目标包是否已安装。

    返回 ``True`` 表示确认已安装；``False`` 表示**未检测到**；``None`` 表示无法判断。
    注意 Android 11+ 的软件包可见性过滤会让已安装的包也查不到，因此调用方不应把
    ``False`` 当作「一定没装」——这也是返回值设计成三态的原因。
    """
    name = _as_text(package_name) or DEFAULT_PACKAGE_NAME
    context = android_context()
    if context is None:
        return None
    try:
        info = context.getPackageManager().getPackageInfo(name, 0)
    except Exception:
        return False
    return info is not None


def _dispatch(context: Any, classes: Dict[str, Any], uri: str, package_name: str) -> None:
    """按「先精确、后宽松」的顺序尝试投递。全部失败则抛最后一个异常。"""
    Intent = classes["Intent"]
    uri_obj = classes["Uri"].parse(uri)

    builder = Intent(Intent.ACTION_VIEW)
    builder.setData(uri_obj)
    builder.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    last_error: Optional[Exception] = None

    # 1) 指定包名：最精确，避免把链接交给其它 BT 客户端，也不需要 <queries> 之外的解析。
    if package_name:
        try:
            targeted = Intent(Intent.ACTION_VIEW)
            targeted.setData(uri_obj)
            targeted.setPackage(package_name)
            targeted.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(targeted)
            return
        except Exception as exc:  # ActivityNotFoundException / SecurityException 等
            last_error = exc

    # 2) 不指定包名：交给系统按 IntentFilter 解析（可能弹出选择器）。
    try:
        context.startActivity(builder)
        return
    except Exception as exc:
        last_error = exc

    raise RuntimeError(
        "无法启动 LibreTorrent 处理该链接"
        f"（目标包 {package_name or DEFAULT_PACKAGE_NAME}）。"
        "请确认已安装 LibreTorrent；"
        "若已安装仍失败，打包时需在 AndroidManifest 声明 <queries> "
        "以允许 Android 11+ 的软件包可见性。"
        f" 最后一次错误：{last_error}"
    )


def start_download(uri: str, package_name: str = DEFAULT_PACKAGE_NAME) -> Dict[str, Any]:
    """把链接交给 LibreTorrent。成功返回投递结果，失败抛 RuntimeError。"""
    target = _as_text(uri)
    if not target:
        raise ValueError("缺少磁力链接")
    if not (target.startswith("magnet:") or target.startswith("http://") or target.startswith("https://")):
        raise ValueError(f"不支持的链接类型：{target[:32]}")

    context, detail = context_probe()
    if context is None:
        raise RuntimeError(f"LibreTorrent 链式启动不可用：{detail or unavailable_reason()}")
    classes = _java_classes()
    if not classes:
        raise RuntimeError(unavailable_reason())

    package = _as_text(package_name) or DEFAULT_PACKAGE_NAME
    _dispatch(context, classes, target, package)

    installed = is_package_installed(package)
    return {
        "added": True,
        "engine": package,
        # 单向投递：LibreTorrent 自己管理任务，拿不到 gid
        "gid": None,
        "handoff": True,
        "package_installed": installed,
    }

# JMComic Android Demo

这是一个用于验证 `jmcomic + curl_cffi` 能否被直接打进 Android APK 的最小工程。

它与主项目现有的 `comic_backend` / `comic_frontend` 完全独立，不修改现有架构。

## 技术方案

- Android 原生 Java UI
- Chaquopy 17.0.0
- CPython 3.13
- Android `minSdk 24`
- 仅支持 `arm64-v8a`
- `jmcomic`
- `curl-cffi==0.16.3`
- `cffi==1.17.1`
- `Pillow==11.0.0`
- `pycryptodome==3.21.0`
- `PyYAML==6.0.2`

之所以固定 ARM64，是因为当前 `curl_cffi` 的 Android 官方 wheel 面向 `android_24_arm64_v8a`。这样可以避免 x86_64 模拟器造成的 ABI 假故障。

## Demo 功能

1. 启动 App。
2. 点击“环境自检”，验证 Python、`jmcomic`、`curl_cffi` 是否能够在 APK 内正常 import。
3. 输入 JM 本子 ID。
4. 点击“下载指定 ID 漫画”。
5. Python 端调用 `jmcomic.download_album(id, option)`。
6. 下载文件保存到 App 专属外部目录：

```text
/storage/emulated/0/Android/data/com.mmtttt.jmcomicdemo/files/Pictures/JMComic/
```

这个目录不需要申请传统外部存储权限。

## Android Studio 构建

建议使用带 Android SDK 36 的新版 Android Studio，并确保本机安装 Python 3.13。

直接用 Android Studio 打开：

```text
android_jmcomic_demo/
```

然后选择真实 ARM64 Android 手机运行。

> 不建议第一步使用 x86_64 Android Emulator，因为当前 Demo 只打包 `arm64-v8a`。

命令行也可以：

```bash
gradle :app:assembleDebug
```

生成位置通常为：

```text
app/build/outputs/apk/debug/app-debug.apk
```

## 为什么不直接打包 ULTIMATE_WEB 全部后端

主项目 `comic_backend/requirements.txt` 还包含 Flask、lxml、cryptography、py7zr、rarfile 等依赖。直接全量迁移会一次引入太多 native/平台兼容变量。

这个 Demo 先验证最关键链路：

```text
Android APK
  -> Chaquopy
  -> CPython 3.13
  -> jmcomic
  -> curl_cffi Android native wheel
  -> 网络请求 / 图片下载
```

如果这条链能跑通，再逐步迁移 ULTIMATE_WEB 的业务层会更稳。

## 已知限制

- 仅 ARM64。
- 下载运行在 App 进程内的后台线程，不是正式版 WorkManager/Foreground Service；切后台或系统杀进程时任务可能中断。
- 输出目录是 App 专属目录，正式版若要让用户在系统“下载”目录直接管理文件，应接 Storage Access Framework / MediaStore。
- Demo 只验证单个 JM ID 下载，不包含 ULTIMATE_WEB 的 Web UI、数据库、搜索、任务队列等功能。
- 能成功 assemble APK 只能证明依赖能打包；最终仍需要真实 Android ARM64 设备验证 `curl_cffi` 的 native `.so` 加载和网络行为。

## 关键文件

```text
app/build.gradle
    Chaquopy、Python 版本、ABI 和第三方依赖

app/src/main/python/jm_bridge.py
    Python -> jmcomic 下载逻辑

app/src/main/java/com/mmtttt/jmcomicdemo/MainActivity.java
    最小 Android UI / Java -> Python 调用
```

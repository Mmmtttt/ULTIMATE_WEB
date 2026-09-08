# Android third-party plugin packaging

Android packages use a manifest-driven plugin selection flow. The main project
provides the packaging mechanism, while each third-party plugin declares whether
it is safe to include on Android and which platform-specific dependencies it
needs.

## Main project contract

Set the Android packager to supported-plugin mode:

```json
{
  "android_backend_enable_third_party": true,
  "android_backend_third_party_mode": "supported"
}
```

In this mode, the packager scans `comic_backend/third_party` and only copies
plugins whose `ultimate-plugin.json` contains:

```json
{
  "packaging": {
    "android": {
      "enabled": true
    }
  }
}
```

The generated protocol snapshot is filtered to the same plugin set, so Android
does not expose metadata-only placeholders for plugins that were not packaged.

## Plugin contract

Each Android-ready plugin should keep all platform-specific choices inside its
own directory.

```json
{
  "packaging": {
    "android": {
      "enabled": true,
      "pip_options": ["--no-deps"],
      "pip_requirements": [
        "requests>=2.31.0"
      ]
    }
  }
}
```

If Android needs safer defaults, add a small plugin-local adapter such as
`android_runtime.py`, then call it from the plugin provider when building its
runtime option. Avoid scattering Android checks through business logic.

## Rollback

To disable all Android third-party runtime plugins, set:

```json
{
  "android_backend_enable_third_party": false
}
```

To return to explicit allow-list packaging, set:

```json
{
  "android_backend_third_party_mode": "selected",
  "android_backend_plugins": ["comic.jmcomic"]
}
```

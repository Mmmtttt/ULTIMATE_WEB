# Android Signing Keystore

This directory stores the reusable Android signing key used by the unified packaging script.

- File: `ultimate-release.keystore`
- Default alias: `ultimate`
- Default password fields are configured in `build/packagers.json`.

Why this exists:

- Android in-place upgrades require the **same package id + same signing certificate**.
- CI runners are ephemeral. If key material is generated per run, users will get `签名不一致` and cannot upgrade directly.

You can rotate to your own key later by updating these fields in `build/packagers.json`:

- `android_signing_keystore`
- `android_signing_key_alias`
- `android_signing_store_password`
- `android_signing_key_password`
- `android_signing_dname`

Important:

- Keep a secure backup of your signing key.
- If you lose or change the key, already-installed APKs signed by the old key cannot be upgraded in-place.

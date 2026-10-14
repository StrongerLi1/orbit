# Orbit Android

Native Kotlin/Jetpack Compose client for the existing Orbit server.

## Build prerequisites

- JDK 17
- Android SDK Platform 36
- Android SDK Build Tools 35.0.0

## Build and test

```bash
export JAVA_HOME=/path/to/jdk-17-or-newer
export ANDROID_HOME=/path/to/android-sdk
./gradlew testDebugUnitTest lintDebug assembleDebug
```

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. The app connects to `https://shawnstronger.cloud`; an authenticated administrator can replace that origin from the app's Admin screen.

The app is native Compose. PlayCaptcha and the authenticated Hermes Dashboard are the only WebView surfaces. A custom server must be an HTTPS origin; switching it clears the local session and requires a normal login against the new server.

Writings, the film diary, and the shared library are native screens backed by the existing Orbit APIs. Film exposure forms request foreground location only after the user taps “获取当前位置”; the resolved address remains editable, and failed or denied location falls back to manual entry without storing coordinates.

Shared-library uploads use Android's document picker and stream the selected file to the server. Downloads use the system “Save as” picker and write directly to the selected destination, so the app does not request broad storage permission or keep a private duplicate. Public book links can be copied or sent through Android's share sheet.

See `MANUAL_CHECKLIST.md` for backend-connected and device-only checks that cannot be proved by local JVM tests.

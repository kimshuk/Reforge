---
title: Verify backend configuration in both iOS bundle artifacts
date: 2026-09-28
area: ios
status: verified
---

## Problem

The app and Share Extension must receive the same `NOTEAPP_BACKEND_BASE_URL`. Xcode build settings showed `INFOPLIST_KEY_NOTEAPP_BACKEND_BASE_URL`, but the generated app `Info.plist` did not contain the custom key. The extension used an explicit plist and did contain it.

## Mistake and why it failed

Checking `xcodebuild -showBuildSettings` looked sufficient because both settings expanded to the injected URL. In this project, that did not prove the custom key was emitted into a target that used `GENERATE_INFOPLIST_FILE = YES`. `AppConfig.default` reads `Bundle.main`, so the deployed app would still fail even though the build settings appeared correct.

## Verified approach

Both targets now use explicit plist entries that expand `$(NOTEAPP_BACKEND_BASE_URL)`:

- `ios/App/Info.plist`
- `ios/ShareExtension/Info.plist`

After a Release simulator build with `NOTEAPP_BACKEND_BASE_URL=https://example.invalid`, `plutil -p` confirmed the same value in both built bundle plists under `NoteApp.app` and `NoteApp.app/PlugIns/ShareExtension.appex`.

## Prevention

For bundle-read configuration, verify the built artifacts rather than only the Xcode setting graph. Check both the containing app and every extension after Debug and Release configuration changes.

---
title: Preserve App Group entitlements in iOS simulator builds
date: 2026-10-01
area: ios
status: verified
---

## Problem

Reforge compiled and installed in an iOS simulator but exited during startup at `ios/App/NoteApp.swift:37`. Startup initializes shared storage through `ios/Core/Storage/SharedModelContainer.swift`, which requires `group.com.andrewkim.noteapp`.

## Mistake and why it failed

Building with `CODE_SIGNING_ALLOWED=NO` looked reasonable because simulator builds do not require device provisioning. It also suppressed the simulator entitlement packaging needed by the App Group. The startup console reported `SharedModelContainerError error 0`, corresponding to `appGroupUnavailable`.

A second misleading check was expecting `codesign -d --entitlements :-` to show the App Group on the simulator bundle. In the corrected build, that command returned an empty dictionary: Xcode embedded the simulated entitlements in Mach-O sections instead.

## Verified approach

Build Debug with simulator signing enabled and an ad hoc identity:

```sh
xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp \
  -configuration Debug -destination 'generic/platform=iOS Simulator' \
  NOTEAPP_BACKEND_BASE_URL=http://localhost:3000 \
  CODE_SIGNING_ALLOWED=YES CODE_SIGN_IDENTITY=- build
```

The corrected build succeeded. Both generated `*-Simulated.xcent` files contained the shared App Group. `otool -s __TEXT __entitlements` confirmed entitlement sections in the app and extension executables. After reinstalling in the same simulator, Reforge remained running and displayed Home.

## Prevention

Keep simulator signing enabled for this project. Verify both targets' simulated entitlement files and built executable sections, then confirm the installed app stays running. Do not treat compilation or a successful `simctl launch` response alone as proof of successful startup. Physical-device signature checks and simulator entitlement checks use different artifacts.

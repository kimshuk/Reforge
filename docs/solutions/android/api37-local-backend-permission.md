---
title: Verify local backend access with the Android app UID on API 37
date: 2026-10-10
area: android
status: verified
---

## Problem

The API 37 Debug app showed `Analysis failed on the backend. Please try again.`
when submitting a YouTube URL. The local backend was healthy, but no corresponding
analysis request reached it.

## Mistake and why it failed

A successful `/health` request from the host or `adb shell` did not establish that
the app could connect. Android 17 applies local network restrictions per app UID.
The app targets SDK 37 and had only the `INTERNET` permission. A debugger stopped
at `HomeViewModelKt.analysisErrorMessage` and identified `AnalyzeApiError.TimedOut`;
`HomeViewModel.kt` maps that timeout to the same message used for backend analysis
errors. The generic message therefore hid the connection failure.

## Verified approach

- Compare the same port under the shell UID and app UID:
  `adb shell nc -z -w 3 10.0.2.2 3000` succeeded while
  `adb shell run-as com.andrewkim.reforge /system/bin/nc -z -w 3 10.0.2.2 3000`
  timed out before the fix. AppOps also showed UID-level local network denial.
- Declare `android.permission.ACCESS_LOCAL_NETWORK` in
  `android/app/src/debug/AndroidManifest.xml`, then rebuild and install Debug.
- Grant the development permission with
  `adb shell pm grant com.andrewkim.reforge android.permission.ACCESS_LOCAL_NETWORK`.
  This development workflow requires no new in-app permission prompt.
- The installed app reported `granted=true`, the app-UID port check succeeded,
  and an actual Home submission reached `/analyze`, fetched the transcript, and
  entered clipping extraction. This verifies the connection fix. That particular
  analysis then failed independently with `LLM_CLIPPINGS_INVALID_JSON` because a
  joined contextual explanation exceeded 420 characters; end-to-end analysis
  success was not claimed.
- Merged manifest inspection confirmed that Debug declares the permission and
  Release does not. The Android unit suite passed 84 tests, Lint passed, and the
  Debug APK built successfully.

## Prevention

When testing local development backends on Android 17, verify the installed app's
permission and UID-level connectivity instead of relying on shell health alone.
Reapply the development grant after a clean install or permission revocation.
Read the final analysis status and error code separately from HTTP 200 and network
connectivity. Keep development-only access in the Debug manifest.

Reference: https://developer.android.com/privacy-and-security/local-network-permission

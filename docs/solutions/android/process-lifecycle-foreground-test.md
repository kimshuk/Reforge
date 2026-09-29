---
title: Wait for process background before testing a new foreground event
date: 2026-09-29
area: android
status: verified
---

## Problem

An instrumented test of app-level Trash cleanup intermittently saw no `ProcessLifecycleOwner` foreground callback even though it launched a fresh `MainActivity`.

## Mistake and why it failed

The test treated the previous `ActivityScenario.close()` as an immediate process background transition. Process lifecycle stop is delayed to avoid a false background event during short Activity changes. The next test could launch before `ON_STOP`, leaving the process already started and producing no new `ON_START`. The first run of `ShareLifecycleTest.purgeFailureStaysSilentAndRetriesAtNextForeground` timed out waiting for its initial purge call.

## Verified approach

`android/app/src/androidTest/java/com/andrewkim/reforge/integration/ShareLifecycleTest.kt` waits until the process lifecycle is below `STARTED` before a test launch that must produce a new foreground event. It also waits after finishing a cold share before reopening the database and launching again. The focused suite passed 3/3 and the complete API 37 connected suite passed 54/54 after this change.

## Prevention

When an instrumented test asserts app-level foreground behavior, synchronize on the process lifecycle state between test activities. Closing an Activity only proves its own lifecycle ended; it does not prove the process emitted `ON_STOP`.

---
title: Refresh an open Trash screen after foreground activation
date: 2026-09-28
area: ios
status: verified
---

## Problem

An open Trash destination could keep showing expired or externally restored notes after the app returned from the background. The app-level purge changed storage, but the screen's `@StateObject` kept its previous rows.

## Mistake and why it failed

`ios/Features/Notes/TrashView.swift` loaded rows only in `onAppear`, using the `now` value captured when the destination was created. Returning to the foreground does not necessarily make the destination appear again, and that captured time becomes stale. Storage cleanup in another layer does not automatically refresh `TrashViewModel.notes`.

## Verified approach

Keep the supplied `now` for the initial appearance. Observe `scenePhase` in `TrashView` and call `viewModel.load(now: Date())` when it becomes `.active`. `TrashViewModel.load(now:)` purges at the activation-time 30-day cutoff and then fetches current rows; on failure it retains the previous rows and sets inline `errorMessage`.

`NotesViewModelTests.testTrashForegroundRefreshUsesCurrentCutoff()` hosts the real SwiftUI view, moves the injected scene phase from background to active, and verifies that a note expiring during that interval is purged. It failed at `NotesViewModelTests.swift:137` before the lifecycle hook and passed afterward. The full iOS suite and Debug simulator build also passed.

## Prevention

For screens backed by mutable shared storage, test foreground activation while the destination remains open. Use the activation time for age-based cleanup and reload visible rows after external changes.

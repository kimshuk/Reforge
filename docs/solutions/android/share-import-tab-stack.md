---
title: Keep transient share routes out of saved tab stacks
date: 2026-09-29
area: android
status: verified
---

## Problem

After a successful Android share opened a note detail, selecting Home could reopen the old `share-import` screen. The completed import had already been acknowledged, so the restored screen could be empty.

## Mistake and why it failed

`AppCoordinator.completeShare` originally switched directly from `share-import` to the My Notes graph using the tab navigation options `popUpTo(...){ saveState = true }` and `restoreState = true`. Navigation Compose saved the transient import destination with the tab stack. A later Home selection restored that destination instead of Home.

## Verified approach

`android/app/src/main/java/com/andrewkim/reforge/navigation/AppCoordinator.kt` pops `share-import` before selecting My Notes and replacing its detail route. The same transient-route removal applies to a general launcher intent received during import. `ShareNavigationTest.acknowledgedRecreationDoesNotReopenDetail` and `generalLaunchWhileImportingReturnsHomeWithoutRestoringShare` verify both paths on the API 37 emulator; the focused suite passed 13/13.

## Prevention

Keep external-flow destinations outside the saved tab stacks. Before using tab navigation with `saveState`, remove the transient route; test a later return to each tab, not only the immediate destination.

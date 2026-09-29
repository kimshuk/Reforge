---
title: Reconcile restored share navigation with nonpersisted import state
date: 2026-09-29
area: android
status: verified
---

## Problem

After process-style recreation, Navigation Compose restored `share-import`, while a new `ShareImportViewModel` restored `Idle`. The initial implementation did not persist Loading, Error, or AwaitingRestore. The app therefore displayed an empty share screen and could not safely replay the neutralized launch Intent. A later review found another gap: an Activity Bundle saved before stop could not include a completion published after stop, even though Room had committed the note.

## Mistake and why it failed

Task 5 initially treated a restored NavController route as sufficient evidence that the corresponding import UI state existed. Rotation usually retained the ViewModel, so earlier lifecycle tests passed and hid the split between route restoration and ViewModel restoration. A separate general-launch case showed that `cancelImport()` intentionally leaves `Completed` intact; using it to abandon a queued completion let the collector open an old detail after Home was selected.

The first completion-recovery tests saved the handle after completion or retained the original ViewModel. Both approaches hid the earlier OS snapshot: changing SavedStateHandle after stop does not update a Bundle that Android already captured.

Moving recovery into the state collector introduced a separate reentrancy boundary. After ordinary recreation retained Loading or AwaitingRestore, the recovery flag remained armed. A user's Back or Cancel published Finished before Compose observed the new navigation entry, so the collector could invoke termination a second time and pop the original detail.

## Verified approach

`android/app/src/main/java/com/andrewkim/reforge/sharing/ShareImportViewModel.kt` now saves the pending source key synchronously before ingestion. A fresh ViewModel queries Room through `ShareIngesting.findCommittedNoteId`; an active committed row restores `Completed`, while absent or trashed rows finish without network or mutation. The existing Loading presentation covers that lookup, so no new screen or schema is required.

`android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt` observes the reconciliation result after navigation is bound. A stale share route with `Idle`/`Finished` exits through the existing Back behavior, preserving warm origin or finishing a cold external task without replaying ingestion. `ShareImportViewModel.abandonForGeneralLaunch()` explicitly finishes a pending `Completed` without deleting its saved note or changing `cancelImport()` semantics.

`ShareNavigationTest.bundleCapturedBeforeCommitRecoversCompletedNoteInFreshViewModel` parcels the handle before the Room commit. `activityRestoresPreCommitBundleWithFreshViewModelAndOpensCommittedDetailOnce` freezes the earlier saved-state provider Bundle, clears the Activity ViewModelStore, and recreates the Activity. It verifies a different ViewModel instance, the committed note detail, one transcript request, and one row. The focused API 37 ShareNavigationTest suite passed 19/19. Existing tests still cover incomplete loading, errors, restore prompts, and a general launch abandoning queued completion.

`MainActivity.finishShare()` now disarms recovery before calling the coordinator, and both user exits plus restored unfinished exits use it. The added `recreatedWarmLoadingBackReturnsOnceToOriginDetail` and `recreatedWarmRestoreCancelReturnsOnceToOriginDetailWithoutMutation` verify the original note ID, a live Activity, unchanged rows, and no late second exit. The expanded navigation suite passed 21/21 and ShareImportViewModelTest passed 13/13.

## Prevention

For every restored navigation route, check which state existed when Android saved its Bundle. Test process-style ViewModel replacement separately from rotation, capture the Bundle before completion, and verify against durable data without replaying network. Also test completion queued while lifecycle collection is stopped before handling a new launcher Intent. When recovery observes terminal states, disarm it before an explicit user action publishes the same state; test Back and Cancel after recreation from a nontrivial origin stack.

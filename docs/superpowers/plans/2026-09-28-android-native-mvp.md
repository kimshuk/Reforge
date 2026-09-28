# Android Native MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube 공유로 Reforge를 연 뒤 자막이 있는 로컬 노트를 안전하게 저장·열람하고, 사용자가 명시적으로 분석을 시작할 수 있는 Android 네이티브 MVP를 만든다.

**Architecture:** `android/`의 단일 Activity Compose 앱이 일반 실행과 `ACTION_SEND`를 한 navigation graph로 처리한다. Room repository가 iOS와 동등한 active / trashed / absent 정책을 원자적으로 보장하고, coordinator와 ViewModel이 transcript 수집·취소·늦은 응답 차단을 담당한다. 기존 FastAPI transcript와 SSE analysis 계약을 재사용하며 UI는 기본 Material 3에 한정한다.

**Tech Stack:** Android Gradle Plugin 9.4.0 built-in Kotlin 2.2.10, Kotlin Compose·Serialization compiler plugins 2.2.10, Gradle 9.6.0, JDK 17, compile/target SDK 37, min SDK 26, Compose BOM 2026.09.00, Navigation Compose 2.10.2, Lifecycle 2.11.0, Room 2.8.5 + KSP 2.3.10, Retrofit 3.0.0, OkHttp 5.3.0, Coil 3.6.3, Kotlin Coroutines, Kotlin Serialization, JUnit, kotlinx-coroutines-test, MockWebServer, Room in-memory tests, Compose UI tests

**Spec:** `docs/superpowers/specs/2026-09-28-android-native-mvp-design.md`

## Global Constraints

- application ID와 namespace는 `com.andrewkim.reforge`다.
- Android 8.0(API 26) 이상을 지원하고 compile/target SDK 37, JDK 17을 사용한다.
- 공유 수신은 `ACTION_SEND` + `text/plain`만 선언하며 `MainActivity`는 `android:exported="true"`, `android:launchMode="singleTask"`다.
- 공유는 앱을 즉시 열지만 transcript 저장만 수행한다. LLM 분석은 노트 상세의 `Analyze` 탭에서만 시작한다.
- active 중복은 네트워크 없이 기존 상세를 열고 기존 note 필드를 바꾸지 않는다.
- trashed 중복은 `This video is in Trash. Restore it?`와 `Cancel / Restore`만 제공한다. 새 노트 생성 선택지는 없다.
- 취소·오류에는 부분 note가 없어야 한다. Room transaction commit 뒤 관찰된 취소는 완결된 note를 삭제하지 않는다.
- 노트는 Android 기기 로컬 Room DB에만 저장한다. 계정, 서버 저장, iOS 동기화를 추가하지 않는다.
- Room DB는 cloud backup과 device-to-device transfer 양쪽에서 제외한다.
- 백그라운드 큐, 완료 알림, 자동 재시도, 재시도 버튼을 추가하지 않는다.
- UI는 기본 Material 3를 사용한다. 최종 브랜딩·픽셀 단위 iOS 복제·커스텀 디자인 시스템을 추가하지 않는다.
- Debug 기본 backend는 에뮬레이터용 `http://10.0.2.2:3000`이다. 실기기 Debug는 Gradle property로 LAN/HTTPS URL을 주입한다. Release는 명시적으로 주입한 HTTPS URL만 허용한다.
- Release URL 검증은 Release task 실행 때만 평가한다. property 없는 Debug 구성·테스트는 성공해야 한다.
- 엄격한 TDD는 적용하지 않는다. 각 기능 구현과 테스트를 같은 Task에서 완료하고 Task 종료 전 관련 테스트를 통과시킨다.
- 자동 Android 테스트는 단일 emulator에서 실행해 불필요한 parallel device clone을 만들지 않는다.
- 사용자 문구는 spec의 정확한 영문을 사용하며 새 화면·상태·정책·문구를 임의로 추가하지 않는다.
- Home과 My Notes는 독립 back stack을 유지하며 공유 성공은 My Notes 탭의 대상 상세를 연다.
- 상세의 Analyze는 note ID 재조회 대신 클릭 순간 `AnalysisInputSnapshot`을 전달한다.

## Review Focus

- 공유 text에 설명문과 URL이 섞이거나 같은 영상의 URL 변형이 반복될 때 하나의 video ID로 수렴하고, 서로 다른 두 영상이면 저장하지 않는가 — Task 2 parser tests.
- 가져오기 중 `onNewIntent`로 새 공유가 오면 이전 call이 취소되고, 회전·process recreation은 기존 intent를 재소비하지 않으며, 이전 완료 상태가 새 화면에 적용되지 않는가 — Task 4 generation tests와 Task 9 lifecycle test.
- active/trashed 사전 조회 뒤 다른 coroutine이 상태를 바꿔도 저장 transaction의 최신 조회가 중복 insert나 잘못된 상세 이동을 막는가 — Task 3 race tests와 Task 4 coordinator tests.
- 구성 변경·process recreation 뒤 완료 navigation 상태가 유실·중복 소비되지 않고 이미 저장된 note를 재생성하지 않는가 — Task 5 navigation tests.
- cancellation이 transaction 직전과 commit 직후에 도착할 때 각각 무저장과 완결된 단일 note로 끝나는가 — Task 3 cancellation-boundary tests.

---

### Task 1: Android 프로젝트 기반과 안전한 환경 설정

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/gradle/libs.versions.toml`
- Create: `android/gradle/wrapper/gradle-wrapper.properties`
- Create: `android/gradle/wrapper/gradle-wrapper.jar`
- Create: `android/gradlew`
- Create: `android/gradlew.bat`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/proguard-rules.pro`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/debug/AndroidManifest.xml`
- Create: `android/app/src/main/java/com/andrewkim/reforge/ReforgeApplication.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/config/AppConfig.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/ui/theme/ReforgeTheme.kt`
- Create: `android/app/src/main/res/values/strings.xml`
- Create: `android/app/src/main/res/values/themes.xml`
- Create: `android/app/src/main/res/xml/backup_rules.xml`
- Create: `android/app/src/main/res/xml/data_extraction_rules.xml`
- Create: `android/app/src/test/java/com/andrewkim/reforge/config/AppConfigTest.kt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `data class AppConfig(val backendBaseUrl: HttpUrl)` and `AppConfig.from(rawValue: String, isRelease: Boolean): AppConfig`.
- Produces: Gradle `BuildConfig.BACKEND_BASE_URL`, `BuildConfig.IS_RELEASE`, Compose-enabled empty `MainActivity` and `ReforgeTheme`.
- Consumes: Gradle property `REFORGE_BACKEND_BASE_URL`; Debug omission becomes `http://10.0.2.2:3000`, Release omission or non-HTTPS value fails configuration.

- [ ] **Step 1: Scaffold the Gradle project**

Create a one-module Kotlin DSL project with pinned versions from `Tech Stack`, Room schema export to `android/app/schemas`, Java 17, `minSdk=26`, `compileSdk=37`, `targetSdk=37`, application ID `com.andrewkim.reforge`, test dependencies, and the complete Gradle wrapper 9.6.0 including its JAR. Use AGP 9.4 built-in Kotlin; do not apply `org.jetbrains.kotlin.android`. Apply Compose and Serialization compiler plugins at built-in Kotlin version 2.2.10 and KSP 2.3.10. Add only `google()` and `mavenCentral()` repositories.

- [ ] **Step 2: Add build configuration and manifest boundaries**

Declare launcher plus `ACTION_SEND`/`text/plain` intent filters on `MainActivity`, set `android:launchMode="singleTask"`, add `INTERNET`, set the app label to `Reforge`, enable cleartext only in the Debug manifest, and expose `BACKEND_BASE_URL` through `BuildConfig`. Set `allowBackup="false"` and use both legacy backup rules and Android 12+ data-extraction rules to exclude the database domain from cloud backup and device transfer. Add `android/.gradle`, `android/.kotlin`, `android/local.properties`, build outputs, and IDE-local files to `.gitignore` without ignoring Room schemas.

- [ ] **Step 3: Implement and test `AppConfig`**

Implement `AppConfig.from` with trailing-slash normalization and exact validation. Tests: Debug default and injected LAN URL succeed; blank, unexpanded placeholder, malformed URL fail; Release accepts only an injected HTTPS URL and rejects Debug default, HTTP, or blank. Wire the Gradle property check lazily to Release assemble/bundle tasks so Debug configuration never evaluates the Release requirement.

- [ ] **Step 4: Verify the project baseline**

Run: `cd android && ./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug`

Expected: all three tasks succeed without `REFORGE_BACKEND_BASE_URL`; dependency resolution, Compose compilation, Room KSP code generation, and AAR metadata checks pass; no Android device is started.

- [ ] **Step 5: Verify Release and backup guards**

Run the following separately: property-less `:app:assembleRelease` must fail with the configured HTTPS message; HTTP Release property must fail; a placeholder HTTPS property must assemble an unsigned Release successfully. Inspect merged Debug/Release manifests to prove Debug-only cleartext, `singleTask`, and both backup-rule references; inspect merged backup resources to prove Room databases are excluded from cloud and device transfer.

- [ ] **Step 6: Commit**

```bash
git add .gitignore android
git commit -m "feat: Android 앱 기반 구성 추가"
```

### Task 2: YouTube 공유 입력과 backend 네트워크 계약

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/YouTubeVideoIdentity.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/SharedTextParser.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareIntentParser.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/ApiError.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/TranscriptModels.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/ReforgeApi.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/YoutubeTranscriptService.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/YouTubeAvailabilityService.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/ShareTitleResolver.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/YouTubeVideoIdentityTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/SharedTextParserTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/network/YoutubeTranscriptServiceTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/network/YouTubeAvailabilityServiceTest.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/sharing/ShareIntentParserTest.kt`

**Interfaces:**
- Produces: `data class YouTubeVideoIdentity(val videoId: String, val canonicalUrl: HttpUrl, val sourceKey: String)` and `parse(rawUrl: String): Result<YouTubeVideoIdentity>`.
- Produces: `sealed interface SharedTextResult { data class Valid(val identity, val sourceUrl, val sharedTitle); data object Invalid; data object Ambiguous }` and `SharedTextParser.parse(text: CharSequence): SharedTextResult`.
- Produces: `ShareIntentParser.parse(intent: Intent): SharedTextResult`; this is a thin Android adapter and delegates all text semantics to `SharedTextParser`.
- Produces: `YoutubeTranscriptFetching.fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse`, `YouTubeAvailabilityChecking.check(canonicalUrl): YouTubeAvailability.Available/Unavailable`, and `ShareTitleResolving.resolve(canonicalUrl): String?`.

- [ ] **Step 1: Implement YouTube identity and shared-text parsing**

Accept exact 11-character IDs from `youtube.com/watch?v=`, `www.youtube.com/watch?v=`, `m.youtube.com/watch?v=`, `youtu.be/`, and `/shorts/`; accept HTTP or HTTPS input but always emit an HTTPS `www.youtube.com` canonical URL; strip query/fragment noise; reject other hosts, credentials, embed paths, empty IDs, and 10/12-character IDs. Extract all HTTP(S) URL candidates from shared text: zero valid identities is `Invalid`, multiple representations of one video is one `Valid`, and two distinct video IDs is `Ambiguous`. Use non-URL surrounding text before the URL only as a trimmed optional shared title.

- [ ] **Step 2: Add parser tests including Review Focus inputs**

Test each accepted URL form, including canonical `https://www.youtube.com/watch?v=dQw4w9WgXcQ` and HTTP input, converges to the same HTTPS canonical URL and `youtube:dQw4w9WgXcQ`; malicious suffix hosts and credentials are rejected; prose plus URL preserves title; repeated same-video variants remain valid; two distinct videos are ambiguous. Put actual Android `Intent` action/MIME/extra tests in the instrumented test file rather than JVM unit tests.

- [ ] **Step 3: Implement transcript and title clients**

Use Retrofit/Kotlin Serialization for `POST /youtube/transcript` with `{youtubeUrl,title}` and the exact response fields defined by `backend-fastapi/app/schemas.py::YoutubeTranscriptResponse`. Decode backend `{error:{code,message}}` for non-2xx responses into `ApiError`. `YouTubeAvailabilityService` uses a separate Retrofit base URL and maps 401/404/429/other non-2xx to the iOS-equivalent typed unavailable reasons. `ShareTitleResolver` alone collapses unavailable, timeout, non-2xx, and empty title to `null`; it must rethrow `CancellationException`. Fix transcript timeout at 30 seconds and share-title timeout at 1.5 seconds.

- [ ] **Step 4: Add MockWebServer contract tests**

Assert request paths, methods, JSON keys, canonical URL, every transcript response field, backend error-code preservation, malformed JSON handling, 30-second transcript client config, Home availability mapping for 401/404/429/other, share-title `null` fallback, and cancellation propagation. Tests must verify no LLM/analyze request is made by transcript fetching.

- [ ] **Step 5: Verify Task 2**

Run unit tests with `./gradlew :app:testDebugUnitTest --tests 'com.andrewkim.reforge.sharing.*' --tests 'com.andrewkim.reforge.network.*'`, then run the focused `ShareIntentParserTest` instrumented class on the single emulator.

Expected: parser and network contract tests pass.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main android/app/src/test android/app/src/androidTest android/app/build.gradle.kts android/gradle/libs.versions.toml
git commit -m "feat: Android 공유 및 transcript 계약 추가"
```

### Task 3: Room 콘텐츠 노트 저장소와 휴지통 정책

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/ContentNote.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/ContentNoteEntity.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/ContentNoteDao.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/ReforgeDatabase.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/ContentNoteRepository.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/RoomContentNoteRepository.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/notes/RoomContentNoteRepositoryTest.kt`

**Interfaces:**
- Produces: `ContentNote`, `ContentNoteDraft`, `ShareNotePreparation.Active/Trashed/Absent`, and `SaveNoteOutcome.Saved/AlreadySaved/RestoreRequired` with the spec's exact fields.
- Produces: String UUID note IDs everywhere and `ContentNoteRepository.observeActive(): Flow<List<ContentNote>>`, `observeTrash(): Flow<List<ContentNote>>`, `suspend find(id: String): ContentNote?`, `suspend prepareForShare(sourceKey: String): ShareNotePreparation`, `suspend saveOrReuse(draft: ContentNoteDraft): SaveNoteOutcome`, `suspend moveToTrash(id: String, at: Instant): Boolean`, `suspend restore(id: String): RestoreOutcome.Restored/AlreadyActive/Missing`, `suspend deletePermanently(id: String): Boolean`, and `suspend purgeExpired(cutoff: Instant): Int`.
- Produces: Room DB `reforge.db`, schema version 1, unique index on `sourceKey`, epoch-millisecond converters for `Instant`.

- [ ] **Step 1: Implement Room schema and mapping**

Create the entity with every field from the spec, DAO queries ordered by `createdAt DESC` for active notes and `trashedAt DESC` for trash, explicit domain mapping, and exported schema. Do not use destructive migration fallback.

- [ ] **Step 2: Implement repository transactions**

`prepareForShare` reads the latest state. `saveOrReuse` uses `withTransaction`, re-reads `sourceKey`, inserts only when absent, returns existing active without mutation, and returns restore-required for trash. On unique constraint conflict, re-read and return the concurrent winner rather than replace/upsert. Move, restore, permanent delete, and `trashedAt <= cutoff` purge each run in one transaction.

- [ ] **Step 3: Add instrumented repository tests**

Use a real in-memory Room DB. Assert active/trash order, persistence field mapping, single insert, active immutability, trashed no-change outcome, restore field preservation, permanent delete, exact 30-day cutoff, and no partial row when transaction throws.

- [ ] **Step 4: Add concurrency and cancellation-boundary tests**

Start two `saveOrReuse` calls for the same source key and assert one row, one stable UUID/first URL/transcript/createdAt, and outcomes that converge on the same note. Cancel before entering the transaction and assert no row; suspend after insert but before commit, cancel, and assert rollback; cancel after the repository signals commit and assert the committed row remains complete. Change active to trashed between preflight and save and assert `RestoreRequired`, not a duplicate. Delete or purge a trashed row while restore confirmation is waiting and assert `RestoreOutcome.Missing`; restore it elsewhere first and assert `RestoreOutcome.AlreadyActive` without overwriting fields.

- [ ] **Step 5: Verify Task 3 on one emulator**

Run: `cd android && ./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.andrewkim.reforge.notes.RoomContentNoteRepositoryTest`

Expected: one connected emulator runs all repository tests with zero failures.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/andrewkim/reforge/notes android/app/src/androidTest android/app/schemas
git commit -m "feat: Android 로컬 노트 저장소 추가"
```

### Task 4: 공유 수집 coordinator와 취소 가능한 상태 머신

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareIngestionCoordinator.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareImportState.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareImportViewModel.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/ShareIngestionCoordinatorTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/ShareImportViewModelTest.kt`

**Interfaces:**
- Consumes: Task 2 identity/transcript/title contracts and Task 3 `ContentNoteRepository`.
- Produces: `suspend ShareIngestionCoordinator.ingest(input: SharedTextResult.Valid): ShareIngestionResult` and `suspend restore(noteId: String): ShareIngestionResult`.
- Produces: `ShareIngestionResult.Saved/AlreadySaved/RestoreRequired`, all carrying `noteId`.
- Produces: `ShareImportState.Idle/Loading/AwaitingRestore/Error/Completed/Finished`; every non-idle state carries `generation`, and `Completed` carries `noteId` plus `navigationAcknowledged`.
- Produces: `ShareImportViewModel.accept(input)`, `confirmRestore()`, `cancelRestore()`, `cancelImport()`, and `acknowledgeDetailOpened(generation, noteId)` backed by `SavedStateHandle`.

- [ ] **Step 1: Implement coordinator state boundaries**

Active preflight returns immediately without title/transcript calls. Trashed preflight returns restore-required without network or mutation. Absent starts transcript and best-effort title concurrently, validates response video ID, checks cancellation before draft creation, then uses `saveOrReuse`. Map invalid identity, transcript unavailable, provider/network, identity mismatch, and storage errors to typed domain failures; do not embed user copy in the coordinator. Restore maps `Restored` and `AlreadyActive` to the same existing note detail and maps `Missing` to the approved storage error without creating a replacement.

- [ ] **Step 2: Add coordinator tests**

Assert all active/trashed/absent paths, network call counts, title fallback to canonical URL, shared-title precedence, identity mismatch no-save, transcript failure no-save, concurrent state change to trash, and restore preserving the original note. Assert Share ingestion never calls analysis.

- [ ] **Step 3: Implement generation-based ViewModel state**

Each `accept` increments a generation, cancels the previous job, clears any older completion, and ignores state updates whose generation is stale. Map failures to the exact spec copy. `confirmRestore` is single-flight; `cancelRestore` and `cancelImport` make the current generation terminal once. Persist the current generation and Completed/Finished state in `SavedStateHandle`; do not use a lossy `Channel` for navigation. The UI checks generation immediately before navigation and calls `acknowledgeDetailOpened` only after selecting My Notes and applying the target detail. A newer generation makes any queued older completion ineligible.

- [ ] **Step 4: Add ViewModel cancellation and late-result tests**

With `StandardTestDispatcher`, prove new input cancels old work; old progress/result/error/completed state cannot replace new state; Back before save yields no note; committed success remains a note even if cancellation follows; repeated Restore taps call repository once; Cancel during restore ignores late completion; restore after external purge yields the approved error; restore after external restore opens the existing note. Recreate the ViewModel with the same `SavedStateHandle` before and after navigation acknowledgement to prove completion recovers once and acknowledged completion does not re-open.

- [ ] **Step 5: Verify Task 4**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests 'com.andrewkim.reforge.sharing.ShareIngestionCoordinatorTest' --tests 'com.andrewkim.reforge.sharing.ShareImportViewModelTest'`

Expected: all coordinator and state-machine tests pass.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/andrewkim/reforge/sharing android/app/src/test/java/com/andrewkim/reforge/sharing
git commit -m "feat: Android 공유 수집 상태 흐름 추가"
```

### Task 5: 단일 Activity app shell과 공유 navigation

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/AppContainer.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppDestination.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/AnalysisInputSnapshot.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/ReforgeNavHost.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppCoordinator.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareImportScreen.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/ReforgeApplication.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/navigation/ShareNavigationTest.kt`

**Interfaces:**
- Consumes: Task 2 `ShareIntentParser`, Task 3 repository, and Task 4 persisted import state.
- Produces: `data class AnalysisInputSnapshot(val title: String, val canonicalUrl: String)` plus independent `home` and `notes` tab graphs, `note/{noteId}`, `trash`, and `share-import`; `AppCoordinator.acceptShare(intent)`, `openNote(noteId: String)`, `openHomeForAnalysis(snapshot: AnalysisInputSnapshot)`, and `finishShare()`.
- Produces: UI callbacks only; Composables never access DAO, Retrofit, Activity intent, or mutable repository state directly.

- [ ] **Step 1: Wire dependencies and one-time Intent consumption**

Create manual `AppContainer`. In `onCreate`, process the launch Intent only when `savedInstanceState == null`, then replace it with a neutral `ACTION_MAIN` intent; Activity recreation must not reprocess it. `onNewIntent` always replaces the stored intent and starts a new generation. General launch selects Home; valid/invalid/ambiguous shares enter Share Import.

- [ ] **Step 2: Implement independent tab stacks and Share Import UI**

Use nested graphs with saved/restored state so Home and My Notes stacks survive tab switching. Render Loading, exact errors with `Back`, and trash `Cancel / Restore`. A valid Completed state first selects My Notes and replaces its path with the target detail, then calls `acknowledgeDetailOpened`; re-check generation immediately before applying navigation.

- [ ] **Step 3: Add external-launch and restoration tests**

Launch cold via `ACTION_SEND`, send a second external share to the existing `singleTask` Activity, and prove `onNewIntent` cancels the first. Cover rotation during Loading, rotation after Completed but before acknowledgement, recreation after acknowledgement, older Completed queued before a new share, collector stop/start, and saved-state process recreation. Assert one detail, no duplicate insert, no stale navigation, and correct Back return to the originating app/task.

- [ ] **Step 4: Verify and commit**

Run the focused `ShareNavigationTest` on one emulator, then commit app shell/navigation files as `feat: Android 공유 탐색 흐름 추가`.

### Task 6: My Notes, 상세, 휴지통 UI

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NotesListViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NotesListScreen.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NoteDetailViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NoteDetailScreen.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/TrashViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/TrashScreen.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/notes/NotesScreensTest.kt`

**Interfaces:**
- Consumes: Task 3 repository and Task 5 notes graph.
- Consumes: Task 5 `AnalysisInputSnapshot` and captures it from the displayed note on Analyze click.
- Produces: notes/trash screen states and events.

- [ ] **Step 1: Implement My Notes and Note Detail**

List active notes newest-first, show `No saved notes yet.`, and provide Trash navigation and exact move confirmation. Detail uses Coil `AsyncImage` with `coil-compose` and `coil-network-okhttp`, shows the approved fields/actions, captures `AnalysisInputSnapshot` before invoking navigation, and returns to list when its note becomes missing/trashed.

- [ ] **Step 2: Implement Trash**

Show trash newest-first and `Trash is empty.`; Restore stays in Trash; permanent delete uses exact confirmation. Run purge before observing Trash, silently retain data on purge failure, and retry on the next entry/lifecycle opportunity.

- [ ] **Step 3: Add screen and independent-stack tests**

Assert ordering, empty states, confirmations, restore staying in Trash, missing detail return, and Analyze snapshot surviving a simultaneous move/delete. Test Detail→Home→My Notes returns to the prior detail, Trash→Home→Trash returns to Trash, and share success selects My Notes detail.

- [ ] **Step 4: Verify and commit**

Run `NotesScreensTest` on one emulator and commit notes files as `feat: Android 노트 보관함 화면 추가`.

### Task 7: analysis models와 SSE client

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/AnalyzeModels.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/AnalyzeStreamingClient.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/analysis/AnalyzeStreamingClientTest.kt`

**Interfaces:**
- Produces: exact `/analyze` request, SSE progress/error/result, categories, keywords, sources, citations; `suspend AnalyzeStreamingClient.analyze(request, onProgress): AnalyzeResponse`.

- [ ] **Step 1: Implement models and stable identity fallback**

Match backend camelCase fields. Preserve duplicate terms with server IDs and derive deterministic legacy IDs from transcript/category/keyword indexes. Default missing `sources` to `[source]` and missing citation collections to empty.

- [ ] **Step 2: Implement cancelable SSE parsing**

Use OkHttp streaming POST with `Accept: text/event-stream`; support fragmented lines/frames and Unicode. Unknown events are ignored; malformed known events, backend error, and EOF without result fail; cancellation cancels the call; no retry/reconnect.

- [ ] **Step 3: Test, verify, and commit**

Use MockWebServer for exact request JSON, ordered progress, fragmentation, result and legacy mapping, duplicate-term independence, error, EOF, and cancellation. Run the focused JVM suite and commit as `feat: Android 분석 API 계약 추가`.

### Task 8: Home 분석 상태와 결과 UI

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/KeywordSelectionState.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeState.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeScreen.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppCoordinator.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/navigation/ReforgeNavHost.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/analysis/HomeViewModelTest.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/analysis/HomeScreenTest.kt`

**Interfaces:**
- Consumes: Task 2 typed availability, Task 5 `AnalysisInputSnapshot`, Task 7 client.
- Produces: `setUrl`, `setTitle`, `analyze`, `applySnapshotAndAnalyze`; input generation, progress, error, result, category expansion, and keyword selection state.

- [ ] **Step 1: Implement Home state behavior**

Add URL/title, 500 ms oEmbed availability check, thumbnail, analysis, and generation guards. Home preserves iOS 401/404/429/unknown unavailable states and exact messages; network/decoding failure remains non-blocking. `applySnapshotAndAnalyze` clears old state, applies snapshot, and starts once without note ID requery.

- [ ] **Step 2: Implement minimal Material 3 Home**

Render the current iOS information/action order: empty prompt, fields, Coil thumbnail, Analyze, progress overlay, category/keyword selection, level 1→3 expansion, timestamps, and level citations. Do not add final styling.

- [ ] **Step 3: Add ViewModel and Compose tests**

Cover typed availability, network fallback, debounce cancellation, snapshot reset, one analysis, generation guards, duplicate IDs, level cap/citations, visible states, and Detail Analyze continuing after concurrent note deletion. Rotation must not start analysis twice.

- [ ] **Step 4: Verify and commit**

Run focused unit tests and `HomeScreenTest` on one emulator, then commit as `feat: Android 영상 분석 화면 추가`.

### Task 9: 생명주기, CI, 전체 검증과 기획 적합성 확인

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/lifecycle/TrashPurgeObserver.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/integration/ShareLifecycleTest.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/ReforgeApplication.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: app-start/foreground purge, complete share lifecycle coverage, Android CI, local documentation, and final evidence.

- [ ] **Step 1: Add lifecycle cleanup and integration coverage**

Purge at app startup and foreground; failure is silent and retried next opportunity. Test external cold/warm share, first-job cancellation by second share, Loading rotation, Completed-before-navigation process recreation, acknowledged recreation, app restart persistence, foreground purge, and purge failure retry.

- [ ] **Step 2: Add Android CI**

Install JDK 17 and Android SDK 37, validate the wrapper, cache Gradle, and run unit/lint/Debug build. Run instrumented tests on one API 37 device with sharding/parallel managed devices disabled.

- [ ] **Step 3: Document local configuration**

Document Android Studio path, application ID, emulator default, real-device Gradle property, Release HTTPS gate, tests, and manual share checklist. Never commit developer IPs, secrets, signing files, or `local.properties`.

- [ ] **Step 4: Run implementation and backend verification**

Run `./gradlew clean testDebugUnitTest lintDebug assembleDebug`, the property-less/HTTP/HTTPS Release matrix, merged-manifest and backup-rule checks, and `connectedDebugAndroidTest`. Then run `backend-fastapi/.venv/bin/pytest tests/test_api.py tests/test_analysis.py -q`. Record exact counts and device/API.

- [ ] **Step 5: Run manual UX and conformance checks**

Verify ordinary launch, all share branches, Back, errors, repeated external shares, rotation/recreation, independent tabs, snapshot Analyze, restart, and purge on emulator and available real device. Separately record `구현 검증`, `기획 적합성 검증`, `기획 대비 차이`, `해결되지 않은 충돌`, `근거 없는 추가 요소`; do not claim unrun device coverage.

- [ ] **Step 6: Commit**

Commit lifecycle, CI, and docs as `test: Android MVP 통합 검증 추가`.

### Task 10: 최종 교차검증과 브랜치 마감

**Files:**
- Modify: only files required by verified review findings

**Interfaces:**
- Consumes: completed Tasks 1–9 and evidence.
- Produces: reviewed, clean, locally committed branch; no push or PR without separate authorization.

- [ ] **Step 1: Review the full branch**

Use a fresh reviewer for spec compliance, Activity/task lifecycle, stale generations, Room transactions, API drift, backup/network security, accessibility, and Review Focus gaps. Verify findings before changing code.

- [ ] **Step 2: Fix verified findings and rerun focused tests**

For each accepted finding, change the smallest owning unit, add a regression test, run the focused suite, and commit separately from unrelated refactors.

- [ ] **Step 3: Rerun Task 9 full verification**

Recheck all automated suites, Release matrix, merged manifests, backup rules, Room schema, `git diff --check`, absence of secrets/local IPs, and clean status.

- [ ] **Step 4: Capture qualifying work learnings**

Invoke `capturing-work-learnings`; write only if its qualification gate passes.

- [ ] **Step 5: Report final local commits**

Report commits, test evidence, device coverage, required conformance headings, and remaining prerequisites. Leave commits local unless push/PR is separately authorized.

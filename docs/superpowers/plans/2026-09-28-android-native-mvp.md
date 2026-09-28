# Android Native MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube 공유로 Reforge를 연 뒤 자막이 있는 로컬 노트를 안전하게 저장·열람하고, 사용자가 명시적으로 분석을 시작할 수 있는 Android 네이티브 MVP를 만든다.

**Architecture:** `android/`의 단일 Activity Compose 앱이 일반 실행과 `ACTION_SEND`를 한 navigation graph로 처리한다. Room repository가 iOS와 동등한 active / trashed / absent 정책을 원자적으로 보장하고, coordinator와 ViewModel이 transcript 수집·취소·늦은 응답 차단을 담당한다. 기존 FastAPI transcript와 SSE analysis 계약을 재사용하며 UI는 기본 Material 3에 한정한다.

**Tech Stack:** Kotlin 2.4.10, Android Gradle Plugin 9.4.0, Gradle 9.6.0, JDK 17, compile/target SDK 36, min SDK 26, Compose BOM 2026.09.00, Navigation Compose 2.10.2, Lifecycle 2.11.0, Room 2.8.5 + KSP 2.3.10, Retrofit 3.0.0, OkHttp 5.3.0, Kotlin Coroutines, Kotlin Serialization, JUnit, kotlinx-coroutines-test, MockWebServer, Room in-memory tests, Compose UI tests

**Spec:** `docs/superpowers/specs/2026-09-28-android-native-mvp-design.md`

## Global Constraints

- application ID와 namespace는 `com.andrewkim.reforge`다.
- Android 8.0(API 26) 이상을 지원하고 compile/target SDK 36, JDK 17을 사용한다.
- 공유 수신은 `ACTION_SEND` + `text/plain`만 선언하며 `MainActivity`는 `android:exported="true"`다.
- 공유는 앱을 즉시 열지만 transcript 저장만 수행한다. LLM 분석은 노트 상세의 `Analyze` 탭에서만 시작한다.
- active 중복은 네트워크 없이 기존 상세를 열고 기존 note 필드를 바꾸지 않는다.
- trashed 중복은 `This video is in Trash. Restore it?`와 `Cancel / Restore`만 제공한다. 새 노트 생성 선택지는 없다.
- 취소·오류에는 부분 note가 없어야 한다. Room transaction commit 뒤 관찰된 취소는 완결된 note를 삭제하지 않는다.
- 노트는 Android 기기 로컬 Room DB에만 저장한다. 계정, 서버 저장, iOS 동기화를 추가하지 않는다.
- 백그라운드 큐, 완료 알림, 자동 재시도, 재시도 버튼을 추가하지 않는다.
- UI는 기본 Material 3를 사용한다. 최종 브랜딩·픽셀 단위 iOS 복제·커스텀 디자인 시스템을 추가하지 않는다.
- Debug 기본 backend는 에뮬레이터용 `http://10.0.2.2:3000`이다. 실기기 Debug는 Gradle property로 LAN/HTTPS URL을 주입한다. Release는 명시적으로 주입한 HTTPS URL만 허용한다.
- 엄격한 TDD는 적용하지 않는다. 각 기능 구현과 테스트를 같은 Task에서 완료하고 Task 종료 전 관련 테스트를 통과시킨다.
- 자동 Android 테스트는 단일 emulator에서 실행해 불필요한 parallel device clone을 만들지 않는다.
- 사용자 문구는 spec의 정확한 영문을 사용하며 새 화면·상태·정책·문구를 임의로 추가하지 않는다.

## Review Focus

- 공유 text에 설명문과 URL이 섞이거나 같은 영상의 URL 변형이 반복될 때 하나의 video ID로 수렴하고, 서로 다른 두 영상이면 저장하지 않는가 — Task 2 parser tests.
- 가져오기 중 `onNewIntent`로 새 공유가 오면 이전 call이 취소되고 이전 progress·result·error가 새 화면에 적용되지 않는가 — Task 4 generation tests와 Task 7 lifecycle test.
- active/trashed 사전 조회 뒤 다른 coroutine이 상태를 바꿔도 저장 transaction의 최신 조회가 중복 insert나 잘못된 상세 이동을 막는가 — Task 3 race tests와 Task 4 coordinator tests.
- 구성 변경·process recreation 뒤 완료 navigation effect가 중복 소비되지 않고 이미 저장된 note를 재생성하지 않는가 — Task 5 navigation tests.
- cancellation이 transaction 직전과 commit 직후에 도착할 때 각각 무저장과 완결된 단일 note로 끝나는가 — Task 3 cancellation-boundary tests.

---

### Task 1: Android 프로젝트 기반과 안전한 환경 설정

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/gradle/libs.versions.toml`
- Create: `android/gradle/wrapper/gradle-wrapper.properties`
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
- Create: `android/app/src/test/java/com/andrewkim/reforge/config/AppConfigTest.kt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `data class AppConfig(val backendBaseUrl: HttpUrl)` and `AppConfig.from(rawValue: String, isRelease: Boolean): AppConfig`.
- Produces: Gradle `BuildConfig.BACKEND_BASE_URL`, `BuildConfig.IS_RELEASE`, Compose-enabled empty `MainActivity` and `ReforgeTheme`.
- Consumes: Gradle property `REFORGE_BACKEND_BASE_URL`; Debug omission becomes `http://10.0.2.2:3000`, Release omission or non-HTTPS value fails configuration.

- [ ] **Step 1: Scaffold the Gradle project**

Create a one-module Kotlin DSL project with pinned versions from `Tech Stack`, version catalog aliases, Compose compiler plugin, Room schema export to `android/app/schemas`, Java 17, `minSdk=26`, `compileSdk=36`, `targetSdk=36`, application ID `com.andrewkim.reforge`, test dependencies, and Gradle wrapper 9.6.0. Add only `google()` and `mavenCentral()` repositories.

- [ ] **Step 2: Add build configuration and manifest boundaries**

Declare launcher plus `ACTION_SEND`/`text/plain` intent filters on `MainActivity`, add `INTERNET`, set the app label to `Reforge`, enable cleartext only in the Debug manifest, and expose `BACKEND_BASE_URL` through `BuildConfig`. Add `android/.gradle`, `android/local.properties`, build outputs, and IDE-local files to `.gitignore` without ignoring Room schemas.

- [ ] **Step 3: Implement and test `AppConfig`**

Implement `AppConfig.from` with trailing-slash normalization and exact validation. Tests: Debug default and injected LAN URL succeed; blank, unexpanded placeholder, malformed URL fail; Release accepts only an injected HTTPS URL and rejects Debug default, HTTP, or blank.

- [ ] **Step 4: Verify the project baseline**

Run: `cd android && ./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug`

Expected: all three tasks succeed; no Android device is started.

- [ ] **Step 5: Commit**

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
- Create: `android/app/src/main/java/com/andrewkim/reforge/network/YouTubeTitleService.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/YouTubeVideoIdentityTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/sharing/SharedTextParserTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/network/YoutubeTranscriptServiceTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/network/YouTubeTitleServiceTest.kt`

**Interfaces:**
- Produces: `data class YouTubeVideoIdentity(val videoId: String, val canonicalUrl: HttpUrl, val sourceKey: String)` and `parse(rawUrl: String): Result<YouTubeVideoIdentity>`.
- Produces: `sealed interface SharedTextResult { data class Valid(val identity, val sourceUrl, val sharedTitle); data object Invalid; data object Ambiguous }` and `SharedTextParser.parse(text: CharSequence): SharedTextResult`.
- Produces: `ShareIntentParser.parse(intent: Intent): SharedTextResult`; this is a thin Android adapter and delegates all text semantics to `SharedTextParser`.
- Produces: `YoutubeTranscriptFetching.fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse` and `YouTubeTitleResolving.resolve(canonicalUrl: HttpUrl): String?`.

- [ ] **Step 1: Implement YouTube identity and shared-text parsing**

Accept exact 11-character IDs from `youtube.com/watch?v=`, `m.youtube.com/watch?v=`, `youtu.be/`, and `/shorts/`; strip query/fragment noise; reject other hosts, credentials, non-HTTPS schemes, embed paths, empty IDs, and 10/12-character IDs. Extract all HTTP(S) URL candidates from shared text: zero valid identities is `Invalid`, multiple representations of one video is one `Valid`, and two distinct video IDs is `Ambiguous`. Use non-URL surrounding text before the URL only as a trimmed optional shared title.

- [ ] **Step 2: Add parser tests including Review Focus inputs**

Test each accepted URL form converges to `youtube:dQw4w9WgXcQ`; malicious suffix hosts and credentials are rejected; prose plus URL preserves title; repeated same-video variants remain valid; two distinct videos are ambiguous; unsupported action or MIME passed through `ShareIntentParser` is invalid.

- [ ] **Step 3: Implement transcript and title clients**

Use Retrofit/Kotlin Serialization for `POST /youtube/transcript` with `{youtubeUrl,title}` and the exact response fields in the spec. Decode backend `{error:{code,message}}` for non-2xx responses into `ApiError`. Use a separate Retrofit base URL for YouTube oEmbed and return `null` on its timeout/non-2xx/empty title so title failure never blocks transcript storage. Fix transcript timeout at 30 seconds and title timeout at 1.5 seconds.

- [ ] **Step 4: Add MockWebServer contract tests**

Assert request paths, methods, JSON keys, canonical URL, response decoding, backend error-code preservation, malformed JSON handling, 30-second transcript client config, and title `null` fallback. Tests must verify no LLM/analyze request is made by transcript fetching.

- [ ] **Step 5: Verify Task 2**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests 'com.andrewkim.reforge.sharing.*' --tests 'com.andrewkim.reforge.network.*'`

Expected: parser and network contract tests pass.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main android/app/src/test android/app/build.gradle.kts android/gradle/libs.versions.toml
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
- Produces: `ContentNoteRepository.observeActive(): Flow<List<ContentNote>>`, `observeTrash()`, `find(id)`, `prepareForShare(sourceKey)`, `saveOrReuse(draft)`, `moveToTrash(id, at)`, `restore(id)`, `deletePermanently(id)`, and `purgeExpired(cutoff): Int`.
- Produces: Room DB `reforge.db`, schema version 1, unique index on `sourceKey`, epoch-millisecond converters for `Instant`.

- [ ] **Step 1: Implement Room schema and mapping**

Create the entity with every field from the spec, DAO queries ordered by `createdAt DESC` for active notes and `trashedAt DESC` for trash, explicit domain mapping, and exported schema. Do not use destructive migration fallback.

- [ ] **Step 2: Implement repository transactions**

`prepareForShare` reads the latest state. `saveOrReuse` uses `withTransaction`, re-reads `sourceKey`, inserts only when absent, returns existing active without mutation, and returns restore-required for trash. On unique constraint conflict, re-read and return the concurrent winner rather than replace/upsert. Move, restore, permanent delete, and `trashedAt <= cutoff` purge each run in one transaction.

- [ ] **Step 3: Add instrumented repository tests**

Use a real in-memory Room DB. Assert active/trash order, persistence field mapping, single insert, active immutability, trashed no-change outcome, restore field preservation, permanent delete, exact 30-day cutoff, and no partial row when transaction throws.

- [ ] **Step 4: Add concurrency and cancellation-boundary tests**

Start two `saveOrReuse` calls for the same source key and assert one row, one stable UUID/first URL/transcript/createdAt, and outcomes that converge on the same note. Cancel before entering the transaction and assert no row; cancel after the repository signals commit and assert the committed row remains complete. Change active to trashed between preflight and save and assert `RestoreRequired`, not a duplicate.

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
- Produces: `ShareIngestionCoordinator.ingest(input: SharedTextResult.Valid): ShareIngestionResult` and `restore(noteId: UUID): ShareIngestionResult`.
- Produces: `ShareIngestionResult.Saved/AlreadySaved/RestoreRequired`, all carrying `noteId`.
- Produces: `ShareImportState.Idle/Loading/AwaitingRestore/Error/Completed` and one-shot `ShareImportEffect.OpenDetail(noteId)/Finish`.
- Produces: `ShareImportViewModel.accept(input)`, `confirmRestore()`, `cancelRestore()`, and `cancelImport()`.

- [ ] **Step 1: Implement coordinator state boundaries**

Active preflight returns immediately without title/transcript calls. Trashed preflight returns restore-required without network or mutation. Absent starts transcript and best-effort title concurrently, validates response video ID, checks cancellation before draft creation, then uses `saveOrReuse`. Map invalid identity, transcript unavailable, provider/network, identity mismatch, and storage errors to typed domain failures; do not embed user copy in the coordinator.

- [ ] **Step 2: Add coordinator tests**

Assert all active/trashed/absent paths, network call counts, title fallback to canonical URL, shared-title precedence, identity mismatch no-save, transcript failure no-save, concurrent state change to trash, and restore preserving the original note. Assert Share ingestion never calls analysis.

- [ ] **Step 3: Implement generation-based ViewModel state**

Each `accept` increments a generation, cancels the previous job, and ignores state/effect emissions whose generation is stale. Map failures to the exact spec copy. `confirmRestore` is single-flight; `cancelRestore` and `cancelImport` make the current generation terminal and emit `Finish` once. Keep effects in a `Channel`/`Flow`, not persisted state, so configuration changes cannot re-open detail.

- [ ] **Step 4: Add ViewModel cancellation and late-result tests**

With `StandardTestDispatcher`, prove new input cancels old work; old progress/result/error cannot replace new state; Back before save yields no note; committed success remains a note even if cancellation follows; repeated Restore taps call repository once; Cancel during restore ignores late completion; OpenDetail/Finish effects emit once.

- [ ] **Step 5: Verify Task 4**

Run: `cd android && ./gradlew :app:testDebugUnitTest --tests 'com.andrewkim.reforge.sharing.ShareIngestionCoordinatorTest' --tests 'com.andrewkim.reforge.sharing.ShareImportViewModelTest'`

Expected: all coordinator and state-machine tests pass.

- [ ] **Step 6: Commit**

```bash
git add android/app/src/main/java/com/andrewkim/reforge/sharing android/app/src/test/java/com/andrewkim/reforge/sharing
git commit -m "feat: Android 공유 수집 상태 흐름 추가"
```

### Task 5: 공유 진입, My Notes, 상세, 휴지통 UI

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/AppContainer.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppDestination.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/ReforgeNavHost.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppCoordinator.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/sharing/ShareImportScreen.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NotesListViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NotesListScreen.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NoteDetailViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/NoteDetailScreen.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/TrashViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/notes/TrashScreen.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/ReforgeApplication.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/navigation/ShareNavigationTest.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/notes/NotesScreensTest.kt`

**Interfaces:**
- Consumes: Task 3 repository and Task 4 ViewModel/effects.
- Produces: routes `home`, `notes`, `note/{noteId}`, `trash`, `share-import`; bottom navigation only for Home and My Notes.
- Produces: `AppCoordinator.acceptShare(intent)`, `openNote(noteId)`, `openHomeForAnalysis(noteId)`, and `finishShare()`.
- Produces: UI callbacks only; Composables do not access DAO, Retrofit, Activity intent, or mutable repository state directly.

- [ ] **Step 1: Wire application dependencies and share intents**

Create a manual `AppContainer` for config, OkHttp/Retrofit services, database, repository, coordinators, and ViewModel factories. `MainActivity.onCreate` and `onNewIntent` delegate to `AppCoordinator`; normal launch opens Home, valid share replaces the current share-import destination, invalid/ambiguous share shows the approved invalid-URL state. Do not preserve an in-progress share destination across process recreation.

- [ ] **Step 2: Implement minimal Material 3 navigation and Share Import screen**

Render Loading progress, exact error text with `Back`, and trash confirmation with `Cancel / Restore`. Back calls `cancelImport` before popping/finishing. Consume OpenDetail with `launchSingleTop` and remove share-import from the back stack so rotation or repeated collection cannot duplicate detail.

- [ ] **Step 3: Implement My Notes and Note Detail**

Notes list observes active notes newest-first, shows `No saved notes yet.`, provides Trash navigation, and asks `Move this note to Trash? You can restore it for 30 days.` before deletion. Detail shows title, 16:9 YouTube thumbnail, `Open in YouTube`, optional language/generated metadata, full transcript, `Analyze`, and `Move to Trash`; a missing/trashed current note returns to the list.

- [ ] **Step 4: Implement Trash**

Show trash newest-first and `Trash is empty.`. `Restore` keeps the user on Trash and removes the restored row. Permanent delete asks `Delete this note permanently? This can’t be undone.` with `Cancel / Delete`. Run purge on Trash entry before observing the list.

- [ ] **Step 5: Add Compose navigation and screen tests**

Test general launch vs share first destination, exact Loading/error/restore UI, Back cancellation, save success opening detail once, configuration recreation not duplicating detail, list/trash ordering, empty states, deletion confirmations, restore staying in Trash, external missing note returning to list, and `Analyze` emitting the coordinator callback without directly calling the API.

- [ ] **Step 6: Verify Task 5 on one emulator**

Run: `cd android && ./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.package=com.andrewkim.reforge`

Expected: Room and Compose tests run serially on one connected emulator with zero failures.

- [ ] **Step 7: Commit**

```bash
git add android/app/src/main android/app/src/androidTest
git commit -m "feat: Android 노트 보관함 화면 추가"
```

### Task 6: Home 분석과 결과 상호작용

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/AnalyzeModels.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/AnalyzeStreamingClient.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/KeywordSelectionState.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeState.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeViewModel.kt`
- Create: `android/app/src/main/java/com/andrewkim/reforge/analysis/HomeScreen.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/navigation/AppCoordinator.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/navigation/ReforgeNavHost.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/analysis/AnalyzeStreamingClientTest.kt`
- Create: `android/app/src/test/java/com/andrewkim/reforge/analysis/HomeViewModelTest.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/analysis/HomeScreenTest.kt`

**Interfaces:**
- Produces: Kotlin Serialization models for the exact `/analyze` request, SSE progress/error/result payloads, categories, keywords, sources, and external citations.
- Produces: `AnalyzeStreamingClient.analyze(request: AnalyzeRequest, onProgress: suspend (AnalyzeProgress) -> Unit): AnalyzeResponse`.
- Produces: `HomeViewModel.setUrl`, `setTitle`, `analyze`, and `applyNoteAndAnalyze(note)`; state includes input generation, loading stage/message, error, result, expanded category, and keyword selections.
- Consumes: Task 5 `openHomeForAnalysis(noteId)`; the detail `Analyze` action loads the current active note, applies it once, selects Home, and starts analysis once.

- [ ] **Step 1: Implement response models and stable identity fallback**

Match backend camelCase fields. Preserve duplicate display terms by using `categoryId` and `candidateClippingId`; for legacy null IDs, derive deterministic `transcriptId:category:index` and `categoryIdentity:keyword:index`. Default missing `sources` to `[source]` and missing citation arrays/external sources to empty lists.

- [ ] **Step 2: Implement the cancelable SSE analysis client**

Use OkHttp streaming `POST /analyze?stream=progress` with `Accept: text/event-stream`. Parse complete `event:`/`data:` frames for `progress`, `result`, and `error`; unknown events are ignored, malformed known events fail, backend error code/message are retained, EOF without result fails, and coroutine cancellation cancels the underlying call. Do not retry or reconnect.

- [ ] **Step 3: Add MockWebServer SSE tests**

Assert exact request JSON, ordered progress callbacks, fragmented line/frame handling, Unicode data, result decoding, legacy ID fallback, duplicate-term independence, backend error mapping, malformed frame, EOF without result, and cancellation closing the call.

- [ ] **Step 4: Implement Home state and analysis behavior**

Provide URL/title fields, 500 ms best-effort oEmbed title fill, validation, thumbnail derivation, analysis progress, error, categories, keyword select/remove, and level 1→2→3 expansion with level-specific citations. Every input change/apply-note increments generation and cancels title/analysis work; late callbacks check generation. `applyNoteAndAnalyze` clears prior result/error/selection, applies stored URL/title, and invokes analyze once.

- [ ] **Step 5: Implement the minimal Material 3 Home screen**

Match iOS information and interaction order without pixel imitation: empty prompt, URL/title fields, thumbnail, Analyze action, loading overlay with backend message, category chips, selectable keyword chips, selected explanations, `expand`, remove, timestamp links, and external-source links. Keep all user copy aligned with the current iOS screen.

- [ ] **Step 6: Add Home ViewModel and Compose tests**

Assert validation, debounced title fill cancellation, note application reset, exactly one analysis start, progress/result/error generation guards, duplicate keyword IDs, level cap at 3, citation filtering, and the visible empty/loading/result/error states. Test Detail `Analyze` selects Home and starts once after rotation.

- [ ] **Step 7: Verify Task 6**

Run: `cd android && ./gradlew :app:testDebugUnitTest :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.andrewkim.reforge.analysis.HomeScreenTest`

Expected: analysis unit tests and the focused Home UI suite pass.

- [ ] **Step 8: Commit**

```bash
git add android/app/src/main/java/com/andrewkim/reforge/analysis android/app/src/test/java/com/andrewkim/reforge/analysis android/app/src/androidTest/java/com/andrewkim/reforge/analysis android/app/src/main/java/com/andrewkim/reforge/navigation
git commit -m "feat: Android 영상 분석 흐름 추가"
```

### Task 7: 생명주기, CI, 전체 검증과 기획 적합성 확인

**Files:**
- Create: `android/app/src/main/java/com/andrewkim/reforge/lifecycle/TrashPurgeObserver.kt`
- Create: `android/app/src/androidTest/java/com/andrewkim/reforge/integration/ShareLifecycleTest.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/ReforgeApplication.kt`
- Modify: `android/app/src/main/java/com/andrewkim/reforge/MainActivity.kt`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: all earlier Tasks.
- Produces: app-start and foreground `purgeExpired(now - 30 days)`, lifecycle-safe repeated `ACTION_SEND`, Android CI job, local build/run documentation, and final verification evidence.

- [ ] **Step 1: Add lifecycle cleanup and integration coverage**

Run purge at application startup and each process foreground transition; failures leave data intact and do not block launch. Add an integration test that sends one share, injects a second while the first is suspended, verifies the first is cancelled/ignored, completes the second into one note/detail, recreates the Activity, and confirms no duplicate navigation or insert. Cover app restart persistence and foreground 30-day purge.

- [ ] **Step 2: Add Android CI**

Add a job that installs JDK 17 and Android SDK 36, validates the Gradle wrapper, caches Gradle, runs `testDebugUnitTest`, `lintDebug`, and `assembleDebug`. Add one managed emulator/instrumented-test job or step with hardware acceleration where supported; configure one device and disable sharding/parallel managed devices.

- [ ] **Step 3: Document local configuration and commands**

Update the repository layout, Android Studio open path, application ID, Debug emulator default, real-device `-PREFORGE_BACKEND_BASE_URL=...`, Release HTTPS requirement, unit/instrumented commands, and manual YouTube share checklist. Do not commit a developer IP, API key, signing file, or `local.properties`.

- [ ] **Step 4: Run implementation verification**

Run:

```bash
cd android
./gradlew clean testDebugUnitTest lintDebug assembleDebug
./gradlew connectedDebugAndroidTest
```

Expected: unit, lint, build, Room, Compose, navigation, and integration suites pass on one emulator. Record exact test counts and device/API level.

- [ ] **Step 5: Run backend contract regression**

Run: `cd backend-fastapi && .venv/bin/pytest tests/test_api.py tests/test_analysis.py -q`

Expected: existing transcript and analysis API tests pass without backend changes.

- [ ] **Step 6: Run manual emulator and real-device UX checks**

Verify: ordinary launch; YouTube share target; new save; active duplicate; trash `Cancel`; trash `Restore`; Back during loading; provider/transcript/storage error copy; new share during old request; Detail `Analyze`; app restart; 30-day purge. Use emulator `10.0.2.2` and, when an Android device is available, an injected LAN/HTTPS URL. Do not claim real-device verification when no device was tested.

- [ ] **Step 7: Run planning-to-product conformance review**

Compare the built flow against the spec and iOS notes-library source. Separately record `구현 검증`, `기획 적합성 검증`, `기획 대비 차이`, `해결되지 않은 충돌`, and `근거 없는 추가 요소`. Any mismatch, extra UI/copy, or unresolved conflict blocks completion even when tests pass.

- [ ] **Step 8: Commit**

```bash
git add android .github/workflows/ci.yml README.md
git commit -m "test: Android MVP 통합 검증 추가"
```

### Task 8: 최종 교차검증과 브랜치 마감

**Files:**
- Modify: only files required by verified review findings

**Interfaces:**
- Consumes: completed Tasks 1–7 and their verification evidence.
- Produces: reviewed, clean, locally committed branch; no push or PR unless separately authorized.

- [ ] **Step 1: Review the full branch**

Use a fresh reviewer to inspect the complete diff for spec compliance, lifecycle/cancellation bugs, Room transaction correctness, API contract drift, Android security configuration, inaccessible Compose controls, and untested Review Focus cases. Do not accept findings without reproducing or tracing them to code/spec evidence.

- [ ] **Step 2: Fix verified findings and rerun focused tests**

For each accepted finding, edit the smallest owning unit, add or update a regression test, run the focused suite, and commit with the repository convention. Do not bundle unrelated refactors.

- [ ] **Step 3: Rerun the full verification gate**

Run Task 7 Steps 4 and 5 again after the last fix. Recheck `git diff --check`, Room schema output, Release HTTPS guard, absence of secrets/local IPs, and a clean `git status`.

- [ ] **Step 4: Capture qualifying work learnings**

Invoke `capturing-work-learnings`. Write a solution entry only if its qualification gate identifies a verified non-obvious mistake, failed approach, recurring error, or costly investigation.

- [ ] **Step 5: Report the final local commit state**

Report commit hashes, test evidence, emulator/device coverage, the five required conformance headings, and remaining external prerequisites. Leave all commits local unless the user separately authorizes push and PR creation.

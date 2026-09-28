# iOS Notes Library MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공유 확장으로 저장한 YouTube 자막 노트를 iOS 앱에서 목록·상세·휴지통으로 관리하고, 상세의 한 번의 `Analyze` 동작으로 기존 Home 분석을 시작한다.

**Architecture:** 기존 App Group SwiftData 저장소를 단일 데이터 원본으로 확장하고 모든 복합 쓰기를 기존 파일 잠금과 새 `ModelContext` 안에서 원자적으로 처리한다. 앱 루트는 `TabView`와 앱 수준 coordinator를 사용해 Home/My Notes 탐색, pending route, 상세→분석 전환을 조정하며 Share Extension은 active/trashed/absent 분기를 명시적으로 표현한다.

**Tech Stack:** Swift 5, SwiftUI, UIKit Share Extension, SwiftData, Combine, XCTest, Xcode project targets

**Spec:** `docs/superpowers/specs/2026-09-28-ios-notes-library-design.md`

## Global Constraints

- 기준 브랜치는 PR #9의 `feat/youtube-share-ingestion`이며 기존 공유 수집·Home 분석 동작을 보존한다.
- 화면 문구는 설계 문서의 영어 문구를 그대로 사용한다.
- 공유 직후에는 분석하지 않고 My Notes 상세만 연다.
- 휴지통 보존 경계는 `trashedAt <= now - 30 days`다.
- 휴지통 영상 재공유 취소 시 API 요청, 새 노트, 복원, route를 만들지 않는다.
- 휴지통 영상 재공유 복원 시 같은 note ID와 자막을 유지하고 복원+route를 한 save로 처리한다.
- 검색, 편집, 분석 결과 저장, 내보내기, 계정·동기화, Android, 백엔드 변경은 제외한다.
- 새 외부 의존성을 추가하지 않는다.
- 이 계획은 프로젝트 정책에 따라 TDD를 전제하지 않는다. 각 구현 단위 직후 회귀 테스트를 추가·실행한다.
- iOS 자동 검증 destination은 현재 사용 가능한 `platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA`를 사용한다.

## Review Focus

- 휴지통 조회와 새 저장 사이 상태가 바뀌어도 중복 노트나 휴지통 노트 route가 생기지 않아야 한다 — Task 1의 경쟁 조건 테스트로 고정한다.
- `cutoff`와 정확히 같은 `trashedAt`도 만료 대상으로 삭제되어야 한다 — Task 1 경계값 테스트로 고정한다.
- route snapshot 이후 새 공유 route가 추가돼도 기존 snapshot 확인이 새 route를 삭제하지 않아야 한다 — Task 3 router 테스트로 고정한다.
- 이전 Home 분석 callback이 상세에서 전달한 새 입력을 덮지 않아야 한다 — Task 3 coordinator/Home 회귀 테스트로 고정한다.
- Share Extension 확인 중 취소하거나 복원 save가 실패하면 성공 문구와 부분 변경이 없어야 한다 — Task 1 ViewModel·저장소 테스트로 고정한다.

---

## File Map

### 수정

- `ios/Core/Storage/ContentNote.swift`: `trashedAt` 영속·전달 모델과 저장 결과 상태
- `ios/Core/Storage/ContentNoteRepository.swift`: 활성/휴지통 조회와 원자적 이동·복원·삭제·정리
- `ios/Core/Storage/PendingNoteRoute.swift`: 상세 탐색에 맞춘 immutable route snapshot
- `ios/Core/Sharing/ShareIngestionCoordinator.swift`: active/trashed/absent 공유 분기와 복원
- `ios/Core/Sharing/ShareExtensionViewModel.swift`: 휴지통 복원 확인 상태와 액션
- `ios/ShareExtension/ShareViewController.swift`: 확인 문구와 `Cancel`/`Restore` 버튼
- `ios/App/PendingNoteRouter.swift`: note ID 상세 route 적용 후 선택적 확인
- `ios/App/RootView.swift`: 탭별 탐색과 생명주기 연결
- `ios/App/NoteApp.swift`: 공유 repository/coordinator 조립
- `ios/NoteApp.xcodeproj/project.pbxproj`: 새 앱·테스트 파일 target membership
- 기존 관련 XCTest 파일: 모델·수집·route·Home 회귀 확대

### 생성

- `ios/App/AppCoordinator.swift`: 앱 탭, Notes path, pending route, 분석 전환, lifecycle purge 조정
- `ios/Features/Notes/NotesStore.swift`: Notes 화면이 소비하는 저장소 계약
- `ios/Features/Notes/NotesListViewModel.swift`: 활성 목록과 휴지통 이동 상태
- `ios/Features/Notes/NotesListView.swift`: My Notes 목록과 Trash 진입
- `ios/Features/Notes/ContentNoteDetailViewModel.swift`: 상세 조회·삭제 상태와 표시 데이터
- `ios/Features/Notes/ContentNoteDetailView.swift`: source-first 읽기 전용 상세
- `ios/Features/Notes/TrashViewModel.swift`: 만료 정리·복원·영구 삭제 상태
- `ios/Features/Notes/TrashView.swift`: 휴지통 목록과 확인 UI
- `ios/NoteAppTests/NotesViewModelTests.swift`: 목록·상세·휴지통 상태 테스트
- `ios/NoteAppTests/AppCoordinatorTests.swift`: 탭·route·분석·생명주기 테스트

### Task 1: 휴지통 저장소와 Share Extension 복원 확인

**Files:**
- Modify: `ios/Core/Storage/ContentNote.swift`
- Modify: `ios/Core/Storage/ContentNoteRepository.swift`
- Modify: `ios/Core/Sharing/ShareIngestionCoordinator.swift`
- Modify: `ios/Core/Sharing/ShareExtensionViewModel.swift`
- Modify: `ios/ShareExtension/ShareViewController.swift`
- Modify: `ios/NoteAppTests/ContentNoteRepositoryTests.swift`
- Modify: `ios/NoteAppTests/ShareIngestionCoordinatorTests.swift`
- Modify: `ios/NoteAppTests/ShareExtensionViewModelTests.swift`

**Interfaces:**
- Consumes: 기존 `SharedStoreLock`, `ModelContainer`, `PendingNoteRoute`, 자막·제목 서비스.
- Produces: `StoredContentNote.trashedAt`, `ShareNotePreparation`, 확장된 `SaveNoteOutcome`, 휴지통 저장소 연산, `ShareIngestionResult.restoreRequired`, 단발성 복원 확인 state machine.

- [ ] **Step 1: 모델과 저장소 연산을 구현한다**

  `ContentNote`에 `trashedAt: Date?`를 추가하고 새 draft는 `nil`로 저장한다. `StoredContentNote`에는 `trashedAt: Date? = nil` 기본값을 받는 명시적 initializer를 두어 기존 호출부를 유지하고 실제 snapshot 값은 전달한다.

  ```swift
  enum ShareNotePreparation: Equatable, Sendable {
      case activeRouted(StoredContentNote)
      case trashed(StoredContentNote)
      case absent
  }

  enum SaveNoteOutcome: Equatable, Sendable {
      case saved(StoredContentNote)
      case alreadySaved(StoredContentNote)
      case restoreRequired(StoredContentNote)
  }
  ```

  `ContentNoteRepository`에 아래 연산을 추가한다.

  ```swift
  func prepareForShare(sourceKey: String) throws -> ShareNotePreparation
  func note(id: UUID) throws -> StoredContentNote?
  func activeNotes() throws -> [StoredContentNote]
  func trashedNotes() throws -> [StoredContentNote]
  func moveToTrash(noteID: UUID, at: Date) throws
  func restore(noteID: UUID) throws
  func restoreAndEnqueueRoute(noteID: UUID) throws -> StoredContentNote
  func deletePermanently(noteID: UUID) throws
  @discardableResult func purgeExpiredTrash(cutoff: Date) throws -> Int
  ```

  모든 상태→쓰기 복합 연산은 `lock.withLock`, 새 `ModelContext`, 한 번의 `save()`를 사용한다. `prepareForShare`는 active 조회와 route 저장을 같은 임계 구역에서 처리한다. `saveOrReuse`는 잠금 안에서 active면 route+`.alreadySaved`, trashed면 무변경+`.restoreRequired`, absent면 note+route+`.saved`로 처리한다. 이동·영구 삭제·만료 정리는 대상 route도 같은 save에서 삭제한다.

- [ ] **Step 2: 수집 protocol과 active/trashed/absent 분기를 함께 전환한다**

  `ContentNotePersisting`을 아래 계약으로 교체하고 `ContentNoteRepository` 및 테스트 `RepositoryStub`을 같은 단계에서 전환한다. 구형 `find`+`enqueueRoute` 조합은 제거한다.

  ```swift
  protocol ContentNotePersisting {
      func prepareForShare(sourceKey: String) throws -> ShareNotePreparation
      func saveOrReuse(_ draft: ContentNoteDraft) throws -> SaveNoteOutcome
      func restoreAndEnqueueRoute(noteID: UUID) throws -> StoredContentNote
  }

  enum ShareIngestionResult: Equatable, Sendable {
      case saved(noteID: UUID)
      case alreadySaved(noteID: UUID)
      case restoreRequired(noteID: UUID)
  }

  protocol ShareIngesting {
      func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult
      func restore(noteID: UUID) async throws -> ShareIngestionResult
  }
  ```

  activeRouted는 추가 쓰기·네트워크 없이 `.alreadySaved`, trashed는 무변경·무네트워크 `.restoreRequired`, absent는 기존 자막 흐름을 사용한다. absent 이후 `saveOrReuse`가 경쟁 조건으로 `.restoreRequired`를 반환해도 같은 결과로 전달한다. `restore(noteID:)`는 원자적 복원+route 후 `.alreadySaved`를 반환한다.

- [ ] **Step 3: Share Extension의 단발성 확인 state machine과 UI를 구현한다**

  ```swift
  enum ShareExtensionPhase: Equatable {
      case idle
      case loading
      case awaitingRestore(UUID)
      case restoring(UUID)
      case finished
  }
  ```

  ViewModel은 `@Published private(set) var phase`와 기존 `statusText`, `isLoading`을 일관되게 갱신한다. `.restoreRequired`는 `awaitingRestore`와 정확한 확인 문구를 설정한다. `confirmRestore() async`는 awaiting 상태를 동기적으로 restoring으로 한 번만 전환하여 연속 탭을 무시하고, 완료 시 아직 동일 restoring 상태이며 task가 취소되지 않았을 때만 `Already saved`와 complete를 한 번 호출한다. `cancelRestore()`는 awaiting/restoring에서만 finished로 전환하고 cancel을 한 번 호출한다. finished 이후 callback은 모두 무시한다.

  `ShareViewController`는 `ingestionTask`와 별도 `restoreTask`를 보관한다. `Cancel`은 restore task를 취소한 뒤 `cancelRestore()`, `Restore`는 task 하나만 생성한다. `viewWillDisappear`와 `deinit`은 두 task를 모두 취소한다. awaiting 상태에서 spinner를 숨기고 정확한 `Cancel`/`Restore` 버튼을 표시한다.

- [ ] **Step 4: 저장소·수집·확장 회귀 테스트를 추가하고 실행한다**

  저장소 테스트:

  - 활성/휴지통 승인 정렬, 이동+route 삭제, 필드 보존 복원, 영구 삭제
  - 복원+route 원자성, trashed `saveOrReuse` 무변경, 30일 경계, 정리 재시도
  - `testPrepareForShareCannotRouteANoteMovedToTrashConcurrently()`
  - `testConcurrentTrashAndSaveNeverCreateDuplicateOrRouteTrashedNote()`

  수집·ViewModel 테스트:

  - trashed 중복은 네트워크 없이 restoreRequired
  - 경쟁 조건 restoreRequired, 동일 note 복원+route
  - 정확한 확인 문구, 복원 성공 `Already saved`, 복원 실패 무완료
  - `Cancel → Restore`, Restore 연속 호출, 외부 task 취소 뒤 늦은 완료가 모두 무변경·단일 종료

  Run:

  ```bash
  xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA' -only-testing:NoteAppTests/ContentNoteRepositoryTests -only-testing:NoteAppTests/ShareIngestionCoordinatorTests -only-testing:NoteAppTests/ShareExtensionViewModelTests
  xcodebuild build -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA'
  ```

  Expected: 세 suite 전체 PASS 및 NoteApp/ShareExtension Debug build success.

- [ ] **Step 5: Task 1을 커밋한다**

  ```bash
  git add ios/Core/Storage/ContentNote.swift ios/Core/Storage/ContentNoteRepository.swift ios/Core/Sharing/ShareIngestionCoordinator.swift ios/Core/Sharing/ShareExtensionViewModel.swift ios/ShareExtension/ShareViewController.swift ios/NoteAppTests/ContentNoteRepositoryTests.swift ios/NoteAppTests/ShareIngestionCoordinatorTests.swift ios/NoteAppTests/ShareExtensionViewModelTests.swift
  git commit -m "feat: iOS 노트 휴지통과 공유 복원 확인 추가"
  ```

### Task 2: My Notes·상세·휴지통 화면

**Files:**
- Create: `ios/Features/Notes/NotesStore.swift`
- Create: `ios/Features/Notes/NotesListViewModel.swift`
- Create: `ios/Features/Notes/NotesListView.swift`
- Create: `ios/Features/Notes/ContentNoteDetailViewModel.swift`
- Create: `ios/Features/Notes/ContentNoteDetailView.swift`
- Create: `ios/Features/Notes/TrashViewModel.swift`
- Create: `ios/Features/Notes/TrashView.swift`
- Create: `ios/NoteAppTests/NotesViewModelTests.swift`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Consumes: Task 1의 목록·상세·이동·복원·삭제·정리 연산과 `StoredContentNote`.
- Produces: `NotesStore`, 세 ViewModel, `NotesListView(repository:onOpenNote:onOpenTrash:)`, `ContentNoteDetailView(repository:noteID:onAnalyze:onDeleted:)`, `TrashView(repository:now:)`.

- [ ] **Step 1: Notes 저장소 계약과 ViewModel을 구현한다**

  `NotesStore`는 아래 시그니처만 노출하고 `ContentNoteRepository`가 conform한다.

  ```swift
  protocol NotesStore {
      func note(id: UUID) throws -> StoredContentNote?
      func activeNotes() throws -> [StoredContentNote]
      func trashedNotes() throws -> [StoredContentNote]
      func moveToTrash(noteID: UUID, at: Date) throws
      func restore(noteID: UUID) throws
      func deletePermanently(noteID: UUID) throws
      @discardableResult func purgeExpiredTrash(cutoff: Date) throws -> Int
  }
  ```

  ViewModel 공개 인터페이스는 다음으로 고정한다.

  ```swift
  @MainActor final class NotesListViewModel: ObservableObject {
      @Published private(set) var notes: [StoredContentNote]
      func load()
      func moveToTrash(noteID: UUID, at: Date)
  }

  @MainActor final class ContentNoteDetailViewModel: ObservableObject {
      @Published private(set) var note: StoredContentNote?
      var thumbnailURL: URL? { get }
      func load()
      func moveToTrash(at: Date) -> Bool
  }

  @MainActor final class TrashViewModel: ObservableObject {
      @Published private(set) var notes: [StoredContentNote]
      func load(now: Date)
      func restore(noteID: UUID)
      func deletePermanently(noteID: UUID)
  }
  ```

  실패 시 기존 배열·상세를 유지하고 Home과 같은 간단한 inline `errorMessage`만 갱신한다.

- [ ] **Step 2: 승인된 SwiftUI 화면을 구현한다**

  - My Notes: 최신순 목록, `No saved notes yet.`, Trash 진입, 삭제 확인 `Move this note to Trash? You can restore it for 30 days.` / `Cancel` / `Move to Trash`.
  - Detail: 제목, video ID 기반 16:9 썸네일, canonical URL을 여는 `Open in YouTube`, 존재하는 언어 코드·generated 여부, 전체 자막, `Analyze`, 휴지통 이동.
  - Trash: 삭제 시각 최신순, `Trash is empty.`, inline `Restore`, 영구 삭제 확인 `Delete this note permanently? This can’t be undone.` / `Cancel` / `Delete`.

  복원 성공 시 행만 사라지고 Trash 화면을 유지한다. 상세의 note가 외부에서 사라지거나 휴지통으로 이동한 상태면 `onDeleted`로 목록에 복귀한다.

- [ ] **Step 3: ViewModel 테스트를 추가하고 target에 등록한다**

  `NotesViewModelTests`에 다음을 구현한다.

  - `testListLoadsActiveNotesAndRefreshesAfterMoveToTrash()`
  - `testDetailDerivesThumbnailAndPreservesSnapshotForAnalyze()`
  - `testDetailClosesWhenNoteIsMissingOrTrashed()`
  - `testTrashLoadPurgesAtThirtyDayCutoffBeforeListing()`
  - `testRestoreAndPermanentDeleteRefreshTrashRows()`
  - `testStoreFailureKeepsPreviousVisibleState()`

  앱 파일은 NoteApp target에, 테스트는 NoteAppTests target에 `project.pbxproj`로 등록한다.

- [ ] **Step 4: Notes 테스트와 Debug build를 실행한다**

  Run:

  ```bash
  xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA' -only-testing:NoteAppTests/NotesViewModelTests
  xcodebuild build -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA'
  ```

  Expected: 테스트 PASS, 새 화면 파일을 포함해 build success.

- [ ] **Step 5: Task 2를 커밋한다**

  ```bash
  git add ios/Features/Notes ios/NoteAppTests/NotesViewModelTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: iOS My Notes와 휴지통 화면 추가"
  ```

### Task 3: 앱 탭 탐색·pending route·상세 분석 전환

**Files:**
- Create: `ios/App/AppCoordinator.swift`
- Create: `ios/NoteAppTests/AppCoordinatorTests.swift`
- Modify: `ios/Core/Storage/PendingNoteRoute.swift`
- Modify: `ios/Core/Storage/ContentNoteRepository.swift`
- Modify: `ios/App/PendingNoteRouter.swift`
- Modify: `ios/App/RootView.swift`
- Modify: `ios/App/NoteApp.swift`
- Modify: `ios/Features/Home/HomeViewModel.swift`
- Modify: `ios/NoteAppTests/PendingNoteRouterTests.swift`
- Modify: `ios/NoteAppTests/ContentNoteRepositoryTests.swift`
- Modify: `ios/NoteAppTests/HomeViewModelTests.swift`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Consumes: Task 1의 purge와 Task 2의 Notes 화면, 기존 `HomeViewModel.applySharedNote(_:)`와 `analyze()`.
- Produces: `AppTab`, `NotesRoute`, `AppCoordinator`, `PendingNoteRouter.consumeLatest(open:)`.

- [ ] **Step 1: router와 앱 coordinator를 구현한다**

  `PendingRouteSnapshot`을 `routeIDs: [UUID]`, `noteID: UUID?`로 바꾸고 route ID는 생성 시각 오름차순으로 반환한다. 최신 route 대상이 active일 때만 `noteID`를 채우며 missing 또는 trashed면 `nil`이다. 이 타입 변경과 repository, router, 관련 테스트 소비자 수정은 이 Task 안에서 함께 끝내 컴파일 가능한 상태를 유지한다.

  다음 탐색 타입과 공개 인터페이스를 사용한다.

  ```swift
  enum AppTab: Hashable { case home, myNotes }
  enum NotesRoute: Hashable { case detail(UUID), trash }

  @MainActor final class AppCoordinator: ObservableObject {
      @Published var selectedTab: AppTab
      @Published var notesPath: [NotesRoute]
      let homeViewModel: HomeViewModel

      func activate()
      func openNote(_ noteID: UUID)
      func analyze(_ note: StoredContentNote) async
  }
  ```

  `activate()`는 `cutoff = now - 30 days`로 purge를 시도한 뒤 최신 pending route를 소비한다. purge 실패도 route 처리를 막지 않고 다음 생명주기에 정리를 재시도한다. `openNote`는 My Notes를 선택하고 path를 `[.detail(noteID)]`로 교체한다. `analyze`는 Home에 note를 적용하고 Home 탭을 선택한 다음 `await homeViewModel.analyze()`를 정확히 한 번 호출한다.

  `HomeViewModel.applySharedNote(_:)`는 `youtubeLink`와 `lastAutoFilledURL` 모두 `note.canonicalURL.absoluteString`을 사용하도록 바꾼다. 원래 공유 URL은 상세의 source 정보로만 유지한다.

  `PendingNoteRouter.consumeLatest(open: (UUID) throws -> Void)`는 active note ID를 open closure가 수락한 뒤 snapshot에 포함된 route ID만 확인한다. open 실패 시 route를 남긴다. snapshot의 최신 route가 orphan/trashed/missing note면 그 최신 route 하나만 제거하고 다시 snapshot을 읽어 다음 유효 route를 찾는다. 유효한 최신 route를 열면 그 시점에 캡처된 이전 route까지 함께 확인하며, snapshot 이후 추가된 route는 남긴다.

- [ ] **Step 2: RootView와 NoteApp 조립을 탭 구조로 교체한다**

  `NoteApp`은 container/repository를 한 번 구성해 coordinator와 Notes 화면에 주입한다. `RootView`는 탭마다 독립 `NavigationStack`을 제공한다.

  - Home tab: 기존 `HomeView`와 같은 `HomeViewModel` 인스턴스
  - My Notes tab: `NotesListView`; `.detail(UUID)`와 `.trash` destination
  - 상세 `Analyze`: `Task { await coordinator.analyze(note) }`
  - 첫 화면 `.task`와 `scenePhase == .active`: `coordinator.activate()`
  - Trash 진입: `TrashViewModel.load(now:)`가 별도 purge를 실행

  공유 route를 열 때 자동으로 `analyze()`를 호출하지 않는다.

- [ ] **Step 3: coordinator·router·Home 회귀 테스트를 추가한다**

  `AppCoordinatorTests`:

  - `testActivationPurgesThenOpensLatestNoteInMyNotes()`
  - `testOpenNoteReplacesExistingNotesPath()`
  - `testAnalyzeSelectsHomeAppliesNoteAndStartsExactlyOnce()`

  `PendingNoteRouterTests`:

  - 기존 apply-before-ack 검증을 note ID open-before-ack으로 변경
  - `testAcknowledgeKeepsRouteCreatedAfterSnapshot()` 유지·강화
  - missing/trashed orphan 확인 처리와 open 실패 route 보존

  `HomeViewModelTests`는 상세에서 적용한 note 이후 늦은 progress/error/title callback이 입력을 덮지 않는 기존 세 테스트를 유지한다.

  source URL과 canonical URL이 다른 fixture로 `analyze()`가 분석 서비스에 canonical URL을 정확히 한 번 전달하는 테스트를 추가한다.

- [ ] **Step 4: 앱 조정 계층 테스트와 build를 실행한다**

  Run:

  ```bash
  xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA' -only-testing:NoteAppTests/AppCoordinatorTests -only-testing:NoteAppTests/PendingNoteRouterTests -only-testing:NoteAppTests/HomeViewModelTests -only-testing:NoteAppTests/ContentNoteRepositoryTests
  xcodebuild build -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA'
  ```

  Expected: 테스트 PASS, 두 target build success.

- [ ] **Step 5: Task 3을 커밋한다**

  ```bash
  git add ios/App ios/Core/Storage/PendingNoteRoute.swift ios/Core/Storage/ContentNoteRepository.swift ios/Features/Home/HomeViewModel.swift ios/NoteAppTests/AppCoordinatorTests.swift ios/NoteAppTests/PendingNoteRouterTests.swift ios/NoteAppTests/ContentNoteRepositoryTests.swift ios/NoteAppTests/HomeViewModelTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: 공유 노트를 My Notes 상세로 연결"
  ```

### Task 4: 전체 회귀·기획 적합성 검증

**Files:**
- Modify only if verification finds a defect: files owned by Tasks 1–4

**Interfaces:**
- Consumes: Tasks 1–3의 완성된 iOS 앱과 기존 backend API.
- Produces: NL-01~NL-11 검증 근거와 깨끗한 task diff.

- [ ] **Step 1: 전체 자동 테스트를 실행한다**

  ```bash
  xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,id=27BE906F-3031-4204-970C-4D62383904EA'
  (cd backend-fastapi && PYTHONPATH=. /Users/jeezoo/Code/Projects/Reforge/Reforge/backend-fastapi/.venv/bin/python -m pytest -q -p no:cacheprovider)
  ```

  Expected: 기존 기준선 41개보다 늘어난 iOS 전체 테스트 PASS, backend `169 passed, 1 skipped` 유지.

- [ ] **Step 2: Release bundle 설정과 저장소 영속성을 검증한다**

  Debug/Release simulator build 후 앱과 Share Extension의 built `Info.plist`에 같은 `NOTEAPP_BACKEND_BASE_URL`이 들어 있는지 `plutil -p`로 확인한다. 테스트 store를 다시 연 뒤 활성/휴지통 상태, note ID, 자막, pending route가 유지되는 통합 테스트를 실행한다.

- [ ] **Step 3: 승인된 사용자 흐름을 수동 대조한다**

  NL-01~NL-11을 기준으로 다음을 확인한다.

  - 새 영상 공유 → Saved → 앱 활성화 → My Notes 상세 → 수동 `Analyze`
  - 활성 영상 재공유 → Already saved → 기존 상세
  - 활성 노트 삭제 → Trash → 일반 복원
  - 휴지통 영상 재공유 → Cancel 시 무변경
  - 휴지통 영상 재공유 → Restore → Already saved → 같은 상세
  - 영구 삭제와 30일 경계 정리
  - 재실행 후 활성·휴지통 상태 유지

- [ ] **Step 4: 기획 적합성 보고를 작성한다**

  최종 보고에서 `구현 검증`, `기획 적합성 검증`, `기획 대비 차이`, `해결되지 않은 충돌`, `근거 없는 추가 요소`를 각각 명시한다. 불일치가 하나라도 있으면 완료로 처리하지 않고 해당 Task로 돌아가 수정·재검증한다.

- [ ] **Step 5: 검증 수정분이 있을 때만 커밋한다**

  수정 파일만 선별해 아래 형식으로 커밋한다. 변경이 없으면 빈 커밋을 만들지 않는다.

  ```bash
  git commit -m "fix: iOS 노트 보관함 최종 검증 보완"
  ```

# YouTube Share Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** YouTube Share Extension이 transcript 확보에 성공한 영상만 App Group에 한 번 저장하고, 다음 NoteApp 활성화 때 해당 노트를 기존 Home에 안전하게 적용한다.

**Architecture:** FastAPI에 LLM을 호출하지 않는 transcript 전용 ingestion 경계를 추가하고 기존 `/analyze`도 같은 준비 결과를 사용한다. iOS는 video ID 정규화, transcript client, SwiftData repository, POSIX lock, share coordinator를 공용 Core로 두며 NoteApp과 Share Extension이 같은 App Group store를 사용한다. Extension은 자체 상태만 표시하고, 앱은 pending route snapshot을 적용한 뒤 해당 snapshot만 확인 처리한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy async, pytest; Swift 5, SwiftUI, UIKit Share Extension, SwiftData, XCTest, POSIX `flock`; iOS 17.6+

**Spec:** `docs/superpowers/specs/2026-09-28-youtube-share-ingestion-design.md`

## Global Constraints

- TDD 필수: 각 production 변경 전에 실패 이유가 명확한 테스트를 작성하고 RED를 확인한다.
- Share Extension에서 containing app을 열지 않는다. `UIApplication`, responder-chain 우회, private API를 사용하지 않는다.
- 같은 영상은 URL 문자열이 아니라 정확한 11자 YouTube video ID와 `youtube:<videoId>`로 판정한다.
- Transcript 실패·network timeout·저장 실패와 save 시작 전 취소에는 `ContentNote`와 `PendingNoteRoute`를 남기지 않는다. Lock 안에서 save가 시작된 뒤 관찰된 취소는 note·route를 함께 commit하며, 취소 때문에 이미 저장한 데이터를 삭제하지 않는다.
- 기존 노트의 UUID, 최초 URL, transcript, 생성 시각을 재공유로 갱신하지 않는다.
- NoteApp과 Share Extension의 모든 shared-store 쓰기는 같은 App Group lock file로 직렬화한다.
- 새 화면, 상세 화면, 재시도 버튼, 자동 분석, 알림, 내보내기, 자체 STT fallback을 추가하지 않는다.
- Extension이 직접 표시하는 사용자 문구는 `Saved to Reforge`, `Already saved`, `The video is available, but transcript is not available.`, `Transcript provider failed. Please try again.`만 사용한다. 잘못된 input, 취소, 저장 실패에는 새 문구를 만들지 않고 `cancelRequest`로 종료한다.
- Debug simulator만 localhost fallback을 허용한다. 실기기 Debug는 주입된 LAN/HTTPS URL, Release는 주입된 HTTPS URL만 허용한다.
- App Group identifier는 `group.com.andrewkim.noteapp`, 앱 bundle identifier는 `com.andrewkim.noteapp`, extension은 `com.andrewkim.noteapp.share`를 사용한다.
- 현재 사용자 변경인 `sample.json`과 untracked `AGENTS.md`를 수정·스테이징·커밋하지 않는다.
- 현재 환경은 Xcode 26.6, iOS 26.5 Simulator SDK, `NoteApp` scheme을 제공한다. 다만 최초 확인에서 CoreSimulator 1051.50.0과 Xcode 요구 1051.55.0이 달라 simulator 실행이 막혔다. 구현 전에 다시 확인하고, 계속 막히면 generic simulator `build-for-testing`으로 test bundle compile까지 검증한 뒤 실행 테스트는 외부 blocker로 정확히 보고한다.
- CoreSimulator 문제로 실행 RED/GREEN을 확인할 수 없으면 `build-for-testing`은 컴파일 검증으로만 기록한다. 해당 실행 검증이 필요한 iOS production 단계와 Task 완료·커밋은 보류하고, Simulator 복구 또는 다른 승인된 실행 환경에서 RED/GREEN을 확인한 뒤 진행한다. 미정의 타입의 compile RED는 행동 테스트 RED를 대체하지 않는다.
- 새 XCTest를 작성하는 단계에서 해당 파일을 `NoteAppTests` Sources에 먼저 등록하고, RED/GREEN 출력의 실행 test 수가 0이 아닌지 확인한다. `@testable import NoteApp`에서 검증할 공용 production 파일은 RED 전에 NoteApp target에도 등록한다.

## Review Focus

- 동일 영상 두 건이 동시에 저장될 때 노트는 하나만 남고 최초 필드는 바뀌지 않아야 한다. Task 4의 두 container 경합 테스트로 고정한다.
- pending route 확인 처리 중 새 공유가 생기면 새 route가 삭제되지 않아야 한다. Task 4의 snapshot ID 확인 테스트로 고정한다.
- 공유 노트 적용 후 이전 영상의 늦은 title/progress/result/error가 Home을 되돌리지 않아야 한다. Task 7의 continuation 기반 테스트로 고정한다.
- 짧거나 noise-only인 자막은 사용자용 endpoint와 분석용 `/analyze`에서 서로 다른 검증 경계를 유지해야 한다. Task 1·2의 fixture 테스트로 고정한다.
- extension의 save 전 취소, transcript 오류, video ID 불일치, SwiftData save 실패가 성공 UI나 부분 저장을 만들지 않아야 한다. Save 시작 뒤 취소는 note·route 모두 저장되어야 하고, title timeout은 canonical URL 제목으로 성공해야 한다. Task 5·6의 coordinator/host 테스트로 고정한다.

---

### Task 1: 공용 YouTube transcript 준비 경계

**Files:**
- Create: `backend-fastapi/app/youtube_ingestion.py`
- Create: `backend-fastapi/tests/test_youtube_ingestion.py`
- Modify: `backend-fastapi/app/schemas.py:157-171`
- Modify: `backend-fastapi/app/analysis.py:34-60,271-297`
- Modify: `backend-fastapi/tests/test_analysis.py:359-430`

**Interfaces:**
- Consumes: `fetch_youtube_transcript(url: str) -> YoutubeTranscript`, `sanitize_transcript(raw_snippets) -> SanitizedTranscript`.
- Produces: `PreparedYoutubeTranscript`, `YoutubeTranscriptIngestionService.prepare(youtube_url: str) -> PreparedYoutubeTranscript`, `assert_transcript_available(value: Any) -> str`.
- `PreparedYoutubeTranscript` fields: `video_id`, `canonical_url`, `user_transcript_text`, `analysis_transcript_text`, `source_segments`, `language_code`, `language`, `is_generated`.

- [ ] **Step 1: 기존 `/analyze` 길이 동작 characterization 테스트 작성**

  `test_youtube_analysis_validates_labeled_analysis_text_not_user_text`, `test_youtube_analysis_keeps_short_source_result_when_labeled_text_is_long_enough`, `test_youtube_analysis_rejects_when_analysis_text_is_under_80_chars`를 추가한다. 원문 65~79자와 label 포함 길이를 분리하고 기대값은 현재 외부 동작에서 고정한다.

- [ ] **Step 2: 기존 동작 baseline GREEN 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_analysis.py -q`

  Expected: 새 characterization 테스트 포함 모두 PASS. 실패하면 refactor를 시작하지 않고 fixture가 실제 기존 동작을 표현하도록 바로잡는다.

- [ ] **Step 3: 사용자용 원문과 분석용 text 분리 실패 테스트 작성**

  `test_prepare_keeps_provider_text_without_segment_labels`, `test_prepare_builds_labeled_analysis_text_from_same_snippets`, `test_prepare_rejects_empty_user_transcript`, `test_prepare_keeps_noise_only_user_text_while_analysis_text_is_empty`를 작성한다. 기대값은 hand-written snippet fixture와 literal canonical URL로 만든다.

- [ ] **Step 4: 준비 서비스 테스트 RED 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_youtube_ingestion.py -q`

  Expected: `ModuleNotFoundError` 또는 `YoutubeTranscriptIngestionService` 미정의로 FAIL.

- [ ] **Step 5: 최소 준비 서비스와 availability validator 구현**

  `YoutubeTranscriptIngestionService.__init__(store: TranscriptStore | None = None, fetcher: Callable = fetch_youtube_transcript)`와 `async prepare(youtube_url: str)`를 구현한다. fetcher는 `asyncio.to_thread`에서 한 번 호출한다. 사용자용 text에는 `assert_transcript_available`, 분석용 text에는 아직 `assert_transcript_text`를 적용하지 않는다.

- [ ] **Step 6: 준비 서비스 GREEN 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_youtube_ingestion.py -q`

  Expected: 모두 PASS.

- [ ] **Step 7: characterization 보호 아래 `AnalyzeService` 리팩터링**

  `AnalyzeService.__init__`에 optional `youtube_ingestion`을 추가하고, YouTube `_resolve_transcript`는 `PreparedYoutubeTranscript.analysis_transcript_text`와 `source_segments`를 반환한다. 새 내부 wiring 자체를 assertion하지 않는다.

- [ ] **Step 8: refactor 회귀 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_analysis.py tests/test_youtube_ingestion.py -q`

  Expected: characterization와 새 준비 서비스 테스트 모두 PASS. 기존 `assert_transcript_text` 위치, analysis run, 저장 payload, 응답 계약이 유지된다.

- [ ] **Step 9: backend 부분 회귀 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_youtube_ingestion.py tests/test_analysis.py tests/test_sanitizer.py tests/test_schemas.py -q`

  Expected: 모두 PASS.

- [ ] **Step 10: 커밋**

  ```bash
  git add backend-fastapi/app/youtube_ingestion.py backend-fastapi/app/schemas.py backend-fastapi/app/analysis.py backend-fastapi/tests/test_youtube_ingestion.py backend-fastapi/tests/test_analysis.py
  git commit -m "feat: YouTube transcript 준비 경계 분리"
  ```

### Task 2: FastAPI transcript 전용 endpoint

**Files:**
- Modify: `backend-fastapi/app/schemas.py:14-92`
- Modify: `backend-fastapi/app/youtube_ingestion.py`
- Modify: `backend-fastapi/app/main.py:125-190`
- Modify: `backend-fastapi/tests/test_youtube_ingestion.py`
- Modify: `backend-fastapi/tests/test_api.py:1-145`
- Modify: `backend-fastapi/README.md:31-37`

**Interfaces:**
- Consumes: Task 1의 `YoutubeTranscriptIngestionService.prepare`, `TranscriptStore.set_transcript`.
- Produces: `YoutubeTranscriptRequest`, `YoutubeTranscriptResponse`, `YoutubeTranscriptIngestionService.ingest(youtube_url: str, title: str | None) -> YoutubeTranscriptResponse`, `POST /youtube/transcript`.
- Response keys: `transcriptId`, `videoId`, `canonicalYoutubeUrl`, `transcriptText`, `languageCode`, `language`, `isGenerated`.

- [ ] **Step 1: endpoint 계약과 persistence 실패 테스트 작성**

  `test_transcript_openapi_documents_request_and_response`, `test_ingest_stores_user_text_and_returns_that_row_id`, `test_ingest_does_not_create_analysis_run_or_call_llm`, `test_ingest_preserves_language_metadata`, `test_ingest_propagates_transcript_errors_without_store_write`를 작성한다. Fake store는 `set_transcript` 입력과 호출 횟수만 기록하고 실제 response field를 검증한다.

- [ ] **Step 2: RED 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_youtube_ingestion.py tests/test_api.py -q`

  Expected: `/youtube/transcript` 미등록과 schema/service method 미정의로 FAIL.

- [ ] **Step 3: success path schema, persistence, route 구현**

  `ingest`는 사용자용 원문과 `source_segments`를 `TranscriptStore.set_transcript`에 전달하고 canonical URL을 source URL로 저장한다. Route는 `TranscriptStore(db)` 외에 LLM client나 analysis run을 만들지 않는다.

- [ ] **Step 4: 오류 경계 테스트 추가**

  `test_transcript_endpoint_accepts_65_to_79_character_source`, `test_transcript_endpoint_accepts_noise_only_nonempty_source`, `test_transcript_endpoint_returns_existing_error_envelope`를 추가한다. `EMPTY_TRANSCRIPT`, `TRANSCRIPT_UNAVAILABLE`, `TRANSCRIPT_FETCH_FAILED`, `INVALID_YOUTUBE_URL`의 기존 envelope를 검증한다.

- [ ] **Step 5: 오류 경계 테스트 RED 확인**

  Run: `cd backend-fastapi && .venv/bin/pytest tests/test_youtube_ingestion.py tests/test_api.py -q`

  Expected: short/noise input 또는 request validation/error envelope branch 중 미구현 동작으로 FAIL.

- [ ] **Step 6: request validation과 오류 경계 구현**

  Request는 object만 허용하고 `youtubeUrl` required non-empty, `title` optional non-empty로 검증한다. 기존 `AppError` envelope를 그대로 사용하며 `SHORT_TRANSCRIPT`를 이 endpoint에서 만들지 않는다.

- [ ] **Step 7: GREEN 및 전체 FastAPI 검증**

  Run: `cd backend-fastapi && .venv/bin/pytest -q`

  Expected: PostgreSQL opt-in migration test가 환경 때문에 skip되는 경우를 제외하고 모두 PASS.

  Run: `cd backend-fastapi && .venv/bin/ruff check app tests`

  Expected: exit 0.

- [ ] **Step 8: README endpoint 목록 갱신 후 커밋**

  ```bash
  git add backend-fastapi/app/schemas.py backend-fastapi/app/youtube_ingestion.py backend-fastapi/app/main.py backend-fastapi/tests/test_youtube_ingestion.py backend-fastapi/tests/test_api.py backend-fastapi/README.md
  git commit -m "feat: YouTube transcript endpoint 추가"
  ```

### Task 3: iOS YouTube identity, transcript client, backend 설정

**Files:**
- Create: `ios/Core/YouTube/YouTubeVideoIdentity.swift`
- Create: `ios/Core/Networking/YouTubeTranscriptService.swift`
- Create: `ios/Config/Backend.xcconfig`
- Create: `ios/NoteAppTests/YouTubeVideoIdentityTests.swift`
- Create: `ios/NoteAppTests/YouTubeTranscriptServiceTests.swift`
- Create: `ios/NoteAppTests/AppConfigTests.swift`
- Modify: `ios/Core/Networking/AppConfig.swift:1-19`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj:1-561`

**Interfaces:**
- Produces: `YouTubeVideoIdentity.init(url: URL) throws`, with `videoID`, `canonicalURL`, `sourceKey`.
- Produces: `YouTubeTranscriptRequest`, `YouTubeTranscriptResponse`, `protocol YouTubeTranscriptFetching`, `URLSessionYouTubeTranscriptService.fetch(youtubeURL:title:) async throws`.
- Produces: `AppConfig.load(bundle:environment:isDebug:isSimulator:) throws -> AppConfig`; `AppConfig.default` delegates to it.

- [ ] **Step 1: URL 정규화 실패 테스트 작성**

  watch, mobile, youtu.be, shorts는 literal `dQw4w9WgXcQ`, canonical URL, `youtube:dQw4w9WgXcQ`로 수렴해야 한다. `javascript:`, 다른 host, embed, 빈 값, 10/12자 ID는 `invalidYouTubeURL`이어야 한다. Backend와 범위를 맞추기 위해 embed는 이번 계약에서 거부한다. 이 단계에서 production file reference를 NoteApp Sources에, test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 2: identity 테스트 RED 확인**

  Run when simulator is available: `xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -only-testing:NoteAppTests/YouTubeVideoIdentityTests -destination "platform=iOS Simulator,id=$SIMULATOR_ID" -derivedDataPath /tmp/reforge-derived-data`

  Expected: type 미정의로 build FAIL.

- [ ] **Step 3: identity 최소 구현**

  허용 host와 path만 parsing하고 11자 ID를 검증한다. 원본 query/fragment는 버리고 canonical URL과 sourceKey를 literal 형식으로 만든다.

- [ ] **Step 4: transcript client 실패 테스트 작성**

  custom `URLProtocol`로 POST path, JSON body, timeout, response decoding, backend error decoding, response `videoId`를 검증한다. Mock 자체 호출 여부가 아니라 실제 `URLRequest`와 반환/오류를 assertion한다. Production/test file target membership을 이 단계에서 등록한다.

- [ ] **Step 5: transcript client 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `YouTubeTranscriptServiceTests` 실행.

  Expected: request/response type과 service 미정의로 build FAIL.

- [ ] **Step 6: transcript client 구현**

  Endpoint는 base URL에 `youtube/transcript`를 append한다. request/response field는 Task 2 계약과 정확히 맞춘다. Extension lifetime에 맞춘 request timeout을 30초로 고정한다.

- [ ] **Step 7: AppConfig 환경 실패 테스트 작성**

  Debug simulator의 미설정 값은 `http://localhost:3000`; Debug device는 주입 값 필수; Release는 HTTPS 주입 값만 허용; `$(NOTEAPP_BACKEND_BASE_URL)` 미치환 문자열과 빈 문자열은 거부하는 테스트를 작성한다. 새 test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 8: AppConfig 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `AppConfigTests` 실행.

  Expected: 새 loader interface 미정의 또는 기존 localhost fallback 때문에 FAIL.

- [ ] **Step 9: AppConfig와 shared xcconfig 구현**

  `Backend.xcconfig` 값은 두 target에서 상속 가능하게 두고 실제 endpoint는 저장소에 하드코딩하지 않는다. `AppConfig.default`의 compile-time debug/simulator 값은 testable loader로 전달한다.

- [ ] **Step 10: iOS 부분 테스트 확인**

  Run: Xcode가 있는 환경에서 새 테스트 세 클래스 실행. Expected: 모두 PASS.

- [ ] **Step 11: 커밋**

  ```bash
  git add ios/Core/YouTube/YouTubeVideoIdentity.swift ios/Core/Networking/YouTubeTranscriptService.swift ios/Core/Networking/AppConfig.swift ios/Config/Backend.xcconfig ios/NoteAppTests/YouTubeVideoIdentityTests.swift ios/NoteAppTests/YouTubeTranscriptServiceTests.swift ios/NoteAppTests/AppConfigTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: iOS 공유 수집 기반 계약 추가"
  ```

### Task 4: App Group SwiftData 저장소와 route 확인 처리

**Files:**
- Create: `ios/Core/Storage/ContentNote.swift`
- Create: `ios/Core/Storage/PendingNoteRoute.swift`
- Create: `ios/Core/Storage/SharedModelContainer.swift`
- Create: `ios/Core/Storage/SharedStoreLock.swift`
- Create: `ios/Core/Storage/ContentNoteRepository.swift`
- Create: `ios/NoteAppTests/ContentNoteRepositoryTests.swift`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces: `ContentNoteDraft`, `StoredContentNote`, `SaveNoteOutcome.saved(StoredContentNote)`, `SaveNoteOutcome.alreadySaved(StoredContentNote)`.
- `ContentNote`/draft fields: `id`, `sourceKey`, `sourceType`, `videoId`, `sourceURL`, `canonicalURL`, `title`, `transcriptId`, `transcriptText`, `transcriptLanguageCode`, `transcriptIsGenerated`, `createdAt`; `PendingNoteRoute` fields: `id`, `noteId`, `createdAt`.
- Produces: `SharedModelContainer.make(at storeURL: URL) throws`, `makeAppGroupContainer() throws`.
- Produces: `SharedStoreLock.withLock<T>(_ operation: () throws -> T) throws -> T`.
- Produces: `ContentNoteRepository.find(sourceKey:)`, `saveOrReuse(_:)`, `enqueueRoute(noteID:)`, `pendingRouteSnapshot()`, `acknowledge(routeIDs:)`.
- `PendingRouteSnapshot` carries immutable `routeIDs: [UUID]` and `note: StoredContentNote?`.

- [ ] **Step 1: model과 single-save 실패 테스트 작성**

  Temporary SQLite store를 사용해 새 draft 저장 결과가 note 하나와 route 하나이며 둘이 같은 note ID를 가리키는지 검증한다. `ContentNote`에 `@Attribute(.unique)`를 두지 않는다. Storage production files를 NoteApp Sources에, test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 2: model과 single-save 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `ContentNoteRepositoryTests`의 새 저장 테스트 실행.

  Expected: model/container/repository 미정의로 build FAIL.

- [ ] **Step 3: models/container/lock/repository 최소 구현**

  Lock file은 store와 같은 App Group directory의 `reforge-shared-store.lock`을 사용한다. `open`, blocking `flock(LOCK_EX)`, `defer`의 `LOCK_UN`/`close` 순서를 지킨다. 네트워크 작업은 lock 안에서 실행하지 않는다.

- [ ] **Step 4: 중복 경합과 기존 필드 불변 실패 테스트 작성**

  같은 SQLite URL을 여는 두 `ModelContainer`와 같은 lock URL을 사용해 동일 sourceKey draft를 동시에 저장한다. 결과는 note 1개, route 2개이며 UUID, 최초 URL, title, transcript, createdAt은 첫 저장 값이어야 한다.

- [ ] **Step 5: route snapshot race 실패 테스트 작성**

  snapshot 뒤 새 route를 저장하고 처음 snapshot의 `routeIDs`만 acknowledge한다. 새 route가 남는지, acknowledge 전 재생성한 repository에서 기존 route가 다시 보이는지, 최신 route가 missing note를 가리키면 `note == nil`로 반환되어 조용히 제거 가능한지 검증한다.

- [ ] **Step 6: 경합과 route 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `ContentNoteRepositoryTests` 전체 실행.

  Expected: 조건부 insert 또는 snapshot acknowledge 동작이 아직 없어 새 경합/race 테스트 FAIL.

- [ ] **Step 7: 중복·route semantics 최소 구현**

  모든 write마다 lock 획득 후 새 `ModelContext`를 만들고 sourceKey/route IDs를 다시 조회한다. 새 note와 route는 한 번의 `save()`에 포함하고 기존 note는 route만 추가한다. Acknowledge는 전달받은 IDs만 삭제한다.

- [ ] **Step 8: GREEN 확인**

  Run: Xcode가 있는 환경에서 `ContentNoteRepositoryTests` 실행. Expected: 모든 저장·경합·route 테스트 PASS.

- [ ] **Step 9: 커밋**

  ```bash
  git add ios/Core/Storage ios/NoteAppTests/ContentNoteRepositoryTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: App Group 콘텐츠 노트 저장소 추가"
  ```

### Task 5: Share ingestion coordinator

**Files:**
- Create: `ios/Core/Sharing/SharedURLInput.swift`
- Create: `ios/Core/Sharing/ShareTitleResolver.swift`
- Create: `ios/Core/Sharing/ShareIngestionCoordinator.swift`
- Create: `ios/NoteAppTests/ShareIngestionCoordinatorTests.swift`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Consumes: Tasks 3의 `YouTubeVideoIdentity`, `YouTubeTranscriptFetching`; Task 4의 `ContentNoteRepository`.
- Produces: `ShareIngestionResult.saved(noteID:)`, `.alreadySaved(noteID:)`; `ShareIngestionCoordinator.ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult`.
- `SharedURLInput` fields: `url: URL`, `sharedTitle: String?`.
- Title priority: non-empty shared title, 1.5초 제한의 oEmbed title, canonical URL string.

- [ ] **Step 1: 새 영상과 중복 영상 실패 테스트 작성**

  실제 temporary repository와 stub external services를 사용한다. 새 영상은 transcript client 1회, note 1개, route 1개, `.saved`; 재공유는 transcript/title network 0회, note 1개, route 추가, `.alreadySaved`를 검증한다. Sharing production files를 NoteApp Sources에, test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 2: 새 영상과 중복 영상 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `ShareIngestionCoordinatorTests`의 success/duplicate 테스트 실행.

  Expected: coordinator 미정의로 build FAIL.

- [ ] **Step 3: 최소 coordinator 구현**

  사전 조회는 network 회피용이다. 최종 중복 판정은 `saveOrReuse` lock 내부 재조회 결과만 신뢰한다. transcript와 title은 동시에 시작하며 title은 1.5초 뒤 canonical URL fallback을 사용한다. Draft에는 input의 최초 URL을 `sourceURL`, identity의 정규 URL을 `canonicalURL`로 각각 넣는다.

- [ ] **Step 4: 실패·취소·title fallback·경합 테스트 작성**

  잘못된 URL, transcript 오류, response video ID 불일치, save 전 Task cancellation, repository save 오류는 성공 result와 note/route가 없어야 한다. Title timeout은 canonical URL 제목으로 note 1개와 route 1개를 저장하고 `.saved`여야 한다. Save 호출이 시작된 뒤 취소가 관찰돼도 coordinator가 저장된 note/route를 삭제하지 않는지 검증한다. 두 coordinator 동시 실행도 Task 4의 필드 불변을 유지해야 한다.

- [ ] **Step 5: 실패·취소·경합 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `ShareIngestionCoordinatorTests` 전체 실행.

  Expected: cancellation/video ID/save error 경계 중 미구현 branch 때문에 FAIL.

- [ ] **Step 6: 오류·취소 경계 최소 구현**

  Transcript response의 video ID를 identity와 비교하고, cancellation을 save 전에 다시 확인한다. Save 호출 뒤에는 cancellation cleanup을 하지 않는다. Repository 오류는 그대로 전달하고 success result를 만들지 않는다. Title timeout은 transcript 성공을 실패로 바꾸지 않고 canonical URL을 사용한다.

- [ ] **Step 7: GREEN 확인**

  Run: Xcode가 있는 환경에서 `ShareIngestionCoordinatorTests`와 Task 4 저장소 테스트 실행. Expected: 모두 PASS.

- [ ] **Step 8: 커밋**

  ```bash
  git add ios/Core/Sharing ios/NoteAppTests/ShareIngestionCoordinatorTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: 공유 영상 수집 coordinator 추가"
  ```

### Task 6: Share Extension target과 상태 UI

**Files:**
- Create: `ios/ShareExtension/Info.plist`
- Create: `ios/ShareExtension/ShareExtension.entitlements`
- Create: `ios/Core/Sharing/ShareInputLoader.swift`
- Create: `ios/Core/Sharing/ShareExtensionViewModel.swift`
- Create: `ios/ShareExtension/ShareViewController.swift`
- Create: `ios/App/NoteApp.entitlements`
- Create: `ios/NoteAppTests/ShareInputLoaderTests.swift`
- Create: `ios/NoteAppTests/ShareExtensionViewModelTests.swift`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj:1-561`

**Interfaces:**
- Consumes: Tasks 3–5의 공용 identity, config, network, storage, coordinator.
- Produces: `ShareInputLoader.load(from extensionItems: [NSExtensionItem]) async throws -> SharedURLInput`.
- Produces: `ShareExtensionViewModel.run(input:) async`, `statusText`, `isLoading`, injected `complete`/`cancel` closures.
- Share target bundle ID: `com.andrewkim.noteapp.share`; activation: `public.url` 최대 1개.

- [ ] **Step 1: item-provider 로딩 실패 테스트 작성**

  URL attachment 하나와 `attributedTitle`이 `SharedURLInput`으로 변환되는지 검증한다. URL 없음, 두 번째 비-URL attachment, provider load 오류, cancellation은 안전한 오류 또는 취소가 되어야 한다. 이 단계에서 두 shared production 파일을 NoteApp Sources에, test 파일을 NoteAppTests Sources에 등록해 RED가 실제 test target을 compile하게 한다.

- [ ] **Step 2: extension 상태·종료 실패 테스트 작성**

  새 영상과 중복 영상은 정확한 성공 문구를 먼저 publish한 뒤 complete closure를 한 번 호출해야 한다. transcript 미제공/provider 실패는 정확한 기존 문구를 publish하고 complete를 호출하지 않아야 한다. 잘못된 input, 사용자 cancellation, repository save 실패는 성공 문구 없이 cancel closure만 호출해야 한다. 늦은 completion은 cancellation 뒤 UI를 바꾸지 않아야 한다. 이 test 파일도 같은 단계에서 NoteAppTests Sources에 등록한다.

- [ ] **Step 3: loader와 상태 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `ShareInputLoaderTests`와 `ShareExtensionViewModelTests` 실행.

  Expected: loader/view model/controller contract 미정의로 build FAIL.

- [ ] **Step 4: loader, view model, 얇은 controller 구현**

  Controller는 label과 spinner만 사용한다. 새 버튼·상세 화면은 없다. `Saved to Reforge` 또는 `Already saved`를 렌더한 뒤 `completeRequest`; transcript 미제공과 provider 실패만 승인된 문구를 같은 label에 표시한다. 잘못된 input, 사용자 취소, 저장 실패는 새 문구 없이 `cancelRequest`로 종료한다. `viewWillDisappear`/deinit에서 진행 Task를 cancel한다.

- [ ] **Step 5: target, embed phase, entitlements, shared config 추가**

  App과 extension 모두 `group.com.andrewkim.noteapp` entitlement를 사용한다. App target에 `Embed App Extensions` copy phase와 extension dependency를 추가한다. Extension source phase에는 필요한 Core files, shared loader/view model, `ShareViewController`만 넣고 App UI는 넣지 않는다. 두 bundle의 `NOTEAPP_BACKEND_BASE_URL`은 같은 `Backend.xcconfig` setting을 Info.plist로 전달한다. ATS 전체 허용은 추가하지 않는다.

- [ ] **Step 6: project/target 정적 검증과 Xcode build**

  Run: `plutil -lint ios/ShareExtension/Info.plist ios/ShareExtension/ShareExtension.entitlements ios/App/NoteApp.entitlements`

  Expected: 세 파일 모두 OK.

  Run: `xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/reforge-derived-data build`

  Expected: NoteApp build 성공, built app의 `PlugIns` 아래 Share Extension `.appex` 포함.

- [ ] **Step 7: 커밋**

  ```bash
  git add ios/Core/Sharing/ShareInputLoader.swift ios/Core/Sharing/ShareExtensionViewModel.swift ios/ShareExtension ios/App/NoteApp.entitlements ios/NoteAppTests/ShareInputLoaderTests.swift ios/NoteAppTests/ShareExtensionViewModelTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: iOS Share Extension target 추가"
  ```

### Task 7: 다음 앱 활성화와 Home 상태 세대 연결

**Files:**
- Create: `ios/App/PendingNoteRouter.swift`
- Create: `ios/NoteAppTests/HomeViewModelTests.swift`
- Create: `ios/NoteAppTests/PendingNoteRouterTests.swift`
- Modify: `ios/App/NoteApp.swift:12-31`
- Modify: `ios/App/RootView.swift:10-24`
- Modify: `ios/Features/Home/HomeViewModel.swift:12-199`
- Modify: `ios/Features/Home/HomeView.swift:18-27,119-121,440-451`
- Modify: `ios/NoteApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Consumes: Task 4의 `pendingRouteSnapshot`, `acknowledge`; `StoredContentNote`.
- Produces: `HomeViewModel.applySharedNote(_ note: StoredContentNote)`, read-only `inputGeneration: UInt64`.
- Produces: `PendingNoteRouter.consumeLatest(apply: (StoredContentNote) throws -> Void) throws`.

- [ ] **Step 1: Home 초기화 실패 테스트 작성**

  Public input methods와 controllable fake services로 analysis result, error, unavailable reason, loading/progress, submitted URL/title 상태를 만든 뒤 shared note를 적용한다. URL/title만 새 값이며 나머지는 초기값, `isLoading == false`, 추가 analyze 호출 0회, input generation 증가를 검증한다. 새 HomeViewModel test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 2: 늦은 callback 실패 테스트 작성**

  continuation 기반 fake service로 이전 analyze를 보류한다. shared note 적용 뒤 이전 progress, success, error를 순서별로 재개해도 새 URL/title이 유지되고 result/error/loading이 다시 나타나지 않아야 한다. 보류 중인 oEmbed title도 같은 방식으로 무시해야 한다.

- [ ] **Step 3: Home 상태 세대 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `HomeViewModelTests` 실행.

  Expected: `applySharedNote`/`inputGeneration` 미정의 또는 늦은 callback이 상태를 덮어써 FAIL.

- [ ] **Step 4: HomeViewModel/HomeView 최소 변경**

  `applySharedNote`에서 auto-fill Task cancel, generation 증가, 모든 이전 상태 초기화, 저장 title 주입을 한 동기 전환으로 수행한다. `analyze`와 progress는 시작 generation을 캡처하고 모든 state write 전에 일치 여부를 검사한다. `HomeView`는 generation 변경 시 category 확장과 keyword selection을 초기화한다.

- [ ] **Step 5: route 적용·확인 순서 실패 테스트 작성**

  Router는 snapshot의 최신 note를 먼저 apply하고 성공 뒤 해당 `routeIDs`만 acknowledge해야 한다. apply가 throw하거나 process가 ack 전 멈춘 경우 route가 남고, snapshot 중 새 route는 삭제되지 않으며, missing note snapshot은 Home을 바꾸지 않고 해당 orphan IDs만 지워야 한다. Router production file을 NoteApp Sources에, test file을 NoteAppTests Sources에 등록한다.

- [ ] **Step 6: route 테스트 RED 확인**

  Run: Xcode가 있는 환경에서 `PendingNoteRouterTests` 실행.

  Expected: router 미정의로 build FAIL.

- [ ] **Step 7: app scene 연결 구현**

  `RootView`가 `HomeViewModel`을 소유하고 `HomeView`는 `@ObservedObject`로 받는다. `scenePhase == .active`에서 router를 한 번 실행한다. `NoteApp`은 shared container/repository/router를 구성해 RootView에 주입한다. 자동 Analyze는 호출하지 않는다.

- [ ] **Step 8: GREEN 확인**

  Run: Xcode가 있는 환경에서 `HomeViewModelTests`, `PendingNoteRouterTests`, 기존 `AnalyzeModelsTests` 실행. Expected: 모두 PASS.

- [ ] **Step 9: 커밋**

  ```bash
  git add ios/App/NoteApp.swift ios/App/RootView.swift ios/App/PendingNoteRouter.swift ios/Features/Home/HomeViewModel.swift ios/Features/Home/HomeView.swift ios/NoteAppTests/HomeViewModelTests.swift ios/NoteAppTests/PendingNoteRouterTests.swift ios/NoteApp.xcodeproj/project.pbxproj
  git commit -m "feat: 공유 노트를 Home 활성화 흐름에 연결"
  ```

### Task 8: 전체 검증과 기획 적합성 확인

**Files:**
- Modify only if verification exposes a tested defect: files owned by Tasks 1–7 plus matching tests.

**Interfaces:**
- Consumes: 모든 이전 task 결과.
- Produces: backend 전체 테스트, iOS 전체 테스트/build, entitlement·App Group·embedded extension 증거, 수동 실기기 체크리스트.

- [ ] **Step 1: backend 전체 검증**

  Run: `cd backend-fastapi && .venv/bin/pytest -q`

  Run: `cd backend-fastapi && .venv/bin/ruff check app tests`

  Expected: 둘 다 exit 0. Opt-in PostgreSQL test가 skip되면 정확한 test 이름과 이유를 기록한다.

- [ ] **Step 2: iOS 전체 테스트와 두 target build**

  Run: `xcodebuild -showdestinations -project ios/NoteApp.xcodeproj -scheme NoteApp`; 정상 simulator UDID가 있으면 `SIMULATOR_ID`로 선택한다. 모든 xcodebuild command는 `-derivedDataPath /tmp/reforge-derived-data`를 사용한다.

  Run when simulator is available: `xcodebuild test -project ios/NoteApp.xcodeproj -scheme NoteApp -destination "platform=iOS Simulator,id=$SIMULATOR_ID" -derivedDataPath /tmp/reforge-derived-data`

  Fallback when CoreSimulator mismatch remains: `xcodebuild build-for-testing -project ios/NoteApp.xcodeproj -scheme NoteApp -destination "generic/platform=iOS Simulator" -derivedDataPath /tmp/reforge-derived-data CODE_SIGNING_ALLOWED=NO`

  Run: `xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp -sdk iphonesimulator -configuration Release CODE_SIGNING_ALLOWED=NO -derivedDataPath /tmp/reforge-derived-data build NOTEAPP_BACKEND_BASE_URL=https://example.invalid`

  Expected: simulator가 정상일 때 전체 XCTest PASS, 항상 Debug/Release 또는 build-for-testing compile 성공. `example.invalid`은 build-time HTTPS 검증용이며 배포 endpoint로 사용하지 않는다. CoreSimulator mismatch로 test 실행이 불가능하면 PASS로 간주하지 않는다.

- [ ] **Step 3: 무서명 simulator artifact 설정 검증**

  Built app/appex의 `plutil -p Info.plist`와 build settings를 읽어 extension point, URL activation rule, 같은 backend URL 주입을 확인한다. 앱 bundle의 `PlugIns`에 `.appex`가 하나 존재해야 한다. `CODE_SIGNING_ALLOWED=NO` 산출물에는 `codesign` entitlement 검증을 사용하지 않는다.

- [ ] **Step 4: 서명된 device build entitlement 검증**

  승인된 development team으로 서명된 device build를 만든 뒤 app/appex 각각에 `codesign -d --entitlements :-`를 실행해 `group.com.andrewkim.noteapp`이 모두 포함되는지 확인한다. Provisioning 또는 device가 없으면 완료로 숨기지 말고 정확한 blocker로 보고한다.

- [ ] **Step 5: 실기기 수동 확인**

  승인된 개발 team과 접근 가능한 LAN/HTTPS backend URL로 YouTube 앱 공유 대상 노출, 새 영상 저장, URL 변형 재공유, transcript 미제공, provider 실패, 사용자 취소, 저장 후 앱 재진입을 확인한다. 실기기 검증 전에는 기능을 완전 검증했다고 보고하지 않는다.

- [ ] **Step 6: 기획 적합성 대조**

  설계의 포함/제외, 세 사용자 흐름, 정확한 네 문구, containing app 미실행, 자동 Analyze 미실행, My Notes/상세/재시도 미추가를 diff와 실행 결과에 각각 연결한다. `구현 검증`, `기획 적합성 검증`, `기획 대비 차이`, `해결되지 않은 충돌`, `근거 없는 추가 요소`를 최종 보고에 분리한다.

- [ ] **Step 7: 완료 전 learning gate와 최종 커밋 판단**

  `capturing-work-learnings`를 실행해 비자명한 실패/교훈이 있을 때만 `docs/solutions/` 기록을 추가한다. 수정이 생겼다면 관련 테스트를 다시 RED/GREEN 검증하고 task-owned 파일만 커밋한다. Push, PR, merge는 하지 않는다.

# iOS LLM Context

이 문서는 Reforge 저장소의 현재 iOS 앱 구현을 다른 LLM이 빠르게 이해하고 이어서 작업할 수 있도록 정리한 설명문이다.

## 한 줄 요약

현재 iOS 앱은 SwiftUI로 만든 `NoteApp` 클라이언트이며, 사용자가 YouTube URL을 붙여넣으면 YouTube 제목과 썸네일을 자동으로 가져오고, 백엔드 `/analyze?stream=progress` API를 호출해 영상 자막 기반 카테고리/키워드 분석 결과를 화면에 보여준다.

## 앱 목적

- 입력: YouTube 영상 URL
- 자동 보조: YouTube oEmbed API로 영상 제목을 자동 채움
- 분석 요청: 로컬 또는 설정된 백엔드에 영상 제목과 URL을 전송
- 진행 상태: Server-Sent Events(SSE) 스트림으로 분석 단계 메시지 표시
- 결과 표시: 백엔드가 반환한 카테고리와 키워드를 선택형 pill UI로 보여주고, 선택한 키워드는 단계별 설명(level1, level2, level3)으로 확장 가능하게 표시

## 기술 스택

- SwiftUI 기반 네이티브 iOS 앱
- Swift Concurrency(`async/await`, `Task`)
- Combine(`ObservableObject`, 키보드 notification 처리)
- URLSession 네트워킹
- 최소 iOS 타깃: iOS 17.6
- Xcode 프로젝트: `ios/NoteApp.xcodeproj`
- 앱 번들 ID: `com.andrewkim.noteapp`

## 주요 파일 구조

```text
ios/
  App/
    NoteApp.swift
    RootView.swift
  Core/
    Networking/
      AppConfig.swift
      AnalyzeModels.swift
      AnalyzeService.swift
      YouTubeOEmbedService.swift
  Features/
    Home/
      HomeView.swift
      HomeViewModel.swift
      AnalyzeResultView.swift
  Resources/
    Assets.xcassets/
```

## 앱 진입 흐름

1. `NoteApp.swift`
   - 앱의 `@main` 진입점이다.
   - `URLSessionAnalyzeService(config: .default)`와 `YouTubeOEmbedService()`를 생성한다.
   - 서비스 초기화 실패 시 `fatalError`로 앱을 중단한다.
   - `RootView`에 두 서비스를 주입한다.

2. `RootView.swift`
   - `NavigationStack`을 만들고 `HomeView`를 첫 화면으로 띄운다.
   - `HomeViewModel`을 생성하면서 `AnalyzeService`, `YouTubeTitleService`를 주입한다.

3. `HomeView.swift`
   - 실제 사용자 화면이다.
   - 하단 floating input bar에서 YouTube URL을 입력받는다.
   - URL이 입력되면 제목/썸네일 영역을 보여준다.
   - 분석 결과가 있으면 카테고리 pill, 키워드 pill, 선택 키워드 리스트를 표시한다.
   - 분석 중에는 전체 화면 로딩 overlay와 진행 단계 indicator를 보여준다.

4. `HomeViewModel.swift`
   - 화면 상태와 비즈니스 흐름을 담당한다.
   - YouTube URL 검증, 제목 자동 채움, 분석 API 호출, 에러 메시지, 분석 결과 상태를 관리한다.

## 화면 UX 흐름

1. 초기 상태
   - 화면 중앙에 `Add a YouTube link to get started` 안내 문구가 보인다.
   - 하단에는 `Paste YouTube URL` 입력 bar가 떠 있다.

2. URL 입력
   - 사용자가 하단 bar에 YouTube URL을 입력한다.
   - `HomeViewModel.handleYouTubeLinkChange()`가 호출된다.
   - URL이 YouTube 링크이면 0.5초 debounce 후 `YouTubeOEmbedService.checkAvailability()`가 실행된다.
   - 영상이 사용 가능하면 제목이 자동으로 `titleInput`에 들어간다.
   - 영상이 비공개/삭제/제한 상태이면 사용자용 에러 메시지를 표시한다.

3. 제목/썸네일 표시
   - 유효한 YouTube URL이고 영상 사용 불가 상태가 아니면 제목 입력 영역이 보인다.
   - 썸네일은 `https://img.youtube.com/vi/{videoID}/hqdefault.jpg` 형식으로 만든다.
   - 지원 URL 형식은 일반 `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/shorts/...`, `youtube.com/embed/...`이다.

4. 분석 실행
   - 사용자가 URL 입력 field에서 submit/go를 누르면 `HomeViewModel.analyze()`가 실행된다.
   - 제목과 YouTube URL을 검증한다.
   - `AnalyzeService.analyzeYouTube(title:youtubeUrl:onProgress:)`로 백엔드 요청을 보낸다.
   - 분석 중에는 `isLoading = true`가 되고 로딩 overlay가 표시된다.

5. 분석 결과 표시
   - 백엔드가 `AnalyzeResponse`를 반환하면 `analysisResult`에 저장된다.
   - 결과의 `categories`를 상단 horizontal pill 목록으로 표시한다.
   - 카테고리를 누르면 해당 카테고리의 키워드 pill들이 flow layout으로 나온다.
   - 키워드 pill을 누르면 선택 목록에 추가된다.
   - 선택된 키워드는 `term: level1 설명` 형태로 표시된다.
   - `expand` 버튼을 누르면 level1 -> level2 -> level3 설명으로 확장된다.
   - 각 키워드에는 `source.ref` URL을 timestamp label로 바꾼 링크가 붙는다.

## 상태 모델

`HomeViewModel`의 핵심 `@Published` 상태:

- `titleInput`: 영상 제목 입력값. oEmbed 성공 시 자동 채움.
- `youtubeLink`: 사용자가 입력한 YouTube URL.
- `isLoading`: 분석 요청 진행 여부.
- `loadingStage`: 백엔드 SSE stage 값. 로딩 indicator 위치 계산에 사용.
- `loadingStatusMessage`: 백엔드 SSE message 값. 로딩 overlay 문구에 사용.
- `errorMessage`: 사용자에게 보여줄 에러 문구.
- `analysisResult`: 분석 성공 시 저장되는 `AnalyzeResponse`.
- `videoUnavailableReason`: oEmbed 기반 사전 검증 결과.

`HomeView`의 로컬 상태:

- `expandedCategoryId`: 현재 펼쳐진 카테고리의 stable ID.
- `selectedKeywordIdsByCategory`: 카테고리별 선택된 `candidateClippingId` 기반 keyword occurrence ID set.
- `keywordDisplayLevelByCategory`: 카테고리/키워드별 현재 설명 깊이(1, 2, 3).
- `focusedField`: 제목 입력 field 또는 YouTube URL 입력 field 포커스.

## 백엔드 설정

`AppConfig.default`는 백엔드 base URL을 아래 순서로 결정한다.

1. 런타임 환경 변수 `NOTEAPP_BACKEND_BASE_URL`
2. Info.plist key `NOTEAPP_BACKEND_BASE_URL`
3. 기본값 `http://localhost:3000`

iOS 앱은 현재 `POST {baseURL}/analyze?stream=progress`를 호출한다.

응답의 카테고리는 `categoryId`, 키워드는 `candidateClippingId`를 identity로 사용한다. 동일한 `term`이 한 카테고리에 여러 번 존재할 수 있으므로 title이나 term을 SwiftUI identity 또는 선택 상태 key로 사용하지 않는다. 새 FastAPI 응답의 `sources`는 같은 contextual occurrence를 뒷받침하는 source만 포함하며, `source`는 primary source이다. NestJS rollback 응답처럼 ID와 `sources`가 없는 legacy payload는 transcript/category/keyword position으로 계산한 deterministic fallback ID를 사용한다.

## 분석 요청/응답 계약

요청 body는 `AnalyzeRequest` 모델을 JSON으로 인코딩한다.

```json
{
  "type": "youtube",
  "title": "영상 제목",
  "youtubeUrl": "https://www.youtube.com/watch?v=..."
}
```

응답 모델은 `AnalyzeResponse`이다.

```json
{
  "transcriptId": "uuid",
  "sourceType": "youtube",
  "categories": [
    {
      "title": "카테고리 제목",
      "keywords": [
        {
          "term": "키워드",
          "brief": "짧은 설명",
          "level1": "가장 짧은 설명",
          "level2": "중간 설명",
          "level3": "자세한 설명",
          "source": {
            "type": "youtube",
            "ref": "https://www.youtube.com/watch?v=...&t=123s"
          }
        }
      ]
    }
  ],
  "expiresInSeconds": 3600,
  "videoId": "YouTube video id"
}
```

## SSE 처리 방식

`URLSessionAnalyzeService`는 `Accept: text/event-stream` 헤더와 `stream=progress` query를 사용한다.

처리하는 SSE event:

- `started`, `progress`, `completed`
  - `AnalyzeProgressUpdate`로 decode한다.
  - `stage`, `message`를 받아 로딩 UI를 갱신한다.
- `result`
  - `AnalyzeResponse`로 decode한다.
  - 응답이 `{ data: ... }` 또는 `{ result: ... }` wrapper에 들어와도 처리한다.
- `error`
  - `AnalyzeStreamErrorResponse`로 decode한 뒤 `AnalyzeServiceError.backendError`로 변환한다.

SSE가 아닌 일반 JSON 응답이 와도 `AnalyzeResponse` decode를 시도한다. 또한 여러 JSON object가 붙어서 온 경우를 대비해 문자열에서 JSON object를 추출하는 fallback도 있다.

## 에러 처리

`AnalyzeServiceError.errorDescription`에서 백엔드 error code를 사용자 메시지로 변환한다.

중요한 code 매핑:

- `YOUTUBE_VIDEO_UNAVAILABLE`: 영상 비공개/숨김/삭제
- `YOUTUBE_URL_INVALID`, `INVALID_YOUTUBE_URL`: 잘못된 YouTube URL
- `TRANSCRIPT_UNAVAILABLE`: 영상은 있으나 자막 없음
- `TRANSCRIPT_PROVIDER_RATE_LIMITED`, `OPENAI_QUOTA_OR_RATE_LIMIT`: rate limit
- `TRANSCRIPT_PROVIDER_ERROR`, `TRANSCRIPT_FETCH_FAILED`: 자막 provider 실패
- `PYTHON_DEPENDENCY_MISSING`, `PYTHON_RUNTIME_ERROR`: 백엔드 Python 환경 문제
- `OPENAI_*`: 백엔드 OpenAI 분석 실패

YouTube oEmbed 사전 검증은 아래 HTTP 상태를 별도로 처리한다.

- `401`: private/restricted
- `404`: not found/removed
- `429`: rate limited
- 그 외 비정상 상태: unknown

## UI 구성 상세

`HomeView`는 `GeometryReader` 안에 `ZStack`을 두고 다음을 겹쳐 배치한다.

- 메인 `ScrollView`
- 하단 floating YouTube URL 입력 bar
- 분석 중 loading overlay

주요 UI 요소:

- 제목 입력 영역: `viewModel.shouldShowTitleArea`가 true일 때 표시
- 썸네일: `AsyncImage`로 YouTube thumbnail URL 로딩
- 카테고리 탭: horizontal `ScrollView` 안의 capsule button
- 키워드 pill: custom `PillFlowLayout`으로 줄바꿈 배치
- 선택 키워드 리스트: 카테고리별 group, timestamp link, expand, remove button
- 하단 입력 bar: keyboard 높이에 맞춰 위로 이동

`KeyboardObserver`는 `UIResponder.keyboardWillChangeFrameNotification`과 `keyboardWillHideNotification`을 Combine publisher로 구독해 키보드 높이와 animation duration을 계산한다.

## 현재 구현상 주의점

- `AnalyzeResultView.swift`는 존재하지만 현재 `HomeView`에서 navigation destination으로 연결되어 있지 않다. 과거 또는 디버그용 상세 리스트 화면으로 보인다.
- `SwiftData`가 `NoteApp.swift`에 import되어 있지만 현재 실제 모델/저장소로 쓰이지 않는다.
- `ios/Core/Extensions`, `ios/Core/Storage`, `ios/UI/Components`, `ios/UI/Theme` 디렉터리는 현재 비어 있는 구조성 폴더로 보인다.
- `ios/.env.example`에는 `OPENAI_API_KEY`가 있지만 현재 iOS 코드에서 직접 읽지 않는다. OpenAI API key는 백엔드에서 필요한 값이다.
- 앱은 현재 manual text 분석이 아니라 YouTube URL 분석만 사용한다. 백엔드 쪽에는 manual source 지원 흔적이 있지만 iOS request는 항상 `type: "youtube"`이다.
- URL 검증은 host에 `youtube.com` 또는 `youtu.be`가 포함되는지만 확인한다. 매우 엄격한 도메인 검증은 아니다.
- `timestampLabel(from:)`는 `source.ref` URL query의 `t` 값만 읽는다. `t=123s` 형태를 예상한다.

## 다른 LLM에게 작업을 맡길 때 주면 좋은 지시

다른 LLM에게는 아래 내용을 함께 전달하면 된다.

```text
이 저장소의 iOS 앱은 SwiftUI 기반 NoteApp입니다. 핵심 화면은 ios/Features/Home/HomeView.swift이고, 상태/비즈니스 로직은 ios/Features/Home/HomeViewModel.swift에 있습니다. 앱은 YouTube URL을 입력받아 YouTube oEmbed로 제목을 자동 채우고, ios/Core/Networking/AnalyzeService.swift의 URLSessionAnalyzeService를 통해 POST /analyze?stream=progress 백엔드 API를 SSE로 호출합니다. 응답 모델은 ios/Core/Networking/AnalyzeModels.swift의 AnalyzeResponse/AnalyzeCategory/AnalyzeKeyword입니다.

수정할 때는 기존 구조를 유지하세요:
- 화면 상태는 HomeViewModel의 @Published 값으로 관리합니다.
- 네트워크 계약 변경은 AnalyzeModels.swift와 AnalyzeService.swift를 함께 반영합니다.
- YouTube 제목/가용성 확인은 YouTubeOEmbedService.swift에 둡니다.
- HomeView는 UI 조합과 로컬 선택 상태만 담당하게 유지합니다.
- 백엔드 base URL은 AppConfig.swift의 NOTEAPP_BACKEND_BASE_URL env/plist/default 순서를 따릅니다.
- 분석 진행 단계는 started, fetching_transcript, sanitizing_transcript, transcript_ready, storing_transcript, analyzing_categories, completed를 기준으로 UI에 표시됩니다.
```

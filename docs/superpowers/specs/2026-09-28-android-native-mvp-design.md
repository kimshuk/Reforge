# Android 네이티브 MVP 설계

## 목적

Android 사용자가 YouTube 공유 대상에서 Reforge를 선택하면 앱이 즉시 열리고, 공유된 영상을 검증해 자막이 있는 콘텐츠 노트로 저장한 뒤 해당 노트 상세를 표시한다. Android MVP는 현재 iOS 노트 보관함의 데이터 규칙과 사용자 상태 전이를 유지하되, App Group·Share Extension·pending route처럼 iOS 제약 때문에 생긴 구조는 복제하지 않는다.

이번 단계는 최종 시각 디자인이 아니라 사용자 흐름과 데이터 안정성을 검증하는 MVP다. 화면은 기본 Material 3 구성요소를 사용하고, 향후 디자인 시스템을 적용할 때 도메인·데이터 계층을 바꾸지 않고 표현 계층만 교체할 수 있게 분리한다.

## 구현 계약

### 근거 원본

- `docs/superpowers/specs/2026-09-28-ios-notes-library-design.md`
- 현재 iOS `ContentNote`, `ShareIngestionCoordinator`, `AppCoordinator`, My Notes·상세·휴지통 구현
- 이번 대화에서 승인한 Android 차이: 공유 대상 선택 즉시 앱 열기, UX 동등·Material 3 기본 UI, 기기 로컬 저장, 화면 이탈 시 가져오기 취소

### 포함

- `android/` 아래 Kotlin·Jetpack Compose 네이티브 앱
- application ID `com.andrewkim.reforge`
- 최소 지원 버전 Android 8.0(API 26); compile·target SDK는 구현 시점의 최신 안정 SDK인 API 37
- `ACTION_SEND` 기반 YouTube URL 공유 수신
- 공유 가져오기 진행 화면과 취소
- 기존 FastAPI transcript·analysis 계약 사용
- Room 기반 콘텐츠 노트, 활성 목록, 상세, 휴지통
- Home·My Notes 탭별 독립 탐색 스택
- 활성 중복 재사용, 휴지통 중복 복원 확인, 새 영상 저장
- 상세에서 명시적으로 시작하는 분석 흐름
- 휴지통 복원·영구 삭제·30일 만료 정리
- 기능별 단위·통합·Compose UI 테스트와 단일 에뮬레이터·실기기 확인

### 제외

- 계정, 로그인, 서버 노트 저장, iOS·Android 동기화
- Android Auto Backup, cloud backup, device-to-device DB 이전
- 공유만으로 자동 LLM 분석
- 백그라운드 큐, 완료 알림, 자동 재시도
- 최종 브랜드 디자인, 커스텀 디자인 시스템, 고급 애니메이션
- iOS 화면의 픽셀 단위 복제
- Android에서 불필요한 App Group·Share Extension·pending route 모방
- 백엔드 API의 기능 변경

### 성공 기준

- YouTube 앱에서 `공유 → Reforge`를 선택하면 Reforge가 가져오기 화면으로 열린다.
- 새 영상은 자막 확보와 로컬 저장이 모두 성공한 뒤에만 노트 상세로 이동한다.
- 활성 중복은 네트워크 요청 없이 기존 상세를 연다.
- 휴지통 중복은 `Restore / Cancel` 확인 전에는 아무 상태도 바꾸지 않는다.
- 가져오기 화면을 벗어나거나 새 공유가 들어오면 이전 작업을 취소하고 늦은 결과를 반영하지 않는다.
- 실패·취소·경합으로 부분 노트나 중복 노트가 남지 않는다.
- 앱 재실행 뒤 노트와 휴지통 상태가 유지된다.

## 승인된 사용자 흐름

### 일반 실행

앱은 `Home`과 `My Notes`를 최상위 목적지로 제공하고 각 탭의 탐색 스택을 독립적으로 유지한다. `My Notes`에서 활성 노트 목록, 노트 상세, 휴지통으로 이동한다. 공유 저장·활성 중복·복원 성공은 `My Notes` 탭을 선택하고 대상 상세를 연다. 화면의 정보 구조와 기능은 iOS와 동등하게 유지하되 Android의 내비게이션, 시스템 뒤로 가기, Material 3 구성요소를 사용한다.

### 새 영상 공유

1. 사용자가 YouTube에서 `공유 → Reforge`를 선택한다.
2. Android가 `ACTION_SEND`와 `text/plain` payload로 `MainActivity`를 연다.
3. 앱은 공유 전용 가져오기 화면을 첫 목적지로 표시한다.
4. 공유 text에서 지원하는 YouTube URL을 찾아 정확한 video ID와 canonical URL로 정규화한다. 같은 영상의 URL 변형이 여러 번 있으면 하나로 수렴하고 서로 다른 영상이 두 개 이상이면 잘못된 공유 입력으로 종료한다.
5. 활성·휴지통 어디에도 같은 `youtube:<videoId>`가 없으면 제목과 transcript를 요청한다.
6. transcript 응답의 video ID가 요청한 video ID와 같은지 확인한다.
7. transcript와 노트를 Room transaction으로 저장한다.
8. 저장이 끝난 뒤에만 가져오기 화면을 해당 노트 상세로 교체한다.
9. 공유 시점에는 LLM 분석을 시작하지 않는다.

### 활성 노트 중복 공유

1. canonical video ID로 활성 노트를 찾는다.
2. 제목·transcript·analysis 네트워크 요청을 하지 않는다.
3. 기존 노트의 데이터를 바꾸지 않고 해당 노트 상세를 연다.

### 휴지통 노트 중복 공유

1. canonical video ID로 휴지통 노트를 찾는다.
2. 네트워크 요청과 데이터 변경 없이 `This video is in Trash. Restore it?` 확인을 표시한다.
3. `Restore`: 같은 note ID, transcript, 최초 URL, 생성 시각을 유지해 복원한 뒤 해당 상세를 연다.
4. `Cancel`: 복원, 새 노트, route, 분석 없이 공유 흐름을 종료한다.
5. 휴지통 중복을 새 노트로 만드는 선택지는 MVP에 없다.

### 노트 분석

노트 상세의 `Analyze` 탭 자체를 사용자의 명시적 분석 시작으로 본다. 탭하면 그 순간 화면에 표시된 note의 제목과 canonical URL을 `AnalysisInputSnapshot`으로 캡처하고 Home 분석 화면으로 이동해 바로 기존 `/analyze` 요청을 시작한다. 클릭 직후 노트가 다른 경로에서 휴지통 이동·삭제돼도 전달된 snapshot으로 분석을 계속한다. 공유 저장만으로는 분석하지 않는다.

### 화면 이탈과 새 공유

- 가져오기 중 시스템 뒤로 가기는 현재 네트워크·저장 전 작업을 취소하고 이전 화면 또는 앱 밖으로 돌아간다.
- 저장 transaction이 시작되기 전에 취소가 관찰되면 노트를 만들지 않는다.
- transaction commit 뒤 취소가 도착하면 이미 완결된 노트를 삭제하지 않는다.
- 앱이 열린 상태에서 새 `ACTION_SEND`가 들어오면 이전 가져오기 job을 취소하고 새 입력 세대로 전환한다.
- 이전 입력의 progress·result·error는 새 입력 화면에 반영하지 않는다.

## 화면과 내비게이션

### 단일 Activity

`MainActivity` 하나와 Navigation Compose를 사용한다. 외부 공유가 기존 앱 task의 같은 Activity로 전달되도록 launcher Activity는 `singleTask`로 선언한다. cold start의 `onCreate`와 warm start의 `onNewIntent`가 동일한 `ShareIntentParser`를 호출하고, 유효한 공유 입력은 nav coordinator에 새 입력 세대로 전달한다.

Activity 재생성은 새 사용자 공유로 취급하지 않는다. launch intent는 `savedInstanceState == null`일 때 한 번만 소비하고 즉시 neutral launcher intent로 교체한다. `onNewIntent`로 도착한 실제 새 공유만 현재 generation을 교체한다. 가져오기 완료 상태에는 generation과 note ID를 함께 저장하고, 상세 navigation이 수락된 뒤에만 완료 상태를 확인 처리한다. 회전·process recreation에서는 완료 상세 이동을 복구할 수 있지만 이미 소비한 공유를 다시 요청하지 않는다.

### 목적지

| 목적지 | 역할 |
|---|---|
| Home | URL 직접 입력, 제목 확인, 분석 진행과 결과 표시 |
| Share Import | 공유 URL 검증, 가져오기 progress, 복원 확인, 오류 |
| My Notes | 활성 노트 최신순 목록과 휴지통 진입 |
| Note Detail | 제목, 썸네일, 원본 열기, transcript metadata·본문, Analyze, 휴지통 이동 |
| Trash | 삭제 시각 최신순 목록, 복원, 영구 삭제 |

최종 디자인 전까지 기본 Material 3 typography, color scheme, dialog, progress indicator, navigation component만 사용한다. 도메인 상태나 저장소 API가 Composable에 직접 들어가지 않게 screen state와 event interface를 둔다.

## 구성요소

### 공유·도메인

- `ShareIntentParser`: `ACTION_SEND`와 `text/plain`을 검증하고 공유 text에서 지원 URL을 추출한다.
- `YouTubeVideoIdentity`: 지원 host·path를 검증하고 11자 video ID, canonical URL, source key를 만든다.
- `ShareIngestionCoordinator`: active / trashed / absent 분기, transcript·title 요청, 응답 identity 확인, 저장 결과를 조율한다.
- `ShareImportViewModel`: 입력 세대, progress, 복원 확인, 오류, 완료 navigation 상태와 확인 처리를 관리한다.
- `YouTubeAvailabilityService`: oEmbed 401/404/429/기타 상태를 iOS와 같은 typed unavailable reason으로 보존한다. Home은 해당 상태와 기존 문구를 사용한다.
- `ShareTitleResolver`: 공유 수집에서만 availability 실패를 canonical URL fallback으로 축소한다.

### 데이터

- Room `ContentNoteEntity`와 DAO
- `ContentNoteRepository`: 조회, 조건부 저장, 휴지통 이동·복원·영구 삭제·만료 정리를 transaction으로 제공
- repository는 UI나 Android `Intent` 타입에 의존하지 않는다.

### 네트워크

- Retrofit/OkHttp 기반 `YoutubeTranscriptService`와 기존 analysis client
- Kotlin Coroutines로 취소를 전파한다.
- backend base URL은 build configuration으로 주입한다.
- 에뮬레이터 로컬 개발 주소는 `10.0.2.2`, 실기기는 LAN 또는 HTTPS 주소를 명시한다.
- release build는 주입된 HTTPS 주소를 요구하고 전체 cleartext 허용을 추가하지 않는다.

## 데이터 설계

`ContentNoteEntity`는 iOS `ContentNote`와 의미상 같은 필드를 가진다.

| 필드 | 역할 |
|---|---|
| `id: String` | UUID note ID |
| `sourceKey: String` | `youtube:<videoId>`, unique index |
| `sourceType: String` | `youtube` |
| `videoId: String` | canonical 중복 키 |
| `sourceUrl: String` | 최초 공유 URL |
| `canonicalUrl: String` | canonical YouTube URL |
| `title: String` | 공유 제목, metadata, canonical URL 순 fallback |
| `transcriptId: String` | backend transcript ID |
| `transcriptText: String` | 기기 내 영구 보관 원문 |
| `transcriptLanguageCode: String?` | 언어 코드 |
| `transcriptIsGenerated: Boolean?` | 자동 생성 여부 |
| `createdAt: Instant` | 최초 저장 시각 |
| `trashedAt: Instant?` | null이면 활성, 값이 있으면 휴지통 |

`sourceKey` unique index는 최종 중복 방어선이다. 새 노트 저장은 transaction 안에서 최신 상태를 다시 조회한다. 경합으로 unique constraint가 발생하면 기존 row를 다시 읽어 active면 기존 상세로, trashed면 복원 확인으로 수렴한다. 기존 row를 replace하거나 최초 필드를 갱신하지 않는다.

휴지통 이동은 해당 note의 상태 변경을 한 transaction으로 처리한다. 복원은 `trashedAt = null`만 바꾸며 다른 필드를 유지한다. 영구 삭제는 row를 삭제한다. `cutoff = now - 30 days`에서 `trashedAt <= cutoff`인 노트를 앱 시작, foreground 복귀, 휴지통 진입 때 정리한다. 별도 백그라운드 scheduler는 추가하지 않는다.

## 네트워크·저장 경계

- 활성·휴지통 사전 조회는 네트워크 회피용이다.
- 네트워크는 DB transaction 밖에서 실행한다.
- transcript 성공 전에는 임시 노트를 insert하지 않는다.
- 저장 직전 transaction 안에서 source key를 다시 조회한다.
- transcript response video ID가 요청 ID와 다르면 저장하지 않는다.
- 제목 요청 실패·제한 시간 초과는 canonical URL을 제목으로 사용하며 transcript 저장을 막지 않는다.
- 저장 성공 이후에만 완료 navigation 상태를 기록한다. My Notes 상세가 이를 수락한 뒤 같은 generation의 완료 상태만 확인 처리한다.

## 오류와 사용자 문구

| 상태 | 문구 | 동작 |
|---|---|---|
| 잘못된 공유 URL | `Please enter a valid YouTube URL.` | 저장 없이 `Back` |
| transcript 미제공 | `The video is available, but transcript is not available.` | 저장 없이 `Back` |
| provider·network 실패 | `Transcript provider failed. Please try again.` | 저장 없이 `Back` |
| 로컬 저장 실패 | `Couldn’t save this video. Please try again.` | 부분 저장 없이 `Back` |
| 휴지통 중복 | `This video is in Trash. Restore it?` | `Cancel / Restore` |

Home의 oEmbed availability는 iOS와 같은 문구를 사용한다: `This video is private or restricted.`, `This video was removed or is not found.`, `YouTube is rate-limiting checks right now. Please try again.`, `Unable to verify YouTube video availability.` 공유 수집은 이 상태를 사용자 오류로 확장하지 않고 제목 fallback에만 사용한다.

새 오류 화면에는 `Back`만 둔다. 재시도 버튼, 자동 재시도, 완료 알림은 추가하지 않는다. 알려진 backend 오류 코드는 위 문구로 매핑하고 raw exception, URL, stack trace를 사용자에게 노출하지 않는다.

## 생명주기·동시성

- ViewModel의 coroutine scope가 현재 가져오기 job을 소유한다.
- 각 공유 입력에 generation ID를 부여하고 state·effect 적용 전에 현재 generation과 비교한다.
- `onNewIntent`는 기존 job을 취소한 뒤 새 generation을 시작한다.
- 완료 navigation 상태도 generation을 포함한다. 화면은 적용 직전에 generation을 다시 확인하고 상세 전환을 수락한 뒤 확인 처리한다.
- 화면 이탈은 job을 취소하지만 process 전체의 다른 화면 작업은 취소하지 않는다.
- Room transaction은 짧게 유지하고 파일·네트워크 I/O를 포함하지 않는다.
- 동일 영상의 빠른 연속 공유는 DB unique index와 transaction 후 재조회로 하나의 note에 수렴한다.
- Activity 재생성은 기존 intent를 재소비하지 않는다. 저장 후 navigation 전 process가 종료되면 저장된 완료 상태가 동일 상세 이동을 복구한다.
- Room DB와 노트 데이터는 cloud backup과 device-to-device transfer 대상에서 제외한다.

## 검증 전략

엄격한 테스트 우선 개발은 적용하지 않는다. 기능 단위를 구현한 뒤 해당 단위의 자동 테스트를 같은 작업 묶음에서 추가하고, 완료 전 전체 회귀 검증을 실행한다.

### 단위 테스트

- watch, mobile, youtu.be, shorts URL 정규화와 잘못된 host·ID 거부
- share text의 URL 추출과 잘못된 action·MIME 거부
- active / trashed / absent 분기와 네트워크 호출 여부
- transcript response identity 불일치와 오류 매핑
- 입력 generation 변경 뒤 늦은 progress·result·error 무시

### Room 통합 테스트

- 새 영상 성공은 note 한 개만 저장
- 동시·연속 중복 저장도 하나의 source key로 수렴
- 기존 UUID, 최초 URL, transcript, createdAt 불변
- 휴지통 이동·복원·영구 삭제와 필드 보존
- `trashedAt <= cutoff` 30일 경계
- 실패·취소 시 부분 row 없음
- DB 재개방 뒤 활성·휴지통 상태 유지

### Compose·내비게이션 테스트

- 일반 실행과 공유 실행의 첫 목적지
- 가져오기 progress, 오류와 Back
- 휴지통 `Cancel / Restore`
- 저장 후 상세로 한 번만 이동
- 상세 `Analyze`가 Home으로 이동하며 분석을 한 번 시작
- 새 공유가 기존 가져오기 UI를 대체
- Home·My Notes 탭을 오가도 각 탭의 상세·휴지통 stack 유지
- 회전·process recreation 전후 공유 intent 재소비와 완료 navigation 중복 방지
- oEmbed 401/404/429/기타 상태의 typed 문구와 network·decode non-blocking 처리

### 빌드·수동 확인

- Gradle unit test, instrumented test, lint, debug build
- property 미설정·HTTP·HTTPS 조합의 Release URL guard와 merged manifest·backup rule 확인
- 단일 Android 에뮬레이터로 자동 테스트해 불필요한 병렬 device 생성을 피한다.
- 실제 Android 기기에서 YouTube 앱 공유 대상 노출, 새 영상, 활성 중복, 휴지통 복원·취소, 뒤로 가기, 앱 재진입을 확인한다.
- backend가 로컬이면 에뮬레이터 `10.0.2.2`와 실기기 LAN 접근을 각각 확인한다.

## 구현 검증과 기획 적합성 검증

### 구현 검증

코드가 정의된 계약대로 동작하는지는 자동 테스트, build, lint, 에뮬레이터·실기기 확인으로 검증한다. API fixture뿐 아니라 실제 공유 Intent와 lifecycle 재진입을 포함한다.

### 기획 적합성 검증

완료 전 iOS 노트 보관함 설계와 다음을 다시 대조한다.

- 공유 저장만으로 분석하지 않는가
- active / trashed / absent 분기가 같은가
- 휴지통 취소가 완전한 무변경인가
- 기존 note identity와 transcript를 재사용하는가
- 상세 `Analyze`만 분석을 시작하는가
- 30일 휴지통 정책이 같은가
- 승인되지 않은 알림·재시도·동기화·새 화면이 추가되지 않았는가

## 기획 대비 차이

- iOS는 Share Extension에서 저장하고 containing app을 강제로 열지 않지만 Android는 공유 대상 선택 즉시 `MainActivity`를 연다.
- iOS의 App Group, process 간 file lock, pending route는 Android 단일 앱·Room 구조에 필요하지 않다.
- Android는 전체 앱 화면에서 실패를 표시하므로 iOS의 조용한 extension 취소 대신 승인된 저장 실패 문구와 `Back`을 제공한다.
- 시각 표현은 iOS 복제가 아니라 기본 Material 3를 사용한다. 화면 목적과 상태 전이는 동등하다.

## 해결되지 않은 충돌

없음. 플랫폼 차이와 새 저장 실패 문구는 사용자 승인으로 해소했다.

## 근거 없는 추가 요소

없음. 계정·동기화·백그라운드 완료·알림·자동 재시도·최종 디자인은 추가하지 않는다.

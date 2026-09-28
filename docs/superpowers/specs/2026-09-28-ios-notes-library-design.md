# iOS 노트 보관함 MVP 설계

## 1. 목적과 기준점

이 문서는 YouTube 공유 수집 기능(PR #9, `feat/youtube-share-ingestion`) 위에 iOS 로컬 노트 보관함 MVP를 추가하기 위한 승인된 제품·기술 계약이다. 공유 확장으로 저장된 `ContentNote`를 앱에서 목록과 상세 화면으로 열람하고, 상세 화면에서 기존 분석 흐름을 명시적으로 시작하며, 휴지통에서 30일 동안 복원할 수 있게 한다.

구현은 PR #9의 공유 수집 모델, App Group 저장소, pending route, 기존 Home 분석 흐름을 기준으로 시작한다. 백엔드 계약 변경은 이 범위에 포함하지 않는다.

## 2. 구현 계약

### 2.1 포함 범위

| ID | 요구사항 | 근거 | 검증 방법 |
|---|---|---|---|
| NL-01 | 앱 하단에 `Home`, `My Notes` 탭을 제공하고 각 탭은 독립적인 탐색 스택을 가진다. | 승인된 화면 흐름 | UI 상태 테스트와 수동 탐색 |
| NL-02 | `My Notes`는 활성 노트를 생성일 최신순으로 표시한다. | 승인된 목록 정책 | 저장소 정렬 테스트와 목록 확인 |
| NL-03 | 상세 화면은 제목, 썸네일, 원본 YouTube 열기, 자막 메타데이터, 전체 자막, `Analyze`를 읽기 전용으로 표시한다. | 승인된 source-first 상세 | 상세 화면 테스트와 수동 확인 |
| NL-04 | 상세의 `Analyze` 한 번으로 Home 탭을 선택하고 해당 URL·제목을 적용한 뒤 기존 분석을 즉시 시작한다. | 승인된 분석 전환 | ViewModel·탐색 통합 테스트 |
| NL-05 | 활성 노트 삭제는 같은 노트를 참조하는 pending route와 함께 한 트랜잭션에서 휴지통으로 이동한다. | 승인된 데이터 일관성 정책 | 저장소 원자성 테스트 |
| NL-06 | 휴지통 노트는 복원 또는 즉시 영구 삭제할 수 있고, 삭제 시각 최신순으로 표시한다. | 승인된 휴지통 정책 | 저장소·화면 테스트 |
| NL-07 | 휴지통에서 30일이 지난 노트는 앱 시작, foreground 진입, 휴지통 진입 때 정리한다. | 승인된 보존 정책 | 경계값·생명주기 테스트 |
| NL-08 | 공유된 영상이 활성 노트면 네트워크 요청 없이 기존 노트의 상세 route를 추가하고 `Already saved`를 표시한다. | PR #9 기존 동작 유지 | Share Extension 회귀 테스트 |
| NL-09 | 공유된 영상이 휴지통에 있으면 `Restore` 확인 전까지 아무것도 변경하지 않는다. 복원을 승인하면 같은 노트를 복원하고 상세 route를 원자적으로 추가하며, 취소하면 공유 수집을 종료한다. | 승인된 중복 정책 | Share Extension 분기·원자성 테스트 |
| NL-10 | 공유된 영상이 존재하지 않을 때만 기존 자막 API 흐름으로 새 노트와 route를 저장한다. | PR #9 기존 동작 유지 | 수집 회귀 테스트 |
| NL-11 | 공유 route는 `My Notes` 탭을 선택하고 대상 상세를 연 뒤에만 확인 처리한다. | 승인된 route 정책 | route 경쟁 조건 테스트 |

### 2.2 제외 범위

- 검색, 정렬 방식 선택, 필터
- 노트·자막 편집
- 분석 결과 저장
- 내보내기와 공유
- 계정, 클라우드 동기화, 다중 기기 일관성
- Android 구현
- 백엔드 API 또는 데이터베이스 변경

## 3. 사용자 흐름

### 3.1 목록과 상세

1. 사용자가 `My Notes` 탭을 선택한다.
2. 활성 노트를 `createdAt` 내림차순으로 본다.
3. 행을 선택하면 해당 `ContentNote.ID`의 상세 화면으로 이동한다.
4. 상세 화면은 저장된 원본 정보와 자막을 읽기 전용으로 보여준다.
5. `Open in YouTube`는 저장된 canonical URL을 시스템 URL 열기로 전달한다.

활성 목록이 비어 있으면 `No saved notes yet.`를 표시한다.

### 3.2 상세에서 분석

1. 사용자가 상세 화면에서 `Analyze`를 누른다.
2. 앱은 Home 탭을 선택한다.
3. 저장된 canonical URL과 제목을 기존 Home 분석 입력에 적용한다.
4. 같은 사용자 동작의 연속 처리로 기존 분석을 즉시 시작한다.

공유 route로 상세가 열린 경우에도 자동 분석하지 않는다. 사용자가 `Analyze`를 눌러야 한다. 이전 분석의 늦은 진행·오류 callback이 새 입력 상태를 덮지 못하도록 기존 generation guard를 유지한다.

### 3.3 활성 노트를 휴지통으로 이동

상세 또는 목록의 삭제 액션은 아래 확인을 표시한다.

> Move this note to Trash? You can restore it for 30 days.

버튼은 `Cancel`, `Move to Trash`다. 승인하면 `trashedAt`을 현재 시각으로 설정하고 같은 노트를 가리키는 모든 pending route를 같은 저장 트랜잭션에서 삭제한다. 현재 상세가 삭제된 노트라면 상세를 닫고 활성 목록으로 돌아간다.

### 3.4 휴지통

`My Notes`에서 휴지통으로 진입한다. 휴지통은 `trashedAt` 내림차순으로 표시한다. 비어 있으면 `Trash is empty.`를 표시한다.

- `Restore`: `trashedAt = nil`로 바꾸고 사용자는 휴지통에 머문다. 복원된 행은 휴지통 목록에서 사라진다.
- `Delete`: 아래 확인 후 노트와 남은 pending route를 한 트랜잭션에서 영구 삭제한다.

> Delete this note permanently? This can’t be undone.

버튼은 `Cancel`, `Delete`다.

### 3.5 30일 자동 정리

정리 기준 시각을 `cutoff = now - 30 days`로 계산한다. `trashedAt <= cutoff`인 노트는 만료된 것으로 간주해 영구 삭제한다. 앱 시작, 앱의 foreground 전환, 휴지통 진입마다 정리를 시도한다. 백그라운드 작업은 추가하지 않는다.

정리 저장이 실패하면 부분 변경을 노출하지 않고 다음 생명주기 기회에 다시 시도한다. 사용자에게 새 오류 화면이나 알림은 추가하지 않는다.

### 3.6 YouTube 공유 분기

공유 확장은 canonical video ID를 만든 뒤 App Group 잠금 안에서 상태를 조회한다.

1. **활성 노트 존재**: 자막·제목 네트워크 요청 없이 기존 note ID의 pending route를 추가한다. `Already saved`를 표시하고 확장을 닫는다.
2. **휴지통 노트 존재**: 아래 확인을 표시하고 대기한다.
3. **노트 없음**: 기존 자막 수집 흐름으로 새 노트와 pending route를 저장한다.

휴지통 확인 문구는 다음과 같다.

> This video is in Trash. Restore it?

버튼은 `Cancel`, `Restore`다.

- `Restore`: 기존 note ID와 자막을 그대로 사용한다. 자막 API를 호출하지 않고 `trashedAt = nil` 변경과 pending route 추가를 같은 트랜잭션에서 저장한다. 성공 후 `Already saved`를 표시하고 닫는다.
- `Cancel`: 확장을 취소 완료한다. API 요청, 새 노트 생성, 복원, route 추가를 모두 하지 않는다.

휴지통 중복 공유에서 새 노트를 만드는 선택지는 MVP에 없다.

## 4. 화면 및 탐색 구조

앱 루트는 `TabView`와 탭별 독립 `NavigationStack`으로 구성한다.

```text
AppShell
├── Home NavigationStack
│   └── Home
└── My Notes NavigationStack
    ├── My Notes
    ├── Content Note Detail
    └── Trash
```

앱 수준 탐색 상태는 최소한 다음을 소유한다.

- `selectedTab`: Home 또는 My Notes
- `notesPath`: My Notes 스택의 route 배열
- 상세에서 분석을 시작하기 위한 note 전달 액션

pending route를 소비할 때는 최신 유효 route의 note ID를 기준으로 `selectedTab = .myNotes`와 `notesPath = [.detail(noteID)]`를 먼저 반영한다. 화면 상태가 이를 수락한 뒤 캡처했던 route ID만 확인 처리한다. 새 공유가 동시에 도착해도 캡처 이후 route는 삭제하지 않는다. 대상 노트가 없거나 이미 만료됐다면 해당 고아 route만 조용히 제거한다.

## 5. 데이터 모델과 저장소

### 5.1 모델 변경

기존 `ContentNote`에 nullable 필드를 추가한다.

```swift
var trashedAt: Date?
```

- `nil`: 활성 노트
- 값 존재: 휴지통 노트

기존 저장 데이터는 `trashedAt = nil`로 해석한다. UUID, video ID, canonical URL, 제목, 자막과 기존 생성 시각은 이동·복원 시 바꾸지 않는다. 썸네일은 video ID에서 파생하며 별도 영속 필드를 추가하지 않는다.

### 5.2 저장소 책임

저장소는 다음 연산을 명확히 분리한다.

- 활성 목록 조회: `trashedAt == nil`, `createdAt` 내림차순
- 휴지통 목록 조회: `trashedAt != nil`, `trashedAt` 내림차순
- video ID별 상태 조회: active / trashed / absent
- 휴지통 이동과 관련 route 삭제
- 일반 복원
- 공유 복원과 route 추가
- 영구 삭제와 관련 route 삭제
- cutoff 이전 휴지통 일괄 정리
- 최신 pending route snapshot 조회와 선택적 확인 처리

모든 읽기-판단-쓰기 연산은 기존 App Group 잠금 안에서 새로운 `ModelContext`를 사용한다. 복합 동작은 한 번의 save로 완료하고 save 실패 시 호출자에게 실패를 반환하며 부분 상태를 남기지 않는다.

동시 공유, 삭제, 복원은 잠금 안에서 최신 상태를 다시 읽어 분기한다. 이에 따라 오래된 사전 조회 결과로 새 노트를 중복 생성하거나 복원된 노트를 다시 복원하지 않는다.

## 6. 구성 요소 책임 변경

### 6.1 App shell과 Notes 기능

- App shell: 탭 선택, 각 탐색 스택, pending route 적용, 상세→Home 분석 전달을 조정한다.
- Notes list ViewModel: 활성 목록 새로고침과 휴지통 이동을 담당한다.
- Trash ViewModel: 정리 실행, 휴지통 목록, 복원, 영구 삭제를 담당한다.
- Detail ViewModel: note ID로 최신 데이터를 읽고 원본 열기·분석·휴지통 이동 액션을 제공한다.

화면은 SwiftData `ModelContext`를 직접 조합해 복합 쓰기를 수행하지 않고 저장소 API를 사용한다.

### 6.2 PendingNoteRouter

기존처럼 Home ViewModel에 공유 노트를 바로 적용하지 않는다. 최신 유효 note ID와 확인 대상 route ID를 앱 shell에 전달한다. 앱 shell이 My Notes 상세 탐색 상태를 반영한 후 router가 캡처된 route만 확인 처리한다.

### 6.3 ShareIngestionCoordinator와 ShareExtensionViewModel

수집기는 canonical video ID에 대해 active / trashed / absent 사전 분기를 제공한다. 휴지통 결과에서는 네트워크 작업을 시작하지 않고 확인 대기 상태를 반환한다.

ShareExtensionViewModel은 휴지통 확인 상태를 표현하고 `Restore`와 `Cancel`을 수집기에 전달한다. 복원 성공은 기존 중복 성공 문구인 `Already saved`를 사용한다. 저장 실패는 성공으로 표시하거나 확장을 정상 완료하지 않는다.

## 7. 오류와 경쟁 조건

- 활성 목록·상세 조회 실패: 기존 화면 패턴 안에서 재시도 가능한 상태를 사용하고 새로운 제품 흐름은 만들지 않는다.
- 휴지통 이동, 복원, 영구 삭제 실패: 현재 화면과 원래 데이터 상태를 유지한다.
- 공유 복원 save 실패: 노트와 route 모두 변경되지 않은 상태로 남기고 성공 문구를 표시하지 않는다.
- 휴지통 확인 중 사용자가 확장을 취소: 이후 복원 요청을 무시하고 아무 변경도 저장하지 않는다.
- 상세 표시 중 다른 경로에서 삭제·만료: 상세를 닫아 유효한 목록 상태로 돌아간다.
- 분석 전환 직전 노트가 삭제됨: 전달 시점에 저장된 입력 snapshot을 사용해 기존 Home 분석 흐름을 시작한다.
- 새 공유 route가 기존 snapshot 확인 처리 중 도착: 새 route는 확인 처리 대상에 포함하지 않는다.

## 8. 검증 계획

### 8.1 구현 검증

- 저장소 단위 테스트: 활성·휴지통 정렬, 이동, 복원, 영구 삭제, 관련 route 정리, 원자성
- 보존 기간 테스트: `cutoff` 직전·정확히 경계·직후와 정리 재시도
- 공유 수집 테스트: active / trashed restore / trashed cancel / absent 네 분기와 네트워크 호출 여부
- route 테스트: 상세 수락 후 확인, 고아 route, snapshot 이후 새 route 보존
- 탐색·ViewModel 테스트: 탭 전환, 상세 열기, 한 번의 `Analyze`, 늦은 callback 차단
- 영속성 테스트: 앱 재실행 후 활성·휴지통 상태와 route 유지
- 전체 iOS 회귀 테스트와 백엔드 테스트

구현 시작 전 기준선은 백엔드 `169 passed, 1 skipped`, iOS `41 tests passed`다.

### 8.2 기획 적합성 검증

완료 전 실제 사용자 흐름을 이 문서의 NL-01~NL-11과 다시 대조한다. 특히 다음을 별도로 확인한다.

- 공유 직후 자동 분석되지 않고 My Notes 상세가 열리는가
- 분석은 상세의 `Analyze` 한 번으로만 시작되는가
- 휴지통 중복 공유에서 새 노트가 생성되지 않는가
- 취소 시 복원·API·route가 모두 발생하지 않는가
- 승인되지 않은 화면, 문구, 버튼, 탐색 단계가 추가되지 않았는가

## 9. 기획 대비 상태

### 기획 대비 차이

없음. 이 문서는 대화에서 승인된 MVP 흐름을 구현 가능한 계약으로 구체화한다.

### 해결되지 않은 충돌

없음.

### 근거 없는 추가 요소

없음. 오류 표시는 기존 제품 패턴을 재사용하며 새로운 사용자 노출 상태는 추가하지 않는다.

## 10. 완료 조건

- NL-01~NL-11 구현과 검증이 모두 통과한다.
- 기존 Share Extension과 Home 분석 회귀 테스트가 통과한다.
- `구현 검증`과 `기획 적합성 검증`을 별도로 완료한다.
- `기획 대비 차이`, `해결되지 않은 충돌`, `근거 없는 추가 요소`를 최종 보고에 명시한다.
- 검색·편집·분석 결과 저장·동기화·Android 등 제외 범위가 섞이지 않는다.

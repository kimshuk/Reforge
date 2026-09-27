import SwiftData
import XCTest
@testable import NoteApp

@MainActor
final class ShareIngestionCoordinatorTests: XCTestCase {
    func testNewVideoFetchesTranscriptAndSavesOneNoteAndRoute() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let transcript = TranscriptStub(response: makeResponse())
        let title = TitleStub(result: "Fetched title")
        let coordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: transcript,
            titleResolver: title
        )

        let result = try await coordinator.ingest(
            SharedURLInput(
                url: URL(string: "https://youtu.be/dQw4w9WgXcQ?t=10")!,
                sharedTitle: nil
            )
        )

        guard case let .saved(noteID) = result else {
            return XCTFail("Expected a saved result")
        }
        XCTAssertEqual(transcript.callCount, 1)
        XCTAssertEqual(title.callCount, 1)
        let context = ModelContext(fixture.container)
        let notes = try context.fetch(FetchDescriptor<ContentNote>())
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(notes.first?.id, noteID)
        XCTAssertEqual(notes.first?.sourceURL.absoluteString, "https://youtu.be/dQw4w9WgXcQ?t=10")
        XCTAssertEqual(notes.first?.canonicalURL.absoluteString, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        XCTAssertEqual(notes.first?.title, "Fetched title")
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 1)
    }

    func testDuplicateSkipsAllNetworkAndAddsRoute() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let original = makeDraft()
        _ = try fixture.repository.saveOrReuse(original)
        let transcript = TranscriptStub(response: makeResponse())
        let title = TitleStub(result: "Should not load")
        let coordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: transcript,
            titleResolver: title
        )

        let result = try await coordinator.ingest(
            SharedURLInput(
                url: URL(string: "https://www.youtube.com/shorts/dQw4w9WgXcQ")!,
                sharedTitle: "Changed"
            )
        )

        XCTAssertEqual(result, .alreadySaved(noteID: original.id))
        XCTAssertEqual(transcript.callCount, 0)
        XCTAssertEqual(title.callCount, 0)
        let context = ModelContext(fixture.container)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<ContentNote>()), 1)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 2)
    }

    func testInvalidURLAndTranscriptFailureDoNotSaveAnything() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let invalidTranscript = TranscriptStub(response: makeResponse())
        let invalidCoordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: invalidTranscript,
            titleResolver: TitleStub(result: nil)
        )

        await XCTAssertThrowsErrorAsync {
            try await invalidCoordinator.ingest(
                SharedURLInput(
                    url: URL(string: "https://example.com/video")!,
                    sharedTitle: nil
                )
            )
        }
        XCTAssertEqual(invalidTranscript.callCount, 0)

        let failingTranscript = TranscriptStub(error: StubError.transcript)
        let failingCoordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: failingTranscript,
            titleResolver: TitleStub(result: nil)
        )
        await XCTAssertThrowsErrorAsync {
            try await failingCoordinator.ingest(validInput)
        }

        let context = ModelContext(fixture.container)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<ContentNote>()), 0)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 0)
    }

    func testMismatchedResponseAndSaveFailureDoNotReportSuccess() async throws {
        let repository = RepositoryStub()
        let mismatchCoordinator = ShareIngestionCoordinator(
            repository: repository,
            transcriptService: TranscriptStub(response: makeResponse(videoID: "aaaaaaaaaaa")),
            titleResolver: TitleStub(result: "Title")
        )

        do {
            _ = try await mismatchCoordinator.ingest(validInput)
            XCTFail("Expected identity mismatch")
        } catch let error as ShareIngestionError {
            XCTAssertEqual(error, .videoIdentityMismatch)
        }
        XCTAssertEqual(repository.saveCount, 0)

        repository.saveError = StubError.save
        let saveFailureCoordinator = ShareIngestionCoordinator(
            repository: repository,
            transcriptService: TranscriptStub(response: makeResponse()),
            titleResolver: TitleStub(result: "Title")
        )
        await XCTAssertThrowsErrorAsync {
            try await saveFailureCoordinator.ingest(validInput)
        }
        XCTAssertEqual(repository.saveCount, 1)
    }

    func testCancellationBeforeSaveLeavesNoNoteOrRoute() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let transcript = SuspendedTranscriptStub()
        let coordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: transcript,
            titleResolver: TitleStub(result: nil)
        )
        let task = Task {
            try await coordinator.ingest(
                SharedURLInput(url: validInput.url, sharedTitle: "Title")
            )
        }
        await transcript.waitUntilStarted()

        task.cancel()
        transcript.resume(returning: makeResponse())
        do {
            _ = try await task.value
            XCTFail("Expected cancellation")
        } catch is CancellationError {
        }

        let context = ModelContext(fixture.container)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<ContentNote>()), 0)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 0)
    }

    func testCancellationObservedDuringSaveKeepsCommittedResult() async throws {
        let stored = makeStoredNote()
        let repository = RepositoryStub(saveOutcome: .saved(stored))
        let coordinator = ShareIngestionCoordinator(
            repository: repository,
            transcriptService: TranscriptStub(response: makeResponse()),
            titleResolver: TitleStub(result: "Title")
        )
        var task: Task<ShareIngestionResult, Error>?
        repository.onSave = { task?.cancel() }
        task = Task { try await coordinator.ingest(validInput) }

        let result = try await task?.value

        XCTAssertEqual(result, .saved(noteID: stored.id))
        XCTAssertEqual(repository.saveCount, 1)
    }

    func testTitleFailureFallsBackToCanonicalURL() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let coordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: TranscriptStub(response: makeResponse()),
            titleResolver: TitleStub(result: nil)
        )

        _ = try await coordinator.ingest(validInput)

        let note = try XCTUnwrap(
            ModelContext(fixture.container).fetch(FetchDescriptor<ContentNote>()).first
        )
        XCTAssertEqual(
            note.title,
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
    }

    func testSharedTitleWinsWithoutCallingTitleResolver() async throws {
        let fixture = try makeFixture()
        defer { try? FileManager.default.removeItem(at: fixture.directory) }
        let title = TitleStub(result: "Fetched title")
        let coordinator = ShareIngestionCoordinator(
            repository: fixture.repository,
            transcriptService: TranscriptStub(response: makeResponse()),
            titleResolver: title
        )

        _ = try await coordinator.ingest(
            SharedURLInput(url: validInput.url, sharedTitle: "  Shared title  ")
        )

        let note = try XCTUnwrap(
            ModelContext(fixture.container).fetch(FetchDescriptor<ContentNote>()).first
        )
        XCTAssertEqual(note.title, "Shared title")
        XCTAssertEqual(title.callCount, 0)
    }

    func testTitleResolverReturnsNilAtTimeout() async {
        let resolver = ShareTitleResolver(
            service: SlowTitleService(),
            timeoutNanoseconds: 1_000_000
        )

        let title = await resolver.resolveTitle(
            for: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!
        )

        XCTAssertNil(title)
    }

    private func makeFixture() throws -> (
        directory: URL,
        container: ModelContainer,
        repository: ContentNoteRepository
    ) {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let container = try SharedModelContainer.make(
            at: directory.appendingPathComponent("store.sqlite")
        )
        let repository = ContentNoteRepository(
            container: container,
            lock: SharedStoreLock(
                fileURL: directory.appendingPathComponent("reforge-shared-store.lock")
            )
        )
        return (directory, container, repository)
    }

    private func makeResponse(videoID: String = "dQw4w9WgXcQ") -> YouTubeTranscriptResponse {
        YouTubeTranscriptResponse(
            transcriptId: "11111111-1111-4111-8111-111111111111",
            videoId: videoID,
            canonicalYoutubeUrl: URL(string: "https://www.youtube.com/watch?v=\(videoID)")!,
            transcriptText: "Transcript text",
            languageCode: "en",
            language: "English",
            isGenerated: false
        )
    }

    private func makeDraft() -> ContentNoteDraft {
        ContentNoteDraft(
            id: UUID(),
            sourceKey: "youtube:dQw4w9WgXcQ",
            sourceType: "youtube",
            videoId: "dQw4w9WgXcQ",
            sourceURL: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Original",
            transcriptId: "11111111-1111-4111-8111-111111111111",
            transcriptText: "Original transcript",
            transcriptLanguageCode: "en",
            transcriptIsGenerated: false,
            createdAt: Date(timeIntervalSince1970: 1_000)
        )
    }

    private var validInput: SharedURLInput {
        SharedURLInput(
            url: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            sharedTitle: nil
        )
    }

    private func makeStoredNote() -> StoredContentNote {
        let draft = makeDraft()
        return StoredContentNote(
            id: draft.id,
            sourceKey: draft.sourceKey,
            sourceType: draft.sourceType,
            videoId: draft.videoId,
            sourceURL: draft.sourceURL,
            canonicalURL: draft.canonicalURL,
            title: draft.title,
            transcriptId: draft.transcriptId,
            transcriptText: draft.transcriptText,
            transcriptLanguageCode: draft.transcriptLanguageCode,
            transcriptIsGenerated: draft.transcriptIsGenerated,
            createdAt: draft.createdAt
        )
    }
}

@MainActor
private final class TranscriptStub: YouTubeTranscriptFetching {
    let result: Result<YouTubeTranscriptResponse, Error>
    private(set) var callCount = 0

    init(response: YouTubeTranscriptResponse) {
        result = .success(response)
    }

    init(error: Error) {
        result = .failure(error)
    }

    func fetch(youtubeURL: URL, title: String?) async throws -> YouTubeTranscriptResponse {
        callCount += 1
        return try result.get()
    }
}

@MainActor
private final class SuspendedTranscriptStub: YouTubeTranscriptFetching {
    private var continuation: CheckedContinuation<YouTubeTranscriptResponse, Error>?
    private var startedContinuation: CheckedContinuation<Void, Never>?
    private var didStart = false

    func fetch(youtubeURL: URL, title: String?) async throws -> YouTubeTranscriptResponse {
        didStart = true
        startedContinuation?.resume()
        startedContinuation = nil
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        if didStart { return }
        await withCheckedContinuation { startedContinuation = $0 }
    }

    func resume(returning response: YouTubeTranscriptResponse) {
        continuation?.resume(returning: response)
        continuation = nil
    }
}

@MainActor
private final class RepositoryStub: ContentNotePersisting {
    var found: StoredContentNote?
    var saveOutcome: SaveNoteOutcome
    var saveError: Error?
    var onSave: (() -> Void)?
    private(set) var saveCount = 0

    init(
        found: StoredContentNote? = nil,
        saveOutcome: SaveNoteOutcome? = nil
    ) {
        self.found = found
        let fallback = StoredContentNote(
            id: UUID(),
            sourceKey: "youtube:dQw4w9WgXcQ",
            sourceType: "youtube",
            videoId: "dQw4w9WgXcQ",
            sourceURL: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Title",
            transcriptId: "id",
            transcriptText: "Text",
            transcriptLanguageCode: "en",
            transcriptIsGenerated: false,
            createdAt: Date()
        )
        self.saveOutcome = saveOutcome ?? .saved(fallback)
    }

    func find(sourceKey: String) throws -> StoredContentNote? { found }

    func saveOrReuse(_ draft: ContentNoteDraft) throws -> SaveNoteOutcome {
        saveCount += 1
        onSave?()
        if let saveError { throw saveError }
        return saveOutcome
    }

    func enqueueRoute(noteID: UUID) throws {}
}

private enum StubError: Error {
    case transcript
    case save
}

private struct SlowTitleService: YouTubeTitleService {
    func checkAvailability(for youtubeURL: String) async throws -> YouTubeAvailabilityResult {
        try await Task.sleep(nanoseconds: 5_000_000_000)
        return .available(title: "Too late")
    }
}

private func XCTAssertThrowsErrorAsync<T>(
    _ expression: () async throws -> T,
    file: StaticString = #filePath,
    line: UInt = #line
) async {
    do {
        _ = try await expression()
        XCTFail("Expected error", file: file, line: line)
    } catch {
    }
}

@MainActor
private final class TitleStub: ShareTitleResolving {
    let result: String?
    private(set) var callCount = 0

    init(result: String?) {
        self.result = result
    }

    func resolveTitle(for canonicalURL: URL) async -> String? {
        callCount += 1
        return result
    }
}

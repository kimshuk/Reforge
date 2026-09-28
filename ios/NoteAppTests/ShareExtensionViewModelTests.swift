import SwiftData
import XCTest
@testable import NoteApp

@MainActor
final class ShareExtensionViewModelTests: XCTestCase {
    func testSavedAndDuplicatePublishExactTextThenComplete() async {
        for (result, text) in [
            (ShareIngestionResult.saved(noteID: UUID()), "Saved to Reforge"),
            (.alreadySaved(noteID: UUID()), "Already saved"),
        ] {
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(result: result),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, text)
            XCTAssertFalse(viewModel.isLoading)
            XCTAssertEqual(completed, 1)
            XCTAssertEqual(cancelled, 0)
        }
    }

    func testApprovedTranscriptErrorsStayVisibleWithoutCompleting() async {
        for (code, text) in [
            ("TRANSCRIPT_UNAVAILABLE", "The video is available, but transcript is not available."),
            ("TRANSCRIPT_FETCH_FAILED", "Transcript provider failed. Please try again."),
        ] {
            var completed = 0
            var cancelled = 0
            let error = YouTubeTranscriptServiceError.backend(
                statusCode: 502,
                code: code,
                message: "backend"
            )
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(error: error),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, text)
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 0)
        }
    }

    func testUnknownFailureCancelsWithoutSuccessText() async {
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: IngestorStub(error: TestError.failure),
            complete: {},
            cancel: { cancelled += 1 }
        )

        await viewModel.run(input: validInput)

        XCTAssertNil(viewModel.statusText)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(cancelled, 1)
    }

    func testOfflineAndTimeoutShowApprovedProviderFailureText() async {
        for code in [URLError.notConnectedToInternet, .timedOut] {
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: IngestorStub(error: URLError(code)),
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )

            await viewModel.run(input: validInput)

            XCTAssertEqual(viewModel.statusText, "Transcript provider failed. Please try again.")
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 0)
        }
    }

    func testRestoreConfirmationUsesExactTextAndCompletesOnce() async {
        let noteID = UUID()
        var completed = 0
        var cancelled = 0
        let ingestor = IngestorStub(result: .restoreRequired(noteID: noteID))
        let viewModel = ShareExtensionViewModel(
            ingestor: ingestor,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )

        await viewModel.run(input: validInput)
        XCTAssertEqual(viewModel.phase, .awaitingRestore(noteID))
        XCTAssertEqual(viewModel.statusText, "This video is in Trash. Restore it?")
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertEqual(completed, 0)

        await viewModel.confirmRestore()
        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertEqual(viewModel.statusText, "Already saved")
        XCTAssertEqual(completed, 1)
        XCTAssertEqual(cancelled, 0)
    }

    func testCancelPreventsLaterRestoreAndFinishesOnce() async {
        let noteID = UUID()
        var completed = 0
        var cancelled = 0
        let ingestor = IngestorStub(result: .restoreRequired(noteID: noteID))
        let viewModel = ShareExtensionViewModel(
            ingestor: ingestor,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )
        await viewModel.run(input: validInput)

        viewModel.cancelRestore()
        await viewModel.confirmRestore()
        viewModel.cancelRestore()

        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertEqual(completed, 0)
        XCTAssertEqual(cancelled, 1)
        XCTAssertEqual(ingestor.restoreCount, 0)
    }

    func testCancelThenRestoreLeavesRealTrashedNoteUnchanged() async throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let storeURL = directory.appendingPathComponent("store.sqlite")
        let container = try SharedModelContainer.make(at: storeURL)
        let repository = ContentNoteRepository(
            container: container,
            lock: SharedStoreLock(fileURL: directory.appendingPathComponent("store.lock"))
        )
        let noteID = UUID()
        let trashedAt = Date(timeIntervalSince1970: 2_000)
        let transcriptText = "Original transcript"
        let draft = ContentNoteDraft(
            id: noteID,
            sourceKey: "youtube:dQw4w9WgXcQ",
            sourceType: "youtube",
            videoId: "dQw4w9WgXcQ",
            sourceURL: validInput.url,
            canonicalURL: URL(string: "https://www.youtube.com/watch?v=dQw4w9WgXcQ")!,
            title: "Original title",
            transcriptId: "11111111-1111-4111-8111-111111111111",
            transcriptText: transcriptText,
            transcriptLanguageCode: "en",
            transcriptIsGenerated: false,
            createdAt: Date(timeIntervalSince1970: 1_000)
        )
        _ = try repository.saveOrReuse(draft)
        try repository.moveToTrash(noteID: noteID, at: trashedAt)
        let transcript = CountingTranscriptStub()
        let title = CountingTitleStub()
        let coordinator = ShareIngestionCoordinator(
            repository: repository,
            transcriptService: transcript,
            titleResolver: title
        )
        var completed = 0
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: coordinator,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )

        await viewModel.run(input: validInput)
        XCTAssertEqual(viewModel.phase, .awaitingRestore(noteID))
        viewModel.cancelRestore()
        await viewModel.confirmRestore()

        let reopened = try SharedModelContainer.make(at: storeURL)
        let context = ModelContext(reopened)
        let notes = try context.fetch(FetchDescriptor<ContentNote>())
        XCTAssertEqual(notes.count, 1)
        XCTAssertEqual(notes.first?.id, noteID)
        XCTAssertEqual(notes.first?.transcriptText, transcriptText)
        XCTAssertEqual(notes.first?.trashedAt, trashedAt)
        XCTAssertEqual(try context.fetchCount(FetchDescriptor<PendingNoteRoute>()), 0)
        XCTAssertEqual(transcript.callCount, 0)
        XCTAssertEqual(title.callCount, 0)
        XCTAssertEqual(completed, 0)
        XCTAssertEqual(cancelled, 1)
    }

    func testRapidRestoreTapsAndCancelIgnoreLateCompletion() async {
        let noteID = UUID()
        let ingestor = SuspendedRestoreIngestor(noteID: noteID)
        var completed = 0
        var cancelled = 0
        let viewModel = ShareExtensionViewModel(
            ingestor: ingestor,
            complete: { completed += 1 },
            cancel: { cancelled += 1 }
        )
        await viewModel.run(input: validInput)

        let first = Task { await viewModel.confirmRestore() }
        await ingestor.waitUntilStarted()
        XCTAssertEqual(viewModel.phase, .restoring(noteID))
        XCTAssertTrue(viewModel.isLoading)
        await viewModel.confirmRestore()
        XCTAssertEqual(ingestor.restoreCount, 1)
        viewModel.cancelRestore()
        ingestor.resume(returning: .alreadySaved(noteID: noteID))
        await first.value

        XCTAssertEqual(viewModel.phase, .finished)
        XCTAssertNotEqual(viewModel.statusText, "Already saved")
        XCTAssertEqual(completed, 0)
        XCTAssertEqual(cancelled, 1)
    }

    func testFailedOrExternallyCancelledRestoreNeverCompletes() async {
        for cancelTask in [false, true] {
            let noteID = UUID()
            let ingestor = SuspendedRestoreIngestor(noteID: noteID)
            var completed = 0
            var cancelled = 0
            let viewModel = ShareExtensionViewModel(
                ingestor: ingestor,
                complete: { completed += 1 },
                cancel: { cancelled += 1 }
            )
            await viewModel.run(input: validInput)
            let task = Task { await viewModel.confirmRestore() }
            await ingestor.waitUntilStarted()
            if cancelTask { task.cancel() }
            if cancelTask {
                ingestor.resume(returning: .alreadySaved(noteID: noteID))
            } else {
                ingestor.resume(throwing: TestError.failure)
            }
            await task.value

            XCTAssertEqual(viewModel.phase, .finished)
            XCTAssertNotEqual(viewModel.statusText, "Already saved")
            XCTAssertEqual(completed, 0)
            XCTAssertEqual(cancelled, 1)
        }
    }

    private var validInput: SharedURLInput {
        SharedURLInput(
            url: URL(string: "https://youtu.be/dQw4w9WgXcQ")!,
            sharedTitle: nil
        )
    }
}

@MainActor
private final class IngestorStub: ShareIngesting {
    let result: Result<ShareIngestionResult, Error>
    private(set) var restoreCount = 0

    init(result: ShareIngestionResult) { self.result = .success(result) }
    init(error: Error) { result = .failure(error) }

    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult {
        try result.get()
    }

    func restore(noteID: UUID) async throws -> ShareIngestionResult {
        restoreCount += 1
        return .alreadySaved(noteID: noteID)
    }
}

@MainActor
private final class CountingTranscriptStub: YouTubeTranscriptFetching {
    private(set) var callCount = 0

    func fetch(youtubeURL: URL, title: String?) async throws -> YouTubeTranscriptResponse {
        callCount += 1
        throw TestError.failure
    }
}

@MainActor
private final class CountingTitleStub: ShareTitleResolving {
    private(set) var callCount = 0

    func resolveTitle(for canonicalURL: URL) async -> String? {
        callCount += 1
        return nil
    }
}

@MainActor
private final class SuspendedRestoreIngestor: ShareIngesting {
    let noteID: UUID
    private var continuation: CheckedContinuation<ShareIngestionResult, Error>?
    private var startedContinuation: CheckedContinuation<Void, Never>?
    private(set) var restoreCount = 0

    init(noteID: UUID) { self.noteID = noteID }

    func ingest(_ input: SharedURLInput) async throws -> ShareIngestionResult {
        .restoreRequired(noteID: noteID)
    }

    func restore(noteID: UUID) async throws -> ShareIngestionResult {
        restoreCount += 1
        startedContinuation?.resume()
        startedContinuation = nil
        return try await withCheckedThrowingContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        if restoreCount > 0 { return }
        await withCheckedContinuation { startedContinuation = $0 }
    }

    func resume(returning result: ShareIngestionResult) {
        continuation?.resume(returning: result)
        continuation = nil
    }

    func resume(throwing error: Error) {
        continuation?.resume(throwing: error)
        continuation = nil
    }
}

private enum TestError: Error { case failure }
